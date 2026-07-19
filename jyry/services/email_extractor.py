"""Recover an employer email (and HR contact) for an Ausbildung posting.

Two entry points:

* :func:`extract_email` — the original behaviour: pull the best non-generic
  email out of a Bundesagentur :class:`JobDetail` (structured fields → mailto
  links → regex over the HTML-stripped description). Used on the cheap first
  pass.
* :func:`extract_emails_from_html` / :func:`extract_result` — a richer, HTML
  multi-strategy harvester used by :mod:`jyry.services.website_crawler` when the
  posting itself carries no email and we fall back to crawling the employer's
  own website (Impressum / Kontakt / Karriere).

Generic addresses (``info@``, ``no-reply@``, ``*@arbeitsagentur.de``, …) are
dropped from the *posting* path — better to skip than to spam an inbox the
recruiter never reads. On the employer's *own* website the softer generics
(``info@``, ``kontakt@``) are accepted as a last resort, because small
Handwerksbetriebe genuinely take applications there.
"""

from __future__ import annotations

import html as html_lib
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urljoin, urlparse

from jyry.services.bundesagentur import JobDetail

# RFC-5322 is overkill; this regex catches the addresses we actually see in
# Bundesagentur descriptions and rejects punctuation that bleeds in from
# surrounding text.
EMAIL_RE = re.compile(
    r"(?<![A-Za-z0-9._%+\-])"
    r"(?P<addr>[A-Za-z0-9._%+\-]+@[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?)+)"
    r"(?![A-Za-z0-9\-])"
)
_MAILTO_RE = re.compile(r"mailto:([^\"'>\s?&]+)", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

# Local-parts that should never be contacted (bounces / automated inboxes).
_HARD_BLOCK_LOCALPARTS: frozenset[str] = frozenset(
    {
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
        "mailer-daemon",
        "postmaster",
        "abuse",
    }
)
# Generic role inboxes: dropped from the posting text, but acceptable (ranked
# last) when found on the employer's own website.
_SOFT_GENERIC_LOCALPARTS: frozenset[str] = frozenset(
    {
        "info",
        "kontakt",
        "contact",
        "support",
        "service",
        "office",
        "datenschutz",
        "privacy",
        "presse",
        "press",
        "marketing",
        "webmaster",
    }
)
GENERIC_LOCALPARTS: frozenset[str] = _HARD_BLOCK_LOCALPARTS | _SOFT_GENERIC_LOCALPARTS

# Domains we must never send to: the job portals themselves, ATS vendors,
# site-builders and other infrastructure whose addresses are never the real
# employer.
GENERIC_DOMAINS: frozenset[str] = frozenset(
    {
        # BA + generic placeholders (original project list)
        "arbeitsagentur.de",
        "bundesagentur.de",
        "jobboerse.de",
        "example.com",
        "example.de",
        "example.org",
        "test.de",
        "test.com",
        "domain.com",
        "email.com",
        # Job portals / aggregators
        "stepstone.de",
        "stepstone.at",
        "stepstone.ch",
        "indeed.com",
        "indeed.de",
        "monster.de",
        "monster.com",
        "heyjobs.co",
        "heyjobs.de",
        "jobware.de",
        "stellenanzeigen.de",
        "meinestadt.de",
        "absolventa.de",
        "azubi.de",
        "azubiyo.de",
        "ausbildung.de",
        "aubi-plus.de",
        "ausbildungsmarkt.de",
        "praktikum.de",
        "berufsstart.de",
        "jobscout24.de",
        "kimeta.de",
        "joblift.de",
        "jobstairs.de",
        "jobmensa.de",
        "jobteaser.com",
        # ATS vendors
        "softgarden.io",
        "softgarden.de",
        "personio.de",
        "personio.com",
        "rexx-systems.com",
        "d.vinci.de",
        # Site-builders / infra / big tech (never real contact emails)
        "wixpress.com",
        "squarespace.com",
        "wordpress.com",
        "shopify.com",
        "jimdo.com",
        "sentry.io",
        "amazonaws.com",
        "google.com",
        "facebook.com",
        "twitter.com",
        "instagram.com",
        "linkedin.com",
        "youtube.com",
        "schema.org",
        "w3.org",
    }
)

# Preferred local-parts, best first — drives ranking of multiple candidates.
PREFERRED_LOCALPARTS: tuple[str, ...] = (
    "bewerbung",
    "ausbildung",
    "karriere",
    "career",
    "jobs",
    "stellenangebote",
    "personal",
    "personalabteilung",
    "hr",
    "recruiting",
    "recruitment",
    "hiring",
)

# File extensions that masquerade as TLDs in scraped text.
FALSE_POSITIVE_TLDS: frozenset[str] = frozenset(
    {
        "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "bmp", "tiff",
        "css", "js", "html", "htm", "php", "asp", "jsp",
        "pdf", "doc", "docx", "xls", "xlsx", "zip", "rar",
        "woff", "woff2", "ttf", "eot", "map", "json", "xml",
    }
)

# Placeholder / demo local-parts (Max Mustermann, John Doe, test@ …).
_PLACEHOLDER_PREFIXES: tuple[str, ...] = (
    "mustermann",
    "max.mustermann",
    "maxmustermann",
    "johndoe",
    "john.doe",
    "jane.doe",
    "erika.mustermann",
    "vorname.nachname",
    "vorname",
    "name.nachname",
    "youremail",
    "username",
    "placeholder",
    "example",
    "beispiel",
)

# Common email obfuscation → real characters.
_OBFUSCATION_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\[\s*at\s*\]", "@"),
    (r"\(\s*at\s*\)", "@"),
    (r"\{\s*at\s*\}", "@"),
    (r"\[\s*ät\s*\]", "@"),
    (r"\[\s*dot\s*\]", "."),
    (r"\(\s*dot\s*\)", "."),
    (r"\[\s*punkt\s*\]", "."),
    (r"\(\s*punkt\s*\)", "."),
    (r"＠", "@"),  # fullwidth ＠
    (r"．", "."),  # fullwidth ．
    (r"&#0?64;", "@"),
    (r"&#x40;", "@"),
    (r"(?<=\w)\s+@\s+(?=\w)", "@"),
    (r"(?<=\w)\s+\.\s+(?=\w)", "."),
)

