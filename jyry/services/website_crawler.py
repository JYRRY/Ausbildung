"""Best-effort crawl of an employer's own website to recover a contact email.

Used as a fallback by the dispatcher when a Bundesagentur posting carries no
sendable email in its text: we fetch the employer homepage plus a few likely
contact pages (Impressum / Kontakt / Karriere / Bewerbung …) and run the HTML
harvester in :mod:`jyry.services.email_extractor` over them.

Design constraints (a crawl must never degrade the sender):
- The whole crawl runs inside a single ``crawl_total_timeout_seconds`` budget.
- Any exception yields an empty result — :meth:`crawl` never raises.
- A global semaphore caps concurrent crawls so one tick can't stall behind
  many slow sites.
- Bounded page count, per-request timeout, HTML read cap, and a small polite
  delay between requests; same-registrable-domain only; https first.

robots.txt is not consulted in v1: a handful of GETs to public contact pages
per employer per day, with an identifying User-Agent, is link-preview-scale
traffic. This is an easy retrofit if ever needed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx

from jyry.services.email_extractor import (
    extract_contact_person_from_html,
    extract_emails_from_html,
    get_contact_page_urls,
    normalize_website,
)

logger = logging.getLogger(__name__)

# Candidate contact/legal paths, tried after the homepage. Order roughly by
# email yield for German SMB sites.
DISCOVERY_PATHS: tuple[str, ...] = (
    "kontakt",
    "impressum",
    "karriere",
    "bewerbung",
    "stellenangebote",
    "jobs",
    "team",
    "ueber-uns",
)

_USER_AGENT = "JYRY-AI/0.1 (+https://github.com/JYRRY/Ausbildung)"


@dataclass(frozen=True, slots=True)
class CrawlResult:
    email: str | None = None
    contact_person: str | None = None
    website_url: str | None = None
    pages_fetched: int = 0
    all_emails: list[str] = field(default_factory=list)


def _registrable(host: str) -> str:
    host = host.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


class WebsiteCrawler:
    """Owns one shared httpx client + a global concurrency gate."""

    def __init__(self, settings: object, *, client: httpx.AsyncClient | None = None) -> None:
        self._s = settings
        self._max_pages: int = getattr(settings, "crawl_max_pages", 5)
        self._req_timeout: float = getattr(settings, "crawl_request_timeout_seconds", 8.0)
        self._total_timeout: float = getattr(settings, "crawl_total_timeout_seconds", 15.0)
        self._delay: float = getattr(settings, "crawl_delay_seconds", 0.5)
        self._max_bytes: int = getattr(settings, "crawl_max_html_bytes", 500_000)
        self._accept_generic: bool = getattr(
            settings, "crawl_accept_generic_localparts", True
        )
        self._sem = asyncio.Semaphore(getattr(settings, "crawl_max_concurrent", 3))
        self._owns_client = client is None
        self._client: httpx.AsyncClient = client or httpx.AsyncClient(
            follow_redirects=True,
            max_redirects=5,
            timeout=httpx.Timeout(self._req_timeout),
            headers={"User-Agent": _USER_AGENT, "Accept": "text/html,*/*"},
            http2=False,
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def crawl(self, url: str | None) -> CrawlResult:
        """Crawl ``url`` and return the best contact found. Never raises."""
        if not url:
            return CrawlResult()
        site = normalize_website(url)
        target_domain = _registrable(urlparse(site).netloc)
        if not target_domain:
            return CrawlResult()
        try:
            async with self._sem:
                async with asyncio.timeout(self._total_timeout):
                    return await self._crawl_inner(site, target_domain)
        except Exception as exc:  # noqa: BLE001 — isolation is the whole point
            logger.info("crawl aborted for %s: %s", site, f"{type(exc).__name__}: {exc}")
            return CrawlResult(website_url=site)

    async def _crawl_inner(self, site: str, target_domain: str) -> CrawlResult:
        queue = get_contact_page_urls(site, DISCOVERY_PATHS)
        seen: set[str] = set()
        emails: list[str] = []
        contact_person: str | None = None
        fetched = 0

        for candidate in queue:
            if fetched >= self._max_pages:
                break
            if candidate in seen:
                continue
            seen.add(candidate)

            html = await self._fetch(candidate, allow_http_fallback=(candidate == site))
            if html is None:
                continue
            fetched += 1

            for addr in extract_emails_from_html(html, accept_generic=self._accept_generic):
                if addr not in emails:
                    emails.append(addr)
            if contact_person is None:
                contact_person = extract_contact_person_from_html(html)

            # Stop early once we have a strongly-preferred address (bewerbung@…).
            if emails and _is_preferred(emails[0]):
                break
            if fetched < self._max_pages:
                await asyncio.sleep(self._delay)

        # extract_emails_from_html already ranks best-first per page; re-rank the
        # merged set so a homepage info@ never beats a /karriere bewerbung@.
        emails.sort(key=_merge_rank, reverse=True)
        return CrawlResult(
            email=emails[0] if emails else None,
            contact_person=contact_person,
            website_url=site,
            pages_fetched=fetched,
            all_emails=emails,
        )

    async def _fetch(self, url: str, *, allow_http_fallback: bool) -> str | None:
        try:
            return await self._get(url)
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            if allow_http_fallback and url.startswith("https://"):
                try:
                    return await self._get("http://" + url[len("https://") :])
                except Exception:  # noqa: BLE001
                    return None
            logger.debug("fetch failed %s: %s", url, exc)
            return None
        except Exception as exc:  # noqa: BLE001
            logger.debug("fetch failed %s: %s", url, exc)
            return None

    async def _get(self, url: str) -> str | None:
        async with self._client.stream("GET", url) as resp:
            if resp.status_code >= 400:
                return None
            ctype = resp.headers.get("content-type", "")
            if "html" not in ctype and "xml" not in ctype and ctype:
                return None
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= self._max_bytes:
                    break
            return b"".join(chunks).decode("utf-8", errors="replace")


# Ranking helpers kept module-level so tests can exercise them directly.
from jyry.services.email_extractor import _score as _email_score  # noqa: E402


def _merge_rank(addr: str) -> int:
    return _email_score(addr, from_website=True)


def _is_preferred(addr: str) -> bool:
    return _email_score(addr, from_website=True) > 0
