"""Edit-field entry points — re-enter onboarding states from the main menu.

Each handler loads the user's current value, then drops into the corresponding
onboarding state so the same handler logic handles the reply.
"""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from jyry.bot import keyboards, messages, repos
from jyry.bot.states import OnboardingState


async def cb_edit_body(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        context.user_data["user_id"] = user.id
    await query.edit_message_text(
        messages.ASK_EMAIL_SUBJECT,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
    return OnboardingState.ASK_EMAIL_SUBJECT


async def cb_edit_attachments(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        context.user_data["user_id"] = user.id
    attachments = (
        (full.email_draft.attachments_meta if full and full.email_draft else None) or []
    )
    await query.edit_message_text(
        messages.ASK_ATTACHMENTS,
        reply_markup=keyboards.attachments_keyboard(attachments),
        parse_mode="Markdown",
    )
    return OnboardingState.ASK_ATTACHMENTS


async def cb_edit_specialties(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        context.user_data["user_id"] = user.id
    picked = {s.specialty_keyword for s in (full.specialties if full else [])}
    context.user_data["pending_specialties"] = picked
    await query.edit_message_text(
        messages.ASK_SPECIALTIES_NO_CAP,
        reply_markup=keyboards.specialties_keyboard(picked),
    )
    return OnboardingState.ASK_SPECIALTIES


async def cb_edit_states(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        context.user_data["user_id"] = user.id
    picked = {s.state_code for s in (full.states if full else [])}
    context.user_data["pending_states"] = picked
    await query.edit_message_text(
        messages.ASK_STATES_NO_CAP,
        reply_markup=keyboards.states_keyboard(picked),
    )
    return OnboardingState.ASK_STATES
