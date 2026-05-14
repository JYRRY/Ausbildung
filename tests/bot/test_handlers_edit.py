"""Tests for jyry.bot.handlers.edit — re-entry into onboarding states."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from jyry.bot import messages, repos
from jyry.bot.handlers import edit as edit_handler
from jyry.bot.states import OnboardingState


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


@pytest.mark.asyncio
async def test_cb_edit_body_shows_ask_email_subject_first(db_session):
    update = _make_callback_update(tg_id=200)
    ctx = _make_context(db_session)

    result = await edit_handler.cb_edit_body(update, ctx)

    assert result == OnboardingState.ASK_EMAIL_SUBJECT
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_EMAIL_SUBJECT
    assert "user_id" in ctx.user_data


@pytest.mark.asyncio
async def test_cb_edit_attachments_shows_attachments_keyboard(db_session):
    update = _make_callback_update(tg_id=201)
    ctx = _make_context(db_session)

    result = await edit_handler.cb_edit_attachments(update, ctx)

    assert result == OnboardingState.ASK_ATTACHMENTS
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_ATTACHMENTS


@pytest.mark.asyncio
async def test_cb_edit_specialties_loads_current_picks(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=202)
    await repos.replace_specialties(db_session, user.id, ["Bäcker", "Koch"])

    update = _make_callback_update(tg_id=202)
    ctx = _make_context(db_session)

    result = await edit_handler.cb_edit_specialties(update, ctx)

    assert result == OnboardingState.ASK_SPECIALTIES
    assert ctx.user_data["pending_specialties"] == {"Bäcker", "Koch"}
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_SPECIALTIES_NO_CAP


@pytest.mark.asyncio
async def test_cb_edit_states_loads_current_picks(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=203)
    await repos.replace_states(db_session, user.id, ["BY", "NW"])

    update = _make_callback_update(tg_id=203)
    ctx = _make_context(db_session)

    result = await edit_handler.cb_edit_states(update, ctx)

    assert result == OnboardingState.ASK_STATES
    assert ctx.user_data["pending_states"] == {"BY", "NW"}
    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.ASK_STATES_NO_CAP
