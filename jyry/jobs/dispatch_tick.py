"""One scheduler tick: run :func:`dispatch_one` once, then re-schedule.

Kept side-effect-light: the only state we touch outside ``dispatch_one`` is
a Redis transient-retry counter (``jyry:retry:user:<id>``) that lets us
implement 5 min → 30 min → 2 h back-off across separate ticks. Permanent
failures and successes reset the counter.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from jyry.bot import messages
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.models import User
from jyry.jobs.timing import (
    next_run_at_midnight,
    next_run_for_quota,
    transient_retry_after,
)
from jyry.payments.notify import send_telegram_notice
from jyry.services import deduper
from jyry.services.send_pending import (
    DispatchOutcome,
    DispatchResult,
    dispatch_one,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jyry.config import Settings
    from jyry.services.bundesagentur import BundesagenturClient
    from jyry.services.rate_limiter import DailyQuotaLimiter
    from jyry.services.send_pending import AttachmentFetcher

logger = logging.getLogger(__name__)

_RETRY_KEY_PREFIX = "jyry:retry:user"
_RETRY_KEY_TTL_SECONDS = 60 * 60 * 24


@dataclass(slots=True)
class TickDeps:
    """Bundles everything ``tick_user`` needs without going through globals."""

    settings: Settings
    session_factory: Callable[[], AsyncSession]
    ba_client: BundesagenturClient
    limiter: DailyQuotaLimiter
    fetcher: AttachmentFetcher
    schedule_at: Callable[[int, datetime], Awaitable[None]]
    redis: object  # redis.asyncio.Redis[str] — kept loose to avoid TYPE_CHECKING import


def _retry_key(user_id: int) -> str:
    return f"{_RETRY_KEY_PREFIX}:{user_id}"


async def _get_retry_attempts(deps: TickDeps, user_id: int) -> int:
    raw = await deps.redis.get(_retry_key(user_id))  # type: ignore[attr-defined]
    return int(raw) if raw else 0


async def _bump_retry_attempts(deps: TickDeps, user_id: int) -> int:
    new_value = await deps.redis.incr(_retry_key(user_id))  # type: ignore[attr-defined]
    await deps.redis.expire(  # type: ignore[attr-defined]
        _retry_key(user_id), _RETRY_KEY_TTL_SECONDS
    )
    return int(new_value)


async def _reset_retry_attempts(deps: TickDeps, user_id: int) -> None:
    await deps.redis.delete(_retry_key(user_id))  # type: ignore[attr-defined]


async def _user_remaining_quota(
    deps: TickDeps, session: AsyncSession, user_id: int
) -> int:
    _, remaining = await _user_plan_and_remaining(deps, session, user_id)
    return remaining


async def _user_plan_and_remaining(
    deps: TickDeps, session: AsyncSession, user_id: int
) -> tuple[str, int]:
    user = (
        await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(selectinload(User.subscription))
        )
    ).scalar_one_or_none()
    if user is None:
        return "free", 0
    sub = user.subscription
    if sub is None or sub.plan is None:
        plan_value = "free"
    else:
        plan_value = sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)
    quota = PLAN_DAILY_QUOTA.get(plan_value, PLAN_DAILY_QUOTA["free"])
    remaining = await deps.limiter.remaining(user_id, quota)
    return plan_value, remaining


def _utcnow() -> datetime:
    return datetime.now(tz=UTC)


async def _send_sent_notification(
    deps: TickDeps,
    user_id: int,
    plan_value: str,
    remaining: int,
) -> None:
    """Per-send Telegram ping. First send of the day includes the user's
    specialties so they recognise context; subsequent sends are reduced to a
    counter only to keep the chat tidy. Skipped unless mode == 'per_send'.

    Company / job title are intentionally NOT included — broadcasting employer
    names back to users would let them scrape the bot for application targets.
    """
    async with deps.session_factory() as session:
        user = (
            await session.execute(
                select(User)
                .where(User.id == user_id)
                .options(selectinload(User.specialties))
            )
        ).scalar_one_or_none()
    if user is None or user.notification_mode != "per_send":
        return
    if user.telegram_id is None:
        return

    quota = PLAN_DAILY_QUOTA.get(plan_value, PLAN_DAILY_QUOTA["free"])
    sent_today = max(quota - remaining, 0)
    is_first_today = sent_today == 1
    if is_first_today:
        specialties = ", ".join(s.specialty_keyword for s in user.specialties) or "—"
        text = messages.NOTIFICATION_EMAIL_SENT_FIRST.format(
            specialties=specialties,
            sent_today=sent_today,
            daily_quota=quota,
        )
    else:
        text = messages.NOTIFICATION_EMAIL_SENT.format(
            sent_today=sent_today, daily_quota=quota
        )

    try:
        await send_telegram_notice(
            token=deps.settings.telegram_bot_token.get_secret_value(),
            chat_id=user.telegram_id,
            text=text,
        )
    except Exception:
        logger.exception("notification send failed user_id=%s", user_id)


async def tick_user(user_id: int, *, deps: TickDeps) -> DispatchResult:
    """Run one send attempt for ``user_id`` and re-schedule the next tick."""
    settings = deps.settings
    tz = settings.tz

    try:
        async with deps.session_factory() as session:
            result = await dispatch_one(
                user_id=user_id,
                settings=settings,
                session=session,
                ba_client=deps.ba_client,
                limiter=deps.limiter,
                fetcher=deps.fetcher,
            )
    except Exception:
        logger.exception("tick_user crashed for user_id=%s", user_id)
        # Crash means an unhandled bug; retry on the regular cadence so a
        # single bad row doesn't permanently park the user.
        retry_after = timedelta(seconds=settings.send_min_interval_seconds * 5)
        await deps.schedule_at(user_id, _utcnow() + retry_after)
        return DispatchResult(DispatchOutcome.TRANSIENT_FAILURE, detail="tick crashed")

    now = _utcnow()
    next_run: datetime | None = None

    settled = (DispatchOutcome.SENT, DispatchOutcome.PERMANENT_FAILURE)
    if result.outcome in settled:
        await _reset_retry_attempts(deps, user_id)
        async with deps.session_factory() as session:
            plan_value, remaining = await _user_plan_and_remaining(
                deps, session, user_id
            )
        if result.outcome is DispatchOutcome.SENT:
            await _send_sent_notification(deps, user_id, plan_value, remaining)
        if plan_value == "free" and remaining > 0:
            # Marketing: Free trial fires its 5 sends back-to-back so the
            # user experiences the bot at full throttle within seconds.
            next_run = now + timedelta(seconds=2)
        else:
            next_run = next_run_for_quota(
                now=now,
                remaining_quota=remaining,
                min_interval=timedelta(seconds=settings.send_min_interval_seconds),
                jitter=timedelta(seconds=settings.send_jitter_seconds),
                tz=tz,
            )

    elif result.outcome is DispatchOutcome.TRANSIENT_FAILURE:
        attempt = await _bump_retry_attempts(deps, user_id)
        backoff = transient_retry_after(attempt, settings.send_transient_retry_seconds)
        if backoff is None and result.application_id is not None:
            async with deps.session_factory() as session:
                await deduper.mark_failed(
                    session,
                    result.application_id,
                    error_message=f"transient retries exhausted: {result.detail or ''}",
                )
                await session.commit()
            await _reset_retry_attempts(deps, user_id)
            async with deps.session_factory() as session:
                remaining = await _user_remaining_quota(deps, session, user_id)
            next_run = next_run_for_quota(
                now=now,
                remaining_quota=remaining,
                min_interval=timedelta(seconds=settings.send_min_interval_seconds),
                jitter=timedelta(seconds=settings.send_jitter_seconds),
                tz=tz,
            )
        else:
            next_run = now + (backoff or timedelta(seconds=settings.send_min_interval_seconds))

    elif result.outcome is DispatchOutcome.NO_POSTING_FOUND:
        async with deps.session_factory() as session:
            plan_value, _ = await _user_plan_and_remaining(deps, session, user_id)
        # Free users should not stare at a silent bot for 30 minutes when no
        # posting matches their filter — keep poking BA every minute.
        no_posting_backoff_seconds = (
            60 if plan_value == "free" else settings.send_no_posting_backoff_seconds
        )
        next_run = now + timedelta(seconds=no_posting_backoff_seconds)

    elif result.outcome is DispatchOutcome.QUOTA_EXHAUSTED:
        next_run = next_run_at_midnight(now, tz)

    elif result.outcome is DispatchOutcome.USER_NOT_READY:
        next_run = None  # caller (bot onboarding handler) re-activates explicitly

    if next_run is not None:
        await deps.schedule_at(user_id, next_run)

    return result
