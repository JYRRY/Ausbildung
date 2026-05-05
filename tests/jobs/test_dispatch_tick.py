"""Tests for jyry.jobs.dispatch_tick.tick_user."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio

from jyry.db.enums import ApplicationStatus, Language, Plan, SubscriptionStatus
from jyry.db.models import (
    Application,
    EmailDraft,
    Subscription,
    User,
    UserSpecialty,
    UserState,
)
from jyry.jobs.dispatch_tick import TickDeps, tick_user
from jyry.services.crypto import encrypt_secret
from jyry.services.rate_limiter import DailyQuotaLimiter
from jyry.services.send_pending import DispatchOutcome, DispatchResult


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


def _build_deps(
    settings,
    db_session,
    redis,
    *,
    schedule_at: AsyncMock | None = None,
) -> TickDeps:
    schedule_at = schedule_at or AsyncMock()

    @asynccontextmanager
    async def _factory():
        # Yield the same db_session across all internal opens — fine for tests
        # since aiosqlite + the conftest fixture keep it alive for the run.
        yield db_session

    limiter = DailyQuotaLimiter(redis, settings)
    return TickDeps(
        settings=settings,
        session_factory=_factory,
        ba_client=MagicMock(),
        limiter=limiter,
        fetcher=MagicMock(),
        schedule_at=schedule_at,
        redis=redis,
    )


async def _seed_user(session, *, plan: Plan = Plan.PRO) -> User:
    user = User(
        telegram_id=99,
        full_name="Bob",
        gmail_address="bob@gmail.com",
        gmail_app_password_enc=encrypt_secret("pw"),
        language=Language.AR,
        is_active=True,
        onboarding_complete=True,
    )
    session.add(user)
    await session.flush()
    session.add(
        Subscription(
            user_id=user.id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            daily_quota=100,
            emails_sent_today=0,
        )
    )
    session.add(
        EmailDraft(
            user_id=user.id,
            subject_template="Bewerbung {{company}}",
            body_template="text",
            attachments_meta=[],
        )
    )
    session.add(UserSpecialty(user_id=user.id, specialty_keyword="Bäcker"))
    session.add(UserState(user_id=user.id, state_code="BY"))
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_sent_outcome_resets_retry_and_schedules_next_quota_tick(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)

    # Pretend a previous tick failed transiently — counter at 2.
    await redis.set(f"jyry:retry:user:{user.id}", "2")

    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(return_value=DispatchResult(DispatchOutcome.SENT, application_id=1)),
    )
    await tick_user(user.id, deps=deps)

    assert schedule_at.call_count == 1
    sched_user_id, sched_when = schedule_at.call_args.args
    assert sched_user_id == user.id
    assert sched_when > datetime.now(tz=UTC)
    # Counter cleared.
    assert await redis.get(f"jyry:retry:user:{user.id}") is None


@pytest.mark.asyncio
async def test_transient_outcome_uses_backoff_schedule(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)

    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(
            return_value=DispatchResult(
                DispatchOutcome.TRANSIENT_FAILURE, application_id=7, detail="421 busy"
            )
        ),
    )
    before = datetime.now(tz=UTC)
    await tick_user(user.id, deps=deps)

    assert schedule_at.call_count == 1
    _, when = schedule_at.call_args.args
    delta = (when - before).total_seconds()
    # First retry slot is 300s in the default config.
    assert 290 < delta < 360
    # Counter incremented to 1.
    assert await redis.get(f"jyry:retry:user:{user.id}") == "1"


@pytest.mark.asyncio
async def test_transient_exhaustion_marks_application_failed(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    # Pre-create the QUEUED application row that the tick will mark FAILED.
    db_session.add(
        Application(
            user_id=user.id,
            kundennummer="kn-X",
            company_name="X",
            email_to="x@y.de",
            email_subject="s",
            status=ApplicationStatus.QUEUED.value,
        )
    )
    await db_session.commit()
    app_id = (
        await db_session.execute(
            __import__("sqlalchemy").select(Application.id).where(
                Application.kundennummer == "kn-X"
            )
        )
    ).scalar_one()

    # 3 prior transient failures already on the counter — the 4th is the limit.
    await redis.set(f"jyry:retry:user:{user.id}", "3")

    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)
    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(
            return_value=DispatchResult(
                DispatchOutcome.TRANSIENT_FAILURE,
                application_id=app_id,
                detail="421 busy",
            )
        ),
    )
    await tick_user(user.id, deps=deps)

    refreshed = (
        await db_session.execute(
            __import__("sqlalchemy").select(Application).where(Application.id == app_id)
        )
    ).scalar_one()
    assert refreshed.status == ApplicationStatus.FAILED.value
    assert refreshed.error_message and "transient retries exhausted" in refreshed.error_message
    # Counter cleared after exhaustion.
    assert await redis.get(f"jyry:retry:user:{user.id}") is None


@pytest.mark.asyncio
async def test_quota_exhausted_routes_to_midnight(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)
    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(return_value=DispatchResult(DispatchOutcome.QUOTA_EXHAUSTED)),
    )
    await tick_user(user.id, deps=deps)
    assert schedule_at.call_count == 1
    _, when = schedule_at.call_args.args
    # Next run must land on local-midnight, which is at most 24h away.
    delta = when - datetime.now(tz=UTC)
    assert timedelta(0) < delta <= timedelta(hours=24, minutes=1)


@pytest.mark.asyncio
async def test_no_posting_uses_backoff(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)
    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(return_value=DispatchResult(DispatchOutcome.NO_POSTING_FOUND)),
    )
    before = datetime.now(tz=UTC)
    await tick_user(user.id, deps=deps)
    _, when = schedule_at.call_args.args
    delta = (when - before).total_seconds()
    assert 1700 < delta < 1900  # ~30 min default backoff


@pytest.mark.asyncio
async def test_user_not_ready_does_not_reschedule(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)
    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(return_value=DispatchResult(DispatchOutcome.USER_NOT_READY)),
    )
    await tick_user(user.id, deps=deps)
    assert schedule_at.call_count == 0


@pytest.mark.asyncio
async def test_unhandled_crash_is_swallowed_and_reschedules(
    settings, db_session, redis, mocker
):
    user = await _seed_user(db_session)
    schedule_at = AsyncMock()
    deps = _build_deps(settings, db_session, redis, schedule_at=schedule_at)
    mocker.patch(
        "jyry.jobs.dispatch_tick.dispatch_one",
        AsyncMock(side_effect=RuntimeError("boom")),
    )
    result = await tick_user(user.id, deps=deps)
    assert result.outcome is DispatchOutcome.TRANSIENT_FAILURE
    assert result.detail == "tick crashed"
    assert schedule_at.call_count == 1
