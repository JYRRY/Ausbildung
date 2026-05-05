"""Best-effort recovery of an employer email from a Bundesagentur JobDetail.

The API doesn't expose an email field; the address — when present — sits in
the free-text job description. We walk three layers:

1. Structured fields (future-proof: in case BA adds them).
2. ``mailto:`` links inside the description.
3. Raw regex over the (HTML-stripped) description body.

Generic addresses (``info@``, ``no-reply@``, ``*@arbeitsagentur.de``, …) are
filtered out — better to drop a posting than spam an inbox the recruiter
never reads.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from typing import Any

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
_MAILTO_RE = re.compile(r"mailto:([^\"'>\s?]+)", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")

GENERIC_LOCALPARTS: frozenset[str] = frozenset(
    {
        "noreply",
        "no-reply",
        "donotreply",
        "do-not-reply",
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
        "postmaster",
        "mailer-daemon",
        "abuse",
    }
)
GENERIC_DOMAINS: frozenset[str] = frozenset(
    {
        "arbeitsagentur.de",
        "bundesagentur.de",
        "jobboerse.de",
        "example.com",
        "example.de",
        "example.org",
        "test.de",
    }
)
PREFERRED_LOCALPARTS: tuple[str, ...] = (
    "bewerbung",
    "ausbildung",
    "karriere",
    "career",
    "jobs",
    "personal",
    "hr",
    "recruiting",
    "recruitment",
)


def _strip_html(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", html.unescape(_HTML_TAG_RE.sub(" ", text))).strip()


def _normalise(addr: str) -> str:
    return addr.strip().strip(".,;:<>()[]\"'").lower()


def _split(addr: str) -> tuple[str, str] | None:
    if "@" not in addr:
        return None
    local, _, domain = addr.partition("@")
    if not local or not domain or "." not in domain:
        return None
    return local, domain


def _is_generic(addr: str) -> bool:
    parts = _split(addr)
    if parts is None:
        return True
    local, domain = parts
    if local in GENERIC_LOCALPARTS:
        return True
    if domain in GENERIC_DOMAINS:
        return True
    return any(domain.endswith("." + g) for g in GENERIC_DOMAINS)


def _score(addr: str) -> int:
    """Higher = more preferred. Used to pick the best of several candidates."""
    parts = _split(addr)
    if parts is None:
        return -1
    local, _ = parts
    for i, preferred in enumerate(PREFERRED_LOCALPARTS):
        if local == preferred or local.startswith(preferred + ".") or local.startswith(
            preferred + "-"
        ):
            return 100 - i
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
        yield match.group(1)

    # Layer 3 — regex over the plain text.
    for match in EMAIL_RE.finditer(_strip_html(body)):
        yield match.group("addr")


def extract_email(detail: JobDetail) -> str | None:
    """Return the most-preferred non-generic email in ``detail`` or None."""
    seen: set[str] = set()
    candidates: list[str] = []
    for raw_addr in _iter_candidates(detail):
        addr = _normalise(raw_addr)
        if not addr or addr in seen:
            continue
        seen.add(addr)
        if _is_generic(addr):
            continue
        candidates.append(addr)

    if not candidates:
        return None
    return max(candidates, key=_score)
