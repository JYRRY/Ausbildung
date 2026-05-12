"""Forces every user to be a member of the configured Telegram channel.

Implemented as a low-priority ``TypeHandler`` (group ``-1``) that runs before
any other handler. If the user is not subscribed, the gate sends the
subscribe-prompt and stops further processing via
:class:`telegram.ext.ApplicationHandlerStop`. The bot must be admin in the
channel for ``get_chat_member`` to work for non-members.
"""
from __future__ import annotations

import logging

from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.error import BadRequest, Forbidden, TelegramError
from telegram.ext import ApplicationHandlerStop, ContextTypes

from jyry.bot import keyboards, messages
from jyry.bot.keyboards import CB

logger = logging.getLogger(__name__)

_MEMBER_STATUSES = {
    ChatMemberStatus.OWNER,
    ChatMemberStatus.ADMINISTRATOR,
    ChatMemberStatus.MEMBER,
    ChatMemberStatus.RESTRICTED,
}


async def _is_member(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    channel = context.bot_data.get("required_channel")
    if not channel:
        return True
    try:
        member = await context.bot.get_chat_member(channel, user_id)
    except (BadRequest, Forbidden, TelegramError) as exc:
        logger.warning("get_chat_member(%s, %s) failed: %s", channel, user_id, exc)
        return False
    return member.status in _MEMBER_STATUSES


async def gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Block every update until the user is a channel member."""
    user = update.effective_user
    if user is None:
        return
    channel = context.bot_data.get("required_channel")
    if not channel:
        return
    # Let the re-check callback through so the "I subscribed" button always works.
    if update.callback_query and update.callback_query.data == CB["channel_check"]:
        return
    if await _is_member(context, user.id):
        return
    kb = keyboards.subscribe_gate(channel)
    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                messages.SUBSCRIBE_REQUIRED, reply_markup=kb, parse_mode="Markdown"
            )
        except BadRequest:
            msg = update.callback_query.message
            if msg is not None and hasattr(msg, "reply_text"):
                await msg.reply_text(
                    messages.SUBSCRIBE_REQUIRED, reply_markup=kb, parse_mode="Markdown"
                )
    elif update.message:
        await update.message.reply_text(
            messages.SUBSCRIBE_REQUIRED, reply_markup=kb, parse_mode="Markdown"
        )
    raise ApplicationHandlerStop


async def cb_channel_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the 'I have subscribed' button click."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    channel = context.bot_data.get("required_channel")
    if not channel:
        return
    if await _is_member(context, update.effective_user.id):
        await query.edit_message_text(messages.SUBSCRIBE_SUCCESS)
    else:
        await query.edit_message_text(
            messages.SUBSCRIBE_STILL_NOT_MEMBER,
            reply_markup=keyboards.subscribe_gate(channel),
            parse_mode="Markdown",
        )
