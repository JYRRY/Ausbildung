"""Top-level /start handler and menu-routing callbacks."""
from __future__ import annotations

from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from jyry.bot import keyboards, messages, repos
from jyry.bot.states import OnboardingState


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        if user.onboarding_complete:
            full = await repos.load_user(session, user.id)
            if full and repos.has_active_subscription(full):
                await update.message.reply_text(
                    messages.MAIN_MENU_TITLE,
                    reply_markup=keyboards.main_menu(is_active=full.is_active),
                )
                return
    await update.message.reply_text(messages.WELCOME, reply_markup=keyboards.welcome_menu())


async def cb_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.ABOUT,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )


async def cb_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(messages.PLANS_TITLE, reply_markup=keyboards.plans_menu())


async def cb_loslegen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """'Loslegen' button: gate on subscription then onboarding status."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    if not full or not repos.has_active_subscription(full):
        await query.edit_message_text(messages.PLANS_TITLE, reply_markup=keyboards.plans_menu())
        return ConversationHandler.END

    context.user_data["user_id"] = full.id
    if not full.onboarding_complete:
        return await _resume_onboarding(query, context, full)

    await query.edit_message_text(
        messages.MAIN_MENU_TITLE,
        reply_markup=keyboards.main_menu(is_active=full.is_active),
    )
    return ConversationHandler.END


async def _resume_onboarding(
    query: Any,
    context: ContextTypes.DEFAULT_TYPE,
    full: Any,
) -> int:
    """Jump straight to the first unfilled onboarding step.

    Avoids forcing returning users to retype name + Gmail + every step on
    every restart. Already-filled fields stay in DB untouched; the user
    can still edit any of them later via the main-menu edit entries.
    """
    assert context.user_data is not None
    user_data = context.user_data
    if not full.full_name:
        await query.edit_message_text(
            messages.ASK_NAME,
            reply_markup=keyboards.back_only(allow_forward=True),
        )
        return OnboardingState.ASK_NAME

    if not full.gmail_address:
        await query.edit_message_text(
            messages.CONSENT_WARNING,
            reply_markup=keyboards.consent_keyboard(),
            parse_mode="Markdown",
        )
        return OnboardingState.ASK_GMAIL_CONSENT

    if not full.gmail_app_password_enc:
        user_data["pending_gmail"] = (full.gmail_address or "").lower()
        await query.edit_message_text(
            messages.APP_PASSWORD_INSTRUCTIONS,
            reply_markup=keyboards.app_password_keyboard(has_existing=False),
            parse_mode="Markdown",
        )
        return OnboardingState.ASK_APP_PASSWORD

    if not full.specialties:
        picked: set[str] = set()
        user_data["pending_specialties"] = picked
        await query.edit_message_text(
            messages.ASK_SPECIALTIES_NO_CAP,
            reply_markup=keyboards.specialties_keyboard(picked),
        )
        return OnboardingState.ASK_SPECIALTIES

    if not full.states:
        picked_states: set[str] = set()
        user_data["pending_states"] = picked_states
        await query.edit_message_text(
            messages.ASK_STATES_NO_CAP,
            reply_markup=keyboards.states_keyboard(picked_states),
        )
        return OnboardingState.ASK_STATES

    draft = full.email_draft
    if draft is None or not draft.subject_template:
        await query.edit_message_text(
            messages.ASK_EMAIL_SUBJECT,
            reply_markup=keyboards.back_only(allow_forward=True),
            parse_mode="Markdown",
        )
        return OnboardingState.ASK_EMAIL_SUBJECT

    if not draft.body_template:
        await query.edit_message_text(
            messages.ASK_EMAIL_BODY,
            reply_markup=keyboards.back_only(allow_forward=True),
            parse_mode="Markdown",
        )
        return OnboardingState.ASK_EMAIL_BODY

    metas = draft.attachments_meta or []
    if not metas:
        await query.edit_message_text(
            messages.ASK_ATTACHMENTS,
            reply_markup=keyboards.attachments_keyboard(metas),
            parse_mode="Markdown",
        )
        return OnboardingState.ASK_ATTACHMENTS

    # Everything is filled — jump straight to the final confirm screen.
    await query.edit_message_text(
        messages.CONFIRM_PROMPT,
        reply_markup=keyboards.confirm_keyboard(),
        parse_mode="Markdown",
    )
    return OnboardingState.CONFIRM


async def cb_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Return to the main menu. Wired both as a top-level callback and as a
    ConversationHandler fallback, so it cleanly exits any in-progress
    onboarding/edit flow when the user taps 🏠 Menü."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
    await query.edit_message_text(
        messages.MAIN_MENU_TITLE,
        reply_markup=keyboards.main_menu(is_active=full.is_active if full else True),
    )
    return ConversationHandler.END
