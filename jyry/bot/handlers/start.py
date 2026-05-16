"""Top-level /start handler and menu-routing callbacks."""
from __future__ import annotations

from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from jyry.bot import keyboards, messages, repos
from jyry.bot.states import OnboardingState
from jyry.services.crypto import decrypt_secret


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    assert update.effective_user and update.message
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    if full and full.onboarding_complete and repos.has_active_subscription(full):
        await update.message.reply_text(
            messages.MAIN_MENU_TITLE,
            reply_markup=keyboards.main_menu(
                is_active=full.is_active,
                show_templates=repos.can_use_templates(full),
            ),
        )
        return

    # Returning user with saved partial progress — acknowledge stored data
    # so they don't feel they need to restart from scratch.
    if full and _has_partial_progress(full):
        progress = _format_progress(full)
        name_suffix = f", {_md_escape(full.full_name)}" if full.full_name else ""
        await update.message.reply_text(
            messages.WELCOME_BACK.format(name_suffix=name_suffix, progress=progress),
            reply_markup=keyboards.welcome_menu(),
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(messages.WELCOME, reply_markup=keyboards.welcome_menu())


_MD_SPECIAL = "_*[`"


def _md_escape(text: str) -> str:
    """Escape Telegram Markdown (v1) reserved chars to avoid silent send failures."""
    return "".join("\\" + c if c in _MD_SPECIAL else c for c in text)


def _has_partial_progress(full: Any) -> bool:
    """True if the user has at least one onboarding field saved."""
    draft = full.email_draft
    return bool(
        full.full_name
        or full.gmail_address
        or full.gmail_app_password_enc
        or full.specialties
        or full.states
        or (draft and (draft.subject_template or draft.body_template))
        or (draft and (draft.attachments_meta or []))
    )


_SUBJECT_PREVIEW_MAX = 60


def _mask_app_password(enc: bytes) -> str:
    """Show the first 4 chars then 12 dots so the user can recognise which
    password is stored without exposing it fully."""
    try:
        plain = decrypt_secret(enc)
    except Exception:
        return "✅"
    if len(plain) < 4:
        return "✅"
    return _md_escape(plain[:4]) + "•" * 12


def _format_progress(full: Any) -> str:
    """Render a per-field checklist of what's already saved."""
    draft = full.email_draft
    attachments = (draft.attachments_meta if draft else None) or []

    name_line = (
        f"✅ Name: {_md_escape(full.full_name)}" if full.full_name else "⬜ Name:"
    )
    gmail_line = (
        f"✅ Gmail: {_md_escape(full.gmail_address)}"
        if full.gmail_address
        else "⬜ Gmail:"
    )
    pw_line = (
        f"✅ App-Passwort: {_mask_app_password(full.gmail_app_password_enc)}"
        if full.gmail_app_password_enc
        else "⬜ App-Passwort:"
    )
    if full.specialties:
        keywords = ", ".join(_md_escape(s.specialty_keyword) for s in full.specialties)
        berufe_line = f"✅ Berufe: {keywords}"
    else:
        berufe_line = "⬜ Berufe:"
    states_line = (
        f"✅ Bundesländer: {len(full.states)}" if full.states else "⬜ Bundesländer:"
    )
    if draft and draft.subject_template:
        subj = draft.subject_template.strip()
        if len(subj) > _SUBJECT_PREVIEW_MAX:
            subj = subj[: _SUBJECT_PREVIEW_MAX - 1].rstrip() + "…"
        subject_line = f"✅ Betreff: {_md_escape(subj)}"
    else:
        subject_line = "⬜ Betreff:"
    text_line = (
        "✅ Text: 1" if draft and draft.body_template else "⬜ Text:"
    )
    anhaenge_line = (
        f"✅ Anhänge: {len(attachments)}" if attachments else "⬜ Anhänge:"
    )

    return "\n".join(
        [
            name_line,
            gmail_line,
            pw_line,
            berufe_line,
            states_line,
            subject_line,
            text_line,
            anhaenge_line,
        ]
    )


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
        reply_markup=keyboards.main_menu(
            is_active=full.is_active,
            show_templates=repos.can_use_templates(full),
        ),
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
        reply_markup=keyboards.main_menu(
            is_active=full.is_active if full else True,
            show_templates=bool(full and repos.can_use_templates(full)),
        ),
    )
    return ConversationHandler.END
