"""Tests for jyry.bot.handlers.start and jyry.bot.handlers.plans."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from jyry.bot import messages, repos
from jyry.bot.handlers import plans as plans_handler
from jyry.bot.handlers import start as start_handler
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.models import Subscription

# --- Test helpers ---

def _make_message_update(tg_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    return update


def _make_callback_update(tg_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    return update


def _make_context(session) -> MagicMock:
    @asynccontextmanager
    async def _scope():
        yield session

    ctx = MagicMock()
    ctx.bot_data = {"session_scope": _scope}
    ctx.user_data = {}
    return ctx


async def _add_active_sub(session, user_id: int) -> Subscription:
    sub = Subscription(
        user_id=user_id,
        plan=Plan.FREE,
        status=SubscriptionStatus.ACTIVE,
        started_at=datetime.now(tz=UTC),
        expires_at=datetime.now(tz=UTC) + timedelta(days=3),
        daily_quota=5,
        emails_sent_today=0,
    )
    session.add(sub)
    await session.flush()
    return sub


# --- /start ---

@pytest.mark.asyncio
async def test_cmd_start_new_user_shows_welcome(db_session):
    update = _make_message_update(tg_id=10)
    ctx = _make_context(db_session)

    await start_handler.cmd_start(update, ctx)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.WELCOME


@pytest.mark.asyncio
async def test_cmd_start_onboarded_user_shows_main_menu(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=11)
    user.onboarding_complete = True
    user.is_active = True
    await _add_active_sub(db_session, user.id)

    update = _make_message_update(tg_id=11)
    ctx = _make_context(db_session)

    await start_handler.cmd_start(update, ctx)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.MAIN_MENU_TITLE


@pytest.mark.asyncio
async def test_cmd_start_onboarded_but_no_sub_shows_welcome(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=12)
    user.onboarding_complete = True
    await db_session.flush()

    update = _make_message_update(tg_id=12)
    ctx = _make_context(db_session)

    await start_handler.cmd_start(update, ctx)

    update.message.reply_text.assert_awaited_once()
    text = update.message.reply_text.call_args[0][0]
    assert text == messages.WELCOME


# --- cb_about ---

@pytest.mark.asyncio
async def test_cb_about_sends_about_text(db_session):
    update = _make_callback_update(tg_id=20)
    ctx = _make_context(db_session)

    await start_handler.cb_about(update, ctx)

    update.callback_query.answer.assert_awaited_once()
    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ABOUT


# --- cb_plans ---

@pytest.mark.asyncio
async def test_cb_plans_shows_plans_menu(db_session):
    update = _make_callback_update(tg_id=21)
    ctx = _make_context(db_session)

    await start_handler.cb_plans(update, ctx)

    update.callback_query.edit_message_text.assert_awaited_once()
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLANS_TITLE


# --- cb_loslegen ---

@pytest.mark.asyncio
async def test_cb_loslegen_no_sub_redirects_to_plans(db_session):
    update = _make_callback_update(tg_id=30)
    ctx = _make_context(db_session)

    await start_handler.cb_loslegen(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLANS_TITLE


@pytest.mark.asyncio
async def test_cb_loslegen_with_sub_and_onboarded_shows_main_menu(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=31)
    user.onboarding_complete = True
    user.is_active = True
    await _add_active_sub(db_session, user.id)

    update = _make_callback_update(tg_id=31)
    ctx = _make_context(db_session)

    await start_handler.cb_loslegen(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.MAIN_MENU_TITLE
    assert ctx.user_data["user_id"] == user.id


@pytest.mark.asyncio
async def test_cb_loslegen_with_sub_not_onboarded_shows_ask_name(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=32)
    await _add_active_sub(db_session, user.id)

    update = _make_callback_update(tg_id=32)
    ctx = _make_context(db_session)

    await start_handler.cb_loslegen(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_NAME
    assert ctx.user_data["user_id"] == user.id


# --- cb_back_to_main ---

@pytest.mark.asyncio
async def test_cb_back_to_main_shows_main_menu(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=40)
    user.is_active = True
    await db_session.flush()

    update = _make_callback_update(tg_id=40)
    ctx = _make_context(db_session)

    await start_handler.cb_back_to_main(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.MAIN_MENU_TITLE


# --- plan handlers ---

@pytest.mark.asyncio
async def test_cb_plan_free_grants_trial_and_shows_ask_name(db_session):
    update = _make_callback_update(tg_id=50)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_free(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert messages.PLAN_FREE_ACTIVATED in text
    assert messages.ASK_NAME in text
    assert "user_id" in ctx.user_data


@pytest.mark.asyncio
async def test_cb_plan_free_for_onboarded_user_shows_main_menu(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=51)
    user.onboarding_complete = True
    user.is_active = True
    await db_session.flush()

    update = _make_callback_update(tg_id=51)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_free(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert messages.PLAN_FREE_ACTIVATED in text
    assert messages.MAIN_MENU_TITLE in text


@pytest.mark.asyncio
async def test_cb_plan_paid_shows_checkout_placeholder(db_session):
    update = _make_callback_update(tg_id=60)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_PLACEHOLDER
