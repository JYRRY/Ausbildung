"""Process-wide AsyncIOScheduler facade.

One ``AsyncIOScheduler`` per bot process; per-user tick jobs live under
the canonical id ``send:<user_id>`` so re-scheduling is idempotent under
two coroutines racing on the same user (e.g. webhook reactivating a paid
subscription while a previous tick is finishing). Persistence is a memory
job-store: the M3.c date-keyed Redis quota plus M3.d's QUEUED rows make
recovery on restart deterministic — we just sweep the DB and re-schedule.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from sqlalchemy import select

from jyry.db.models import User

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jyry.config import Settings
    from jyry.jobs.dispatch_tick import TickDeps

logger = logging.getLogger(__name__)

_JOB_ID_PREFIX = "send"


def job_id_for(user_id: int) -> str:
    return f"{_JOB_ID_PREFIX}:{user_id}"


class JyryScheduler:
    """Schedules per-user dispatch ticks with APScheduler."""

    def __init__(
        self,
        settings: Settings,
        deps_factory: Callable[[], TickDeps],
    ) -> None:
        self._settings = settings
        self._deps_factory = deps_factory
        self._scheduler = AsyncIOScheduler(timezone=str(settings.tz))

    async def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()

    async def stop(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)

    async def activate_user(self, user_id: int) -> None:
        """Schedule the first tick immediately (next event-loop turn)."""
        await self.schedule_at(user_id, datetime.now(tz=UTC) + timedelta(seconds=1))

    async def deactivate_user(self, user_id: int) -> None:
        try:
            self._scheduler.remove_job(job_id_for(user_id))
        except Exception:
            logger.debug("deactivate_user: no job to remove for user_id=%s", user_id)

    async def schedule_at(self, user_id: int, when: datetime) -> None:
        """Add or replace the per-user tick at ``when`` (UTC-aware datetime)."""
        self._scheduler.add_job(
            func=_run_tick,
            trigger=DateTrigger(run_date=when),
            args=[user_id, self._deps_factory],
            id=job_id_for(user_id),
            replace_existing=True,
            misfire_grace_time=300,
            coalesce=True,
        )

    async def sweep_active_users(self, session: AsyncSession) -> int:
        """Schedule a tick for every ready user — call once at startup."""
        rows = await session.execute(
            select(User.id).where(
                User.is_active.is_(True), User.onboarding_complete.is_(True)
            )
        )
        count = 0
        for user_id in rows.scalars():
            await self.activate_user(user_id)
            count += 1
        return count


async def _run_tick(user_id: int, deps_factory: Callable[[], TickDeps]) -> None:
    """APScheduler entry point — imports lazily to avoid import cycles."""
    from jyry.jobs.dispatch_tick import tick_user

    deps = deps_factory()
    # Wire the scheduler.schedule_at into the deps the tick can call back into.
    if not hasattr(deps, "schedule_at") or deps.schedule_at is None:  # pragma: no cover
        raise RuntimeError("TickDeps.schedule_at must be set by deps_factory")
    await tick_user(user_id, deps=deps)


async def shutdown_helper(scheduler: JyryScheduler) -> None:  # pragma: no cover
    await scheduler.stop()


__all__ = ["JyryScheduler", "job_id_for"]
