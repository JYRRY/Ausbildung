"""High-level orchestration: turn a user's (specialties x states) selection
into an async stream of email-enriched, cache-deduplicated postings ready
for the M3 sender to dispatch.

Iteration order: (specialty_outer, state_inner). For each pair we page
through the Bundesagentur search results, check the 24h cache, and only
fetch detail + extract email on cache misses. Postings without a recoverable
non-generic email are silently dropped, matching the project rule.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from itertools import product
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

from jyry.constants import STATE_LABELS_DE
from jyry.services import job_cache_repo
from jyry.services.bundesagentur import BundesagenturClient, SearchHit
from jyry.services.email_extractor import extract_result
from jyry.services.job_cache_repo import fallback_employer_ref

if TYPE_CHECKING:
    from jyry.services.website_crawler import WebsiteCrawler

logger = logging.getLogger(__name__)

_DEFAULT_SEARCH_PAGES = 5
_DEFAULT_SEARCH_SIZE = 100


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


@dataclass(frozen=True, slots=True)
class ReadyPosting:
    """One ready-to-send posting yielded by ``iter_ready_postings``."""

    employer_ref: str
    email: str
    company: str | None
    job_title: str | None
    location: str | None
    state_code: str | None
    specialty_keyword: str
    hash_id: str
    contact_person: str | None = None


def _employer_ref(hit: SearchHit) -> str:
    return hit.kundennummer_hash or fallback_employer_ref(hit.employer)


def _location_string(hit: SearchHit) -> str | None:
    parts = [p for p in (hit.location_plz, hit.location_city) if p]
    return " ".join(parts) if parts else None


async def iter_ready_postings(
    session: AsyncSession,
    client: BundesagenturClient,
    *,
    specialties: Iterable[str],
    states: Iterable[str],
    want: int,
    ttl: timedelta,
    max_pages_per_query: int = _DEFAULT_SEARCH_PAGES,
    page_size: int = _DEFAULT_SEARCH_SIZE,
    crawler: WebsiteCrawler | None = None,
    crawl_budget: int = 0,
) -> AsyncIterator[ReadyPosting]:
    """Yield up to ``want`` ``ReadyPosting`` items.

    The function is a generator — callers can stop early with ``break`` and
    no further HTTP traffic will be issued.

    When a posting carries no email and ``crawler`` is provided (up to
    ``crawl_budget`` times per call), the employer's own website is crawled as
    a fallback. Crawl outcomes are persisted on the cache row so the same
    employer is not re-crawled within ``ttl``.
    """
    if want <= 0:
        return

    seen_refs: set[str] = set()
    produced = 0
    crawls_left = crawl_budget if crawler is not None else 0

    for specialty, state in product(specialties, states):
        wo_label = STATE_LABELS_DE.get(state)
        for page in range(1, max_pages_per_query + 1):
            search_page = await client.search(
                was=specialty, wo=wo_label, page=page, size=page_size
            )
            if not search_page.hits:
                break

            for hit in search_page.hits:
                ref = _employer_ref(hit)
                if ref in seen_refs:
                    continue
                seen_refs.add(ref)

                cached = await job_cache_repo.get_fresh(session, ref, ttl)
                if cached is not None:
                    email = cached.email
                    contact = cached.contact_person
                    # Un-poison: a no-email row that was never crawled and has a
                    # known website gets one crawl attempt now.
                    if (
                        not email
                        and crawler is not None
                        and crawls_left > 0
                        and cached.crawl_attempted_at is None
                        and cached.website_url
                    ):
                        crawls_left -= 1
                        result = await crawler.crawl(cached.website_url)
                        email = result.email
                        contact = result.contact_person or contact
                        await job_cache_repo.upsert(
                            session,
                            employer_ref=ref,
                            raw=cached.raw_data,
                            email=email,
                            company=cached.company_name,
                            title=cached.job_title,
                            location=cached.location,
                            state_code=cached.state_code,
                            specialty_keyword=cached.specialty_keyword,
                            contact_person=contact,
                            website_url=cached.website_url,
                            crawl_attempted_at=_utcnow(),
                        )
                        await session.commit()
                    if not email:
                        continue
                    yield ReadyPosting(
                        employer_ref=ref,
                        email=email,
                        company=cached.company_name,
                        job_title=cached.job_title,
                        location=cached.location,
                        state_code=cached.state_code,
                        specialty_keyword=cached.specialty_keyword or specialty,
                        hash_id=hit.hash_id,
                        contact_person=contact,
                    )
                    produced += 1
                    if produced >= want:
                        return
                    continue

                try:
                    detail = await client.fetch_detail(hit.hash_id)
                except Exception:
                    logger.warning("detail fetch failed for hash=%s", hit.hash_id)
                    continue

                extracted = extract_result(detail)
                email = extracted.email
                contact = extracted.contact_person
                website = extracted.website_url
                location = _location_string(hit)
                crawl_attempted: datetime | None = None

                # Fallback: no email in the posting → crawl the employer site.
                if (
                    email is None
                    and crawler is not None
                    and crawls_left > 0
                    and website
                ):
                    crawls_left -= 1
                    result = await crawler.crawl(website)
                    email = result.email
                    contact = result.contact_person or contact
                    crawl_attempted = _utcnow()

                await job_cache_repo.upsert(
                    session,
                    employer_ref=ref,
                    raw=detail.raw,
                    email=email,
                    company=detail.employer or hit.employer,
                    title=detail.title or hit.profession,
                    location=location,
                    state_code=state,
                    specialty_keyword=specialty,
                    contact_person=contact,
                    website_url=website,
                    crawl_attempted_at=crawl_attempted,
                )
                await session.commit()

                if email is None:
                    continue

                yield ReadyPosting(
                    employer_ref=ref,
                    email=email,
                    company=detail.employer or hit.employer,
                    job_title=detail.title or hit.profession,
                    location=location,
                    state_code=state,
                    specialty_keyword=specialty,
                    hash_id=hit.hash_id,
                    contact_person=contact,
                )
                produced += 1
                if produced >= want:
                    return

            if len(search_page.hits) < page_size:
                break  # last page reached
