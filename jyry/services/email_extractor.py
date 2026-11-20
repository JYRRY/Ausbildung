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

Address policy, strictest first:

* **Never contacted** — automated, administrative and compliance inboxes
  (``no-reply@``, ``datenschutz@``, ``rechnung@``, ``poststelle@`` …, also as
  a prefix such as ``rechnung-eingang@``), job portals / ATS vendors, and
  court / police domains unless the address is an explicit recruiting inbox.
* **General inbox** (``info@``, ``kontakt@``, ``contact@``, ``office@``) —
  accepted from the posting text and from the employer's own website, but
  ranked below every personal or HR address, because small
  Handwerksbetriebe genuinely take applications there.
* **Other departments** (``support@``, ``presse@``, ``marketing@`` …) — only
  from the employer's own website, ranked last.
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

# Automated, administrative and compliance inboxes: nobody there reads job
# applications, and some (Datenschutz, Poststelle) are legally sensitive to
# spam. Blocked as the whole local part or as a prefix followed by ".", "-"
# or "_" ("datenschutz.berlin@", "rechnung-eingang@").
_HARD_BLOCK_LOCALPARTS: frozenset[str] = frozenset(
    {
        # automated / bounces
        "noreply",
        "no-reply",
        "no_reply",
        "donotreply",
        "do-not-reply",
        "do_not_reply",
        "mailer-daemon",
        "bounce",
        # server / admin
        "postmaster",
        "hostmaster",
        "webmaster",
        "abuse",
        "security",
        "noc",
        "spam",
        # compliance / legal
        "datenschutz",
        "dsgvo",
        "privacy",
        "dpo",
        "gdpr",
        # official authority intake
        "poststelle",
        # billing / accounting
        "rechnung",
        "rechnungen",
        "billing",
        "invoice",
        "invoices",
        "buchhaltung",
        "accounting",
        "finanzen",
        "finance",
        # one-way mailings
        "newsletter",
        "feedback",
    }
)
_LOCALPART_PREFIX_SEPARATORS: tuple[str, ...] = (".", "-", "_")

# The company's general inbox: accepted from the posting and the website, but
# ranked below any personal or HR address.
GENERAL_INBOX_LOCALPARTS: frozenset[str] = frozenset(
    {
        "info",
        "kontakt",
        "contact",
        "office",
    }
)
# Other departments' role inboxes: only from the employer's own website
# (``accept_generic``), ranked last.
_DEPARTMENT_LOCALPARTS: frozenset[str] = frozenset(
    {
        "support",
        "service",
        "presse",
        "press",
        "marketing",
    }
)
# Never accepted from the posting text.
GENERIC_LOCALPARTS: frozenset[str] = _HARD_BLOCK_LOCALPARTS | _DEPARTMENT_LOCALPARTS

# Court and police domains: their addresses are case-file intake, not HR. A
# posting may still name an explicit recruiting inbox there (e.g.
# ausbildung@olg-muenchen.justiz.bayern.de), so only preferred local parts
# get through.
_AUTHORITY_DOMAINS: tuple[str, ...] = (
    "justiz.de",
    "justiz.nrw.de",
    "justiz.bayern.de",
    "justiz.hessen.de",
    "polizei.de",
    "polizei.nrw.de",
    "polizei.bayern.de",
)

# Self-hosted job boards outside GENERIC_DOMAINS: their support desks are
# never the employer.
_PORTAL_DOMAIN_KEYWORDS: tuple[str, ...] = (
    "jobboerse",
    "jobportal",
    "stellenportal",
    "stellenmarkt",
)
_PORTAL_SUPPORT_LOCALPARTS: frozenset[str] = frozenset(
    {
        "support",
        "help",
        "kundenservice",
        "service",
        "admin",
    }
)

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
        # BA "Allianzpartner" boards whose ads flow into the v6 search
        # (seen live in partner-sourced Ausbildung postings, 2026-11)
        "gute-jobs.de",
        "finest-jobs.com",
        "jobexport.de",
        "persy.jobs",
        "hogapage.de",
        "genau-mein-job.de",
        "sopea.com",
        "jobboerse-direkt.de",
        "helixjobs.com",
        "deinjob.de",
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

# Employer website URL fields in the BA detail payload, best first. Portal/ATS
# domains are rejected downstream. ``allianzpartnerUrl`` is deliberately absent:
# it names the board a posting came from (BA itself or a partner portal such as
# ausbildung.de), never the employer.
_WEBSITE_RAW_KEYS: tuple[str, ...] = (
    "arbeitgeberdarstellungUrl",
    "externeURL",
    "externeUrl",
)
# For postings fed in by a partner board, ``externeURL`` is that board's ad page.
_EXTERNAL_URL_KEYS: frozenset[str] = frozenset({"externeURL", "externeUrl"})

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


def _matches_localpart(local: str, names: frozenset[str]) -> bool:
    if local in names:
        return True
    return any(
        local.startswith(name + sep)
        for name in names
        for sep in _LOCALPART_PREFIX_SEPARATORS
    )


def _preferred_rank(local: str) -> int | None:
    """Index into PREFERRED_LOCALPARTS for a recruiting inbox, else None."""
    for i, preferred in enumerate(PREFERRED_LOCALPARTS):
        if local == preferred or local.startswith((f"{preferred}.", f"{preferred}-")):
            return i
    return None


