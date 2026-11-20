"""Hourly job: watch the Bundesagentur API and tell the admins when it breaks.

Alerts on the transition healthy → broken, repeats the alert every
``REMIND_EVERY`` while it stays broken, and sends one all-clear when it
recovers. Healthy hours stay silent.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterable
from datetime import UTC, datetime, timedelta

from jyry.services.ba_health import HealthReport, check_ba, format_alert, format_recovery
from jyry.services.bundesagentur import BundesagenturClient

logger = logging.getLogger(__name__)

REMIND_EVERY = timedelta(hours=6)

Notify = Callable[[int, str], Awaitable[bool]]


class BaHealthWatch:
    """Remembers the last outcome between runs (one instance per bot process)."""

    def __init__(self, *, now: Callable[[], datetime] | None = None) -> None:
        self._now = now or (lambda: datetime.now(tz=UTC))
        self.last_ok: bool | None = None
        self.last_alert_at: datetime | None = None

    def message_for(self, report: HealthReport) -> str | None:
        """The admin message this report calls for, or None to stay silent."""
        now = self._now()
        was_ok = self.last_ok
        self.last_ok = report.ok

        if report.ok:
            if was_ok is False:
                self.last_alert_at = None
                return format_recovery(report)
            return None

        if (
            was_ok is not False
            or self.last_alert_at is None
            or now - self.last_alert_at >= REMIND_EVERY
        ):
            self.last_alert_at = now
            return format_alert(report)
        return None


async def run_ba_health_watch(
    *,
    watch: BaHealthWatch,
    client: BundesagenturClient,
    admin_ids: Iterable[int],
    notify: Notify,
) -> HealthReport:
    """One scheduled run: check, then message every admin if needed."""
    report = await check_ba(client)
    if report.ok:
        logger.info("BA health ok (total=%s, %.1fs)", report.search_total,
                    report.elapsed_seconds)
    else:
        logger.warning("BA health FAILED: %s", "; ".join(report.problems))

    text = watch.message_for(report)
    if text:
        for chat_id in admin_ids:
            await notify(chat_id, text)
    return report


__all__ = ["REMIND_EVERY", "BaHealthWatch", "run_ba_health_watch"]