# HTML harvesting strategies (compiled once), in confidence order.
_JSONLD_EMAIL_RE = re.compile(r'"email"\s*:\s*"([^"]+)"', re.IGNORECASE)
_JSONLD_CONTACT_RE = re.compile(
    r'"contactPoint"[^}]{0,2000}?"email"\s*:\s*"([^"]+)"', re.IGNORECASE | re.DOTALL
)
_DATA_EMAIL_RE = re.compile(
    r'data-(?:email|mail|contact)\s*=\s*["\']([^"\']{1,254})["\']', re.IGNORECASE
)
_META_EMAIL_RE = re.compile(
    r'<meta[^>]{0,500}content\s*=\s*["\']([^"\']{0,254}@[^"\']{0,254})["\']',
    re.IGNORECASE,
)
_VCARD_EMAIL_RE = re.compile(
    r'class\s*=\s*["\'][^"\']{0,200}\bemail\b[^"\']{0,200}["\'][^>]{0,200}>([^<]{1,254})<',
    re.IGNORECASE,
)
_ATTR_EMAIL_RE = re.compile(
    r'(?:aria-label|title|value|content)\s*=\s*["\']([^"\']{1,254})["\']',
    re.IGNORECASE,
)

# Employer website URL fields in the BA detail payload, best first. (Confirmed:
# ``externeUrl`` on search hits; ``arbeitgeberdarstellungUrl`` verified live at
# wiring time. Portal/ATS domains are rejected downstream.)
_WEBSITE_RAW_KEYS: tuple[str, ...] = (
    "arbeitgeberdarstellungUrl",
    "externeUrl",
    "allianzpartnerUrl",
)

# HTML byte cap: keep head (meta/JSON-LD) + tail (footer/Impressum) for CPU
# safety on huge pages.
_MAX_HTML_BYTES = 120_000
_HEAD_BYTES = 80_000
_TAIL_BYTES = 40_000


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    """Everything the extractor found for one posting."""

    email: str | None
    contact_person: str | None
    website_url: str | None
    all_emails: list[str] = field(default_factory=list)


