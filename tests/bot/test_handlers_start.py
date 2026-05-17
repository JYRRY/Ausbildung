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


# --- upgrade / cancel flows ---

from pydantic import SecretStr  # noqa: E402

from jyry.bot.keyboards import CB  # noqa: E402
from jyry.config import Settings  # noqa: E402


def _ls_settings(**overrides) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.lemonsqueezy_api_key = SecretStr("k")
    s.lemonsqueezy_store_id = "store-1"
    s.lemonsqueezy_variant_plus = "var-plus"
    s.lemonsqueezy_variant_pro = "var-pro"
    s.lemonsqueezy_variant_max = "var-max"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


async def _add_paid_sub(session, user_id: int, plan: Plan, ls_sub_id: str) -> None:
    sub = Subscription(
        user_id=user_id,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        started_at=datetime.now(tz=UTC),
        expires_at=datetime.now(tz=UTC) + timedelta(days=30),
        daily_quota=30,
        emails_sent_today=0,
        lemonsqueezy_subscription_id=ls_sub_id,
        lemonsqueezy_customer_id="cust-1",
    )
    session.add(sub)
    await session.flush()


@pytest.mark.asyncio
async def test_cb_plans_for_plus_user_shows_active_title_and_upgrade_keyboard(
    db_session,
):
    user = await repos.get_or_create_user(db_session, telegram_id=200)
    await _add_paid_sub(db_session, user.id, Plan.PLUS, "ls-200")

    update = _make_callback_update(tg_id=200)
    ctx = _make_context(db_session)

    await start_handler.cb_plans(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "Plus" in text
    assert messages.PLANS_TITLE_ACTIVE.split("\n")[0].split("{")[0] in text
    kb = update.callback_query.edit_message_text.call_args[1]["reply_markup"]
    cbs = {b.callback_data for row in kb.inline_keyboard for b in row}
    assert CB["plan_pro"] in cbs
    assert CB["plan_max"] in cbs
    assert CB["plan_cancel"] in cbs
    assert CB["plan_plus"] not in cbs


@pytest.mark.asyncio
async def test_cb_plans_for_max_user_shows_already_max_message(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=201)
    await _add_paid_sub(db_session, user.id, Plan.MAX, "ls-201")

    update = _make_callback_update(tg_id=201)
    ctx = _make_context(db_session)

    await start_handler.cb_plans(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_ALREADY_MAX


@pytest.mark.asyncio
async def test_cb_plan_paid_for_plus_user_shows_upgrade_confirm_screen(
    db_session, monkeypatch
):
    from jyry.bot.handlers import plans as ph

    monkeypatch.setattr(ph, "get_settings", lambda: _ls_settings())

    user = await repos.get_or_create_user(db_session, telegram_id=210)
    await _add_paid_sub(db_session, user.id, Plan.PLUS, "ls-210")

    update = _make_callback_update(tg_id=210)
    update.callback_query.data = CB["plan_pro"]
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "Upgrade auf Pro" in text
    kb = update.callback_query.edit_message_text.call_args[1]["reply_markup"]
    cbs = {b.callback_data for row in kb.inline_keyboard for b in row}
    assert CB["plan_upgrade_confirm_pro"] in cbs


@pytest.mark.asyncio
async def test_cb_plan_upgrade_confirm_calls_ls_and_reports_success(
    db_session, monkeypatch
):
    from jyry.bot.handlers import plans as ph
    from jyry.payments import lemonsqueezy as ls

    monkeypatch.setattr(ph, "get_settings", lambda: _ls_settings())

    user = await repos.get_or_create_user(db_session, telegram_id=220)
    await _add_paid_sub(db_session, user.id, Plan.PLUS, "ls-220")

    patched = AsyncMock()
    monkeypatch.setattr(ls, "update_subscription_variant", patched)

    update = _make_callback_update(tg_id=220)
    update.callback_query.data = CB["plan_upgrade_confirm_pro"]
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_upgrade_confirm(update, ctx)

    patched.assert_awaited_once()
    kwargs = patched.call_args.kwargs
    assert kwargs["subscription_id"] == "ls-220"
    assert kwargs["variant_id"] == "var-pro"

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "Pro" in text and "erfolgreich" in text


@pytest.mark.asyncio
async def test_cb_plan_upgrade_confirm_reports_failure_on_api_error(
    db_session, monkeypatch
):
    from jyry.bot.handlers import plans as ph
    from jyry.payments import lemonsqueezy as ls

    monkeypatch.setattr(ph, "get_settings", lambda: _ls_settings())

    user = await repos.get_or_create_user(db_session, telegram_id=221)
    await _add_paid_sub(db_session, user.id, Plan.PLUS, "ls-221")

    async def _boom(*a, **kw):
        raise RuntimeError("ls down")

    monkeypatch.setattr(ls, "update_subscription_variant", _boom)

    update = _make_callback_update(tg_id=221)
    update.callback_query.data = CB["plan_upgrade_confirm_pro"]
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_upgrade_confirm(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_UPGRADE_FAILED


@pytest.mark.asyncio
async def test_cb_plan_cancel_shows_confirm_screen_with_end_of_period_notice(
    db_session,
):
    user = await repos.get_or_create_user(db_session, telegram_id=230)
    await _add_paid_sub(db_session, user.id, Plan.PRO, "ls-230")

    update = _make_callback_update(tg_id=230)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_cancel(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    # The promised message must explicitly mention both: auto-renewal stops
    # AND service continues until the paid period ends.
    assert "automatische Verlängerung" in text
    assert "Ende der bereits bezahlten Laufzeit" in text
    kb = update.callback_query.edit_message_text.call_args[1]["reply_markup"]
    cbs = {b.callback_data for row in kb.inline_keyboard for b in row}
    assert CB["plan_cancel_confirm"] in cbs


@pytest.mark.asyncio
async def test_cb_plan_cancel_confirm_calls_ls_and_reports_success(
    db_session, monkeypatch
):
    from jyry.bot.handlers import plans as ph
    from jyry.payments import lemonsqueezy as ls

    monkeypatch.setattr(ph, "get_settings", lambda: _ls_settings())

    user = await repos.get_or_create_user(db_session, telegram_id=240)
    await _add_paid_sub(db_session, user.id, Plan.PRO, "ls-240")

    patched = AsyncMock()
    monkeypatch.setattr(ls, "cancel_subscription", patched)

    update = _make_callback_update(tg_id=240)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_cancel_confirm(update, ctx)

    patched.assert_awaited_once()
    assert patched.call_args.kwargs["subscription_id"] == "ls-240"
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert "gekündigt" in text


@pytest.mark.asyncio
async def test_cb_plan_cancel_confirm_without_ls_id_reports_failure(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=241)
    # No LS sub linked.

    update = _make_callback_update(tg_id=241)
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_cancel_confirm(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CANCEL_FAILED
