"""Tests for jyry.services.scheduler.JyryScheduler."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

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
