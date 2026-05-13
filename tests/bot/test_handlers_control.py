"""Tests for jyry.bot.handlers.control."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio

from jyry.bot import messages, repos
from jyry.bot.handlers import control as control_handler
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.models import Subscription
from jyry.services.rate_limiter import DailyQuotaLimiter


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture
async def limiter(redis, settings):
    return DailyQuotaLimiter(redis, settings)


def _make_callback_update(tg_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _make_context(session, limiter=None) -> MagicMock:
    @asynccontextmanager
    async def _scope():
        yield session

    ctx = MagicMock()
    ctx.bot_data = {"session_scope": _scope, "limiter": limiter, "scheduler": None}
    ctx.user_data = {}
    return ctx


@pytest.mark.asyncio
async def test_cb_status_shows_formatted_status(db_session, limiter):
    user = await repos.get_or_create_user(db_session, telegram_id=70)
    db_session.add(
        Subscription(
            user_id=user.id,
            plan=Plan.FREE,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(tz=UTC),
            expires_at=datetime.now(tz=UTC) + timedelta(days=3),
            daily_quota=5,
            emails_sent_today=0,
        )
    )
    await db_session.flush()

    update = _make_callback_update(tg_id=70)
    ctx = _make_context(db_session, limiter)

    await control_handler.cb_status(update, ctx)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "Free" in text
    assert "free" not in text  # plan name is capitalized
    assert "5" in text  # daily_quota


@pytest.mark.asyncio
async def test_cb_pause_sets_inactive(db_session, limiter):
    user = await repos.get_or_create_user(db_session, telegram_id=71)
    user.is_active = True
    await db_session.flush()

    update = _make_callback_update(tg_id=71)
    ctx = _make_context(db_session, limiter)

    await control_handler.cb_pause(update, ctx)

    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PAUSED_NOTICE

    # Verify DB state
    from sqlalchemy import select

    from jyry.db.models import User
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_cb_resume_sets_active(db_session, limiter):
    user = await repos.get_or_create_user(db_session, telegram_id=72)
    user.is_active = False
    await db_session.flush()

    update = _make_callback_update(tg_id=72)
    ctx = _make_context(db_session, limiter)

    await control_handler.cb_resume(update, ctx)

    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.RESUMED_NOTICE

    from sqlalchemy import select

    from jyry.db.models import User
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.is_active is True
