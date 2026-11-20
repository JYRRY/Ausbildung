"""Health check for the Bundesagentur Jobsuche API.

The BA has retired endpoints without notice before (``/pc/v4/jobs`` started
answering 403), and the finder then silently yields nothing. This check runs
one broad search plus one detail fetch and reports every way the answer
deviates from what the finder relies on, so an admin hears about it within the
hour instead of from users.

Used by the bot's hourly watch job (:mod:`jyry.jobs.ba_health_watch`), the
admin ``/ba`` command, and the standalone CLI
(:mod:`jyry.scripts.ba_health`) that GitHub Actions can run without a server.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

from jyry.services.bundesagentur import BundesagenturClient

# A nationwide search for one of the largest Ausbildung professions: far
# above this in practice (thousands), so anything lower means the API or
# its filters changed.
PROBE_QUERY = "Kaufmann"
MIN_EXPECTED_TOTAL = 50
_PROBE_PAGE_SIZE = 5


@dataclass(frozen=True, slots=True)
class HealthReport:
    """Outcome of one check. ``problems`` is empty when the API is healthy."""

    problems: list[str] = field(default_factory=list)
    search_total: int | None = None
    sample_refnr: str | None = None
    elapsed_seconds: float = 0.0

    @property
    def ok(self) -> bool:
        return not self.problems


def _describe_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} من {exc.request.url.path}"
    return f"{type(exc).__name__}: {exc}"[:200]


async def check_ba(client: BundesagenturClient) -> HealthReport:
    """Run the probe search and one detail fetch; never raises."""
    started = time.monotonic()
    problems: list[str] = []
    total: int | None = None
    refnr: str | None = None

    try:
        page = await client.search(was=PROBE_QUERY, page=1, size=_PROBE_PAGE_SIZE)
    except Exception as exc:  # every failure is a finding
        problems.append(f"البحث فشل: {_describe_error(exc)}")
        return HealthReport(problems, None, None, time.monotonic() - started)

    total = page.total
    if total < MIN_EXPECTED_TOTAL:
        problems.append(
            f"البحث رجع {total} نتيجة فقط لـ «{PROBE_QUERY}» "
            f"(المتوقع أكثر من {MIN_EXPECTED_TOTAL}) — غالباً تغيّر شكل الرد"
        )
    if not page.hits:
        problems.append("البحث رجع بلا إعلانات قابلة للقراءة (لا يوجد referenznummer)")
        return HealthReport(problems, total, None, time.monotonic() - started)

    if not any(hit.employer for hit in page.hits):
        problems.append("الإعلانات بلا اسم شركة (الحقل firma اختفى)")
    if not any(hit.location_city for hit in page.hits):
        problems.append("الإعلانات بلا مدينة (الحقل stellenlokationen تغيّر)")

    first = page.hits[0]
    refnr = first.refnr
    try:
        detail = await client.fetch_detail(first.hash_id)
    except Exception as exc:
        problems.append(f"تفاصيل الإعلان فشلت: {_describe_error(exc)}")
    else:
        if not detail.description:
            problems.append("تفاصيل الإعلان بلا نص (stellenangebotsBeschreibung)")
        if not detail.employer:
            problems.append("تفاصيل الإعلان بلا اسم شركة")

    return HealthReport(problems, total, refnr, time.monotonic() - started)


def format_alert(report: HealthReport) -> str:
    """Plain-text admin message for a failed check."""
    lines = ["🚨 مشكلة في API الوكالة (BA)", ""]
    lines += [f"• {p}" for p in report.problems]
    lines += [
        "",
        "النتيجة: النظام لن يجد إعلانات جديدة حتى يُصلح هذا.",
        f"مدة الفحص: {report.elapsed_seconds:.1f} ث",
    ]
    return "\n".join(lines)


def format_recovery(report: HealthReport) -> str:
    return (
        "✅ API الوكالة (BA) عاد يعمل\n\n"
        f"نتائج البحث التجريبي: {report.search_total}\n"
        f"مدة الفحص: {report.elapsed_seconds:.1f} ث"
    )


def format_status(report: HealthReport) -> str:
    """Reply for the admin ``/ba`` command — healthy or not."""
    if not report.ok:
        return format_alert(report)
    return (
        "✅ API الوكالة (BA) يعمل\n\n"
        f"نتائج البحث التجريبي «{PROBE_QUERY}»: {report.search_total}\n"
        f"إعلان العيّنة: {report.sample_refnr}\n"
        f"مدة الفحص: {report.elapsed_seconds:.1f} ث"
    )


__all__ = [
    "MIN_EXPECTED_TOTAL",
    "PROBE_QUERY",
    "HealthReport",
    "check_ba",
    "format_alert",
    "format_recovery",
    "format_status",
]