# ── posting path (cheap, first) ───────────────────────────────────────────────


def _strip_html(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", html_lib.unescape(_HTML_TAG_RE.sub(" ", text))).strip()


def _deobfuscate(text: str) -> str:
    for pattern, replacement in _OBFUSCATION_PATTERNS:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def _normalise(addr: str) -> str:
    return addr.strip().strip(".,;:<>()[]\"'").lower()


def _split(addr: str) -> tuple[str, str] | None:
    if "@" not in addr:
        return None
    local, _, domain = addr.partition("@")
    if not local or not domain or "." not in domain:
        return None
    return local, domain


def _is_valid_email(addr: str, *, accept_generic: bool = False) -> bool:
    """Structural + policy validation.

    ``accept_generic`` lets the *website-crawl* path keep ``info@``/``kontakt@``
    (ranked last). The hard blocks (noreply, placeholders, portal domains,
    file-extension TLDs) always apply.
    """
    parts = _split(addr)
    if parts is None:
        return False
    local, domain = parts
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    if domain in GENERIC_DOMAINS or any(
        domain.endswith("." + g) for g in GENERIC_DOMAINS
    ):
        return False
    if domain.split(".")[-1] in FALSE_POSITIVE_TLDS:
        return False

    if local in _HARD_BLOCK_LOCALPARTS:
        return False
    if any(local == p or local.startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return False
    if not accept_generic and local in _SOFT_GENERIC_LOCALPARTS:
        return False
    return True


# Back-compat alias (kept for any external callers / clarity).
def _is_generic(addr: str) -> bool:
    return not _is_valid_email(addr, accept_generic=False)


def _score(addr: str, *, from_website: bool = False) -> int:
    """Higher = more preferred. Preferred local-parts first; on a website a
    soft-generic (info@/kontakt@) ranks below a normal address but is still
    usable."""
    parts = _split(addr)
    if parts is None:
        return -100
    local, _ = parts
    for i, preferred in enumerate(PREFERRED_LOCALPARTS):
        if local == preferred or local.startswith(f"{preferred}.") or local.startswith(
            f"{preferred}-"
        ):
            return 100 - i
    if from_website and local in _SOFT_GENERIC_LOCALPARTS:
        return -10
    return 0


def _iter_candidates(detail: JobDetail) -> Iterable[str]:
    raw: dict[str, Any] = detail.raw or {}

    # Layer 1 — structured fields the API may add later.
    for key in ("bewerbungEmail", "kontaktEmail", "applicationEmail", "email"):
        value = raw.get(key)
        if isinstance(value, str) and "@" in value:
            yield value
    kontakt = raw.get("kontakt")
    if isinstance(kontakt, dict):
        for value in kontakt.values():
            if isinstance(value, str) and "@" in value:
                yield value

    body = detail.description or ""
    if not body:
        return

    # Layer 2 — mailto links (HTML-encoded or raw).
    for match in _MAILTO_RE.finditer(body):
        yield unquote(match.group(1))

    # Layer 3 — regex over the plain, de-obfuscated text.
    for match in EMAIL_RE.finditer(_deobfuscate(_strip_html(body))):
        yield match.group("addr")


def extract_email(detail: JobDetail) -> str | None:
    """Return the most-preferred non-generic email in ``detail`` or None."""
    candidates = _collect(_iter_candidates(detail), accept_generic=False)
    if not candidates:
        return None
    return max(candidates, key=_score)


def extract_result(detail: JobDetail) -> ExtractionResult:
    """Posting-only extraction plus the employer website URL (for crawling)."""
    candidates = _collect(_iter_candidates(detail), accept_generic=False)
    email = max(candidates, key=_score) if candidates else None
    contact = extract_contact_person_from_html(detail.description or "")
    return ExtractionResult(
        email=email,
        contact_person=contact,
        website_url=employer_website(detail),
        all_emails=candidates,
    )


def _collect(raw_addrs: Iterable[str], *, accept_generic: bool) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw_addr in raw_addrs:
        addr = _normalise(raw_addr)
        if not addr or addr in seen:
            continue
        seen.add(addr)
        if _is_valid_email(addr, accept_generic=accept_generic):
            out.append(addr)
    return out


def employer_website(detail: JobDetail) -> str | None:
    """Return a crawlable employer website URL from the detail payload, or None
    if absent or pointing at a portal/ATS domain."""
    raw = detail.raw or {}
    for key in _WEBSITE_RAW_KEYS:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        url = normalize_website(value)
        host = urlparse(url).netloc.lower().split(":")[0]
        host = host[4:] if host.startswith("www.") else host
        if host and host not in GENERIC_DOMAINS and not any(
            host.endswith("." + g) for g in GENERIC_DOMAINS
        ):
            return url
    return None


# ── website-crawl path (HTML multi-strategy) ─────────────────────────────────


def _cap_html(page: str) -> str:
    encoded = page.encode("utf-8", errors="replace")
    if len(encoded) <= _MAX_HTML_BYTES:
        return page
    head = encoded[:_HEAD_BYTES]
    tail = encoded[-_TAIL_BYTES:]
    return (head + tail).decode("utf-8", errors="replace")


def extract_emails_from_html(page: str, *, accept_generic: bool = True) -> list[str]:
    """Harvest valid emails from an HTML page, ranked best-first.

    Strategies in confidence order: mailto → JSON-LD email → contactPoint →
    data-* attrs → meta → vCard → other attribute payloads → stripped text.
    """
    if not page:
        return []
    page = _cap_html(page)
    found: list[str] = []
    seen: set[str] = set()

    def _add(candidate: str) -> None:
        addr = _normalise(html_lib.unescape(candidate))
        if addr and addr not in seen and _is_valid_email(
            addr, accept_generic=accept_generic
        ):
            seen.add(addr)
            found.append(addr)

    for m in _MAILTO_RE.finditer(page):
        _add(unquote(m.group(1)))
    for regex in (_JSONLD_EMAIL_RE, _JSONLD_CONTACT_RE, _DATA_EMAIL_RE):
        for m in regex.finditer(page):
            _add(m.group(1))
    for regex in (_META_EMAIL_RE, _VCARD_EMAIL_RE, _ATTR_EMAIL_RE):
        for m in regex.finditer(page):
            for hit in EMAIL_RE.finditer(_deobfuscate(m.group(1))):
                _add(hit.group("addr"))
    for m in EMAIL_RE.finditer(_deobfuscate(_strip_html(page))):
        _add(m.group("addr"))

    found.sort(key=lambda a: _score(a, from_website=True), reverse=True)
    return found


def extract_contact_person_from_text(text: str) -> str | None:
    """Best-effort HR contact ('Frau/Herr <Name>') from free text."""
    if not text:
        return None
    pattern = (
        r"\b(Frau|Herr)\s+"
        # Titles with a literal dot must be tried before the general name token,
        # otherwise "Dr." is captured as the bare word "Dr" and matching stops.
        r"((?:(?:Dr\.|Prof\.|Dipl\.|med\.|[A-ZÄÖÜ][a-zA-Zäöüß\-]+|von|van|der|de|zu)\s*){1,5})"
    )
    for salutation, raw_name in re.findall(pattern, text):
        name = re.sub(r"[\s,;:!?]+$", "", raw_name).strip()
        if len(name) > 2 and not name.lower().startswith(("und", "oder")):
            return f"{salutation} {name}"
    return None


def extract_contact_person_from_html(page: str) -> str | None:
    return extract_contact_person_from_text(_strip_html(_cap_html(page))) if page else None


def normalize_website(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def get_contact_page_urls(base_url: str, discovery_paths: Iterable[str]) -> list[str]:
    """Home page + candidate contact/legal pages for a domain."""
    parsed = urlparse(base_url)
    root = f"{parsed.scheme}://{parsed.netloc}"
    urls = [base_url]
    for path in discovery_paths:
        candidate = urljoin(root + "/", path)
        if candidate not in urls:
            urls.append(candidate)
    return urls