def _on_domain(domain: str, suffixes: Iterable[str]) -> bool:
    return any(domain == s or domain.endswith("." + s) for s in suffixes)


def _is_valid_email(
    addr: str,
    *,
    accept_generic: bool = False,
    accept_general_inbox: bool = False,
) -> bool:
    """Structural + policy validation.

    ``accept_general_inbox`` keeps ``info@``/``kontakt@`` (the posting path);
    ``accept_generic`` additionally keeps other departments' role inboxes (the
    website-crawl path). Both rank last. The hard blocks (automated and
    compliance inboxes, placeholders, portal and authority domains,
    file-extension TLDs) always apply.
    """
    parts = _split(addr)
    if parts is None:
        return False
    local, domain = parts
    if local.startswith(".") or local.endswith(".") or ".." in local:
        return False

    if _on_domain(domain, GENERIC_DOMAINS):
        return False
    if domain.split(".")[-1] in FALSE_POSITIVE_TLDS:
        return False
    if _on_domain(domain, _AUTHORITY_DOMAINS) and _preferred_rank(local) is None:
        return False
    if local in _PORTAL_SUPPORT_LOCALPARTS and any(
        kw in domain for kw in _PORTAL_DOMAIN_KEYWORDS
    ):
        return False

    if _matches_localpart(local, _HARD_BLOCK_LOCALPARTS):
        return False
    if any(local == p or local.startswith(p) for p in _PLACEHOLDER_PREFIXES):
        return False
    if local in GENERAL_INBOX_LOCALPARTS:
        return accept_generic or accept_general_inbox
    if local in _DEPARTMENT_LOCALPARTS:
        return accept_generic
    return True


def is_recruiting_inbox(addr: str) -> bool:
    """True for an explicit recruiting address (``bewerbung@``, ``ausbildung@`` …)."""
    parts = _split(addr)
    return parts is not None and _preferred_rank(parts[0]) is not None


def is_general_inbox(addr: str) -> bool:
    """True for a company's catch-all inbox (``info@``, ``kontakt@`` …)."""
    parts = _split(addr)
    return parts is not None and parts[0] in GENERAL_INBOX_LOCALPARTS


# Back-compat alias (kept for any external callers / clarity).
def _is_generic(addr: str) -> bool:
    return not _is_valid_email(addr, accept_generic=False)


def _score(addr: str, *, from_website: bool = False) -> int:
    """Higher = more preferred. Recruiting inboxes first, then personal and
    other addresses, then the general inbox, then other departments.

    ``from_website`` is kept for callers; the ranking no longer depends on it
    because the general inbox is now accepted from postings too."""
    del from_website
    parts = _split(addr)
    if parts is None:
        return -100
    local, _ = parts
    rank = _preferred_rank(local)
    if rank is not None:
        return 100 - rank
    if local in GENERAL_INBOX_LOCALPARTS:
        return -10
    if local in _DEPARTMENT_LOCALPARTS:
        return -20
    return 0


def pick_best_email(*addrs: str | None) -> str | None:
    """The highest-ranked of ``addrs`` (Nones ignored); earlier wins ties."""
    present = [a for a in addrs if a]
    return max(present, key=_score) if present else None


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
    """Return the most-preferred usable email in ``detail`` or None."""
    candidates = _collect(_iter_candidates(detail))
    if not candidates:
        return None
    return max(candidates, key=_score)


def extract_result(detail: JobDetail) -> ExtractionResult:
    """Posting-only extraction plus the employer website URL (for crawling)."""
    candidates = _collect(_iter_candidates(detail))
    email = max(candidates, key=_score) if candidates else None
    contact = extract_contact_person_from_html(detail.description or "")
    return ExtractionResult(
        email=email,
        contact_person=contact,
        website_url=employer_website(detail),
        all_emails=candidates,
    )


def _collect(raw_addrs: Iterable[str]) -> list[str]:
    """Normalised, de-duplicated posting candidates that pass the policy."""
    seen: set[str] = set()
    out: list[str] = []
    for raw_addr in raw_addrs:
        addr = _normalise(raw_addr)
        if not addr or addr in seen:
            continue
        seen.add(addr)
        if _is_valid_email(addr, accept_general_inbox=True):
            out.append(addr)
    return out


def _host(url: str) -> str:
    host = urlparse(url).netloc.lower().split(":")[0]
    return host[4:] if host.startswith("www.") else host


def _is_generic_host(host: str) -> bool:
    return _on_domain(host, GENERIC_DOMAINS)


def _is_partner_sourced(raw: dict[str, Any]) -> bool:
    """True when the posting was fed into BA by a partner board."""
    partner = raw.get("allianzpartnerUrl")
    if not isinstance(partner, str) or not partner.strip():
        return False
    host = _host(normalize_website(partner))
    return host != "arbeitsagentur.de" and not host.endswith(".arbeitsagentur.de")


def employer_website(detail: JobDetail) -> str | None:
    """Return a crawlable employer website URL from the detail payload, or None
    if absent or pointing at a portal/ATS domain."""
    raw = detail.raw or {}
    partner_sourced = _is_partner_sourced(raw)
    for key in _WEBSITE_RAW_KEYS:
        if partner_sourced and key in _EXTERNAL_URL_KEYS:
            continue
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        url = normalize_website(value)
        host = _host(url)
        if host and not _is_generic_host(host):
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
