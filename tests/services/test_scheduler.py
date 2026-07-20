"""Tests for jyry.services.scheduler.JyryScheduler."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from jyry.db.enums import Language
from jyry.db.models import User
from jyry.services.scheduler import JyryScheduler, job_id_for


def _deps_factory():
    return MagicMock(name="deps")


@pytest.fixture
def scheduler(settings):
    return JyryScheduler(settings, deps_factory=_deps_factory)


@pytest.mark.asyncio
async def test_start_and_stop_are_idempotent(scheduler):
    await scheduler.start()
    await scheduler.start()
    await scheduler.stop()
    await scheduler.stop()


@pytest.mark.asyncio
async def test_activate_user_adds_job_under_canonical_id(scheduler):
    await scheduler.start()
    try:
        await scheduler.activate_user(user_id=42)
        await asyncio.sleep(0)
        assert scheduler._scheduler.get_job(job_id_for(42)) is not None
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_schedule_at_replaces_existing_job(scheduler):
    await scheduler.start()
    try:
        when_a = datetime.now(tz=UTC) + timedelta(hours=1)
        when_b = datetime.now(tz=UTC) + timedelta(hours=2)
        await scheduler.schedule_at(7, when_a)
        await scheduler.schedule_at(7, when_b)
        # Single job remains (idempotent re-schedule).
        jobs = [j for j in scheduler._scheduler.get_jobs() if j.id == job_id_for(7)]
        assert len(jobs) == 1
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_deactivate_user_removes_job(scheduler):
    await scheduler.start()
    try:
        await scheduler.activate_user(user_id=11)
        await scheduler.deactivate_user(user_id=11)
        assert scheduler._scheduler.get_job(job_id_for(11)) is None
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_deactivate_missing_user_is_a_no_op(scheduler):
    await scheduler.start()
    try:
        await scheduler.deactivate_user(user_id=99999)  # never scheduled
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_sweep_active_users_skips_unfinished_onboarding(
    scheduler, db_session
):
    # Three users: ready, not-onboarded, deactivated.
    db_session.add_all(
        [
            User(
                telegram_id=1,
                language=Language.AR,
                is_active=True,
                onboarding_complete=True,
            ),
            User(
                telegram_id=2,
                language=Language.AR,
                is_active=True,
                onboarding_complete=False,
            ),
            User(
                telegram_id=3,
                language=Language.AR,
                is_active=False,
                onboarding_complete=True,
            ),
        ]
    )
    await db_session.commit()

    await scheduler.start()
    try:
        scheduled = await scheduler.sweep_active_users(db_session)
    finally:
        await scheduler.stop()
    assert scheduled == 1


@pytest.mark.asyncio
async def test_sweep_only_missing_leaves_already_scheduled_users_untouched(
    scheduler, db_session
):
    # Two ready users; one already has a paced tick far in the future.
    db_session.add_all(
        [
            User(telegram_id=1, language=Language.AR, is_active=True, onboarding_complete=True),
            User(telegram_id=2, language=Language.AR, is_active=True, onboarding_complete=True),
        ]
    )
    await db_session.commit()
    ids = list(
        (await db_session.execute(select(User.id))).scalars()
    )
    first, second = ids

    await scheduler.start()
    try:
        # `first` is already scheduled for +1h (simulating quota pacing).
        far = datetime.now(tz=UTC) + timedelta(hours=1)
        await scheduler.schedule_at(first, far)
        before = scheduler._scheduler.get_job(job_id_for(first)).next_run_time

        scheduled = await scheduler.sweep_active_users(db_session, only_missing=True)

        # Only the un-scheduled user got a tick; the paced one is untouched.
        assert scheduled == 1
        after = scheduler._scheduler.get_job(job_id_for(first)).next_run_time
        assert after == before
        assert scheduler.has_job(second) is True
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_add_resweep_job_registers_interval_job(scheduler):
    await scheduler.start()
    try:
        @asynccontextmanager
        async def _scope():
            yield None  # not exercised here

        scheduler.add_resweep_job(session_scope=_scope, interval_seconds=120)
        assert scheduler._scheduler.get_job("resweep_active_users") is not None
    finally:
        await scheduler.stop()


@pytest.mark.asyncio
async def test_run_resweep_schedules_newly_active_user(scheduler, db_session):
    db_session.add(
        User(telegram_id=1, language=Language.AR, is_active=True, onboarding_complete=True)
    )
    await db_session.commit()
    user_id = (
        await db_session.execute(select(User.id))
    ).scalar_one()

    @asynccontextmanager
    async def _scope():
        yield db_session

    await scheduler.start()
    try:
        assert scheduler.has_job(user_id) is False
        await scheduler._run_resweep(session_scope=_scope)
        assert scheduler.has_job(user_id) is True
    finally:
        await scheduler.stop()
