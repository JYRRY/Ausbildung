"""Tests for jyry.bot.channel_gate."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest
from telegram.ext import ApplicationHandlerStop

from jyry.bot import channel_gate, messages
from jyry.bot.keyboards import CB


def _make_context(
    channel: str | None = "@JYRYGROUP", member_status: str | None = None
) -> MagicMock:
    ctx = MagicMock()
    ctx.bot_data = {"required_channel": channel} if channel else {}
    ctx.bot = MagicMock()
    if member_status is None:
        ctx.bot.get_chat_member = AsyncMock(side_effect=BadRequest("user not found"))
    else:
        member = MagicMock()
        member.status = member_status
        ctx.bot.get_chat_member = AsyncMock(return_value=member)
    return ctx


def _make_message_update(tg_id: int = 1) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


def _make_callback_update(tg_id: int = 1, data: str = "cb:other") -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.message = None
    update.callback_query = MagicMock()
    update.callback_query.data = data
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.message = MagicMock()
    update.callback_query.message.reply_text = AsyncMock()
    return update


@pytest.mark.asyncio
async def test_gate_passes_when_no_channel_configured() -> None:
    ctx = _make_context(channel=None)
    update = _make_message_update()
    # Should not raise.
    await channel_gate.gate(update, ctx)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_gate_passes_when_user_is_member() -> None:
    ctx = _make_context(member_status=ChatMemberStatus.MEMBER)
    update = _make_message_update()
    await channel_gate.gate(update, ctx)
    update.message.reply_text.assert_not_called()


@pytest.mark.asyncio
async def test_gate_blocks_non_member_on_message() -> None:
    ctx = _make_context(member_status=ChatMemberStatus.LEFT)
    update = _make_message_update()
    with pytest.raises(ApplicationHandlerStop):
        await channel_gate.gate(update, ctx)
    update.message.reply_text.assert_called_once()
    args, kwargs = update.message.reply_text.call_args
    assert messages.SUBSCRIBE_REQUIRED in args[0]


@pytest.mark.asyncio
async def test_gate_blocks_when_get_chat_member_fails() -> None:
    ctx = _make_context(member_status=None)
    update = _make_message_update()
    with pytest.raises(ApplicationHandlerStop):
        await channel_gate.gate(update, ctx)
    update.message.reply_text.assert_called_once()


@pytest.mark.asyncio
async def test_gate_lets_channel_check_callback_through() -> None:
    ctx = _make_context(member_status=ChatMemberStatus.LEFT)
    update = _make_callback_update(data=CB["channel_check"])
    # Should not raise — the cb_channel_check handler will deal with it.
    await channel_gate.gate(update, ctx)
    update.callback_query.edit_message_text.assert_not_called()


@pytest.mark.asyncio
async def test_cb_channel_check_succeeds_when_now_subscribed() -> None:
    ctx = _make_context(member_status=ChatMemberStatus.MEMBER)
    update = _make_callback_update(data=CB["channel_check"])
    await channel_gate.cb_channel_check(update, ctx)
    update.callback_query.edit_message_text.assert_called_once()
    args, kwargs = update.callback_query.edit_message_text.call_args
    assert args[0] == messages.SUBSCRIBE_SUCCESS


@pytest.mark.asyncio
async def test_cb_channel_check_still_not_member() -> None:
    ctx = _make_context(member_status=ChatMemberStatus.LEFT)
    update = _make_callback_update(data=CB["channel_check"])
    await channel_gate.cb_channel_check(update, ctx)
    update.callback_query.edit_message_text.assert_called_once()
    args, kwargs = update.callback_query.edit_message_text.call_args
    assert args[0] == messages.SUBSCRIBE_STILL_NOT_MEMBER
