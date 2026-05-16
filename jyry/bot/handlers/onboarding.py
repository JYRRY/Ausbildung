"""Linear onboarding ConversationHandler — 9 steps with Zurück on every step.

State flow (happy path):
  entry(cb_loslegen) → ASK_NAME → ASK_GMAIL_CONSENT → ASK_GMAIL_ADDRESS
  → ASK_APP_PASSWORD → ASK_SPECIALTIES → ASK_STATES → ASK_EMAIL_SUBJECT
  → ASK_EMAIL_BODY → ASK_ATTACHMENTS → CONFIRM → END
"""
from __future__ import annotations

from contextlib import suppress
from typing import Any

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from jyry.bot import keyboards, messages, repos
from jyry.bot.states import OnboardingState

S = OnboardingState


# ---------------------------------------------------------------------------
# Entry — called from start.cb_loslegen / plans.cb_plan_free; returns the
# first state so the ConversationHandler can take over.
# ---------------------------------------------------------------------------

async def enter_onboarding(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """Show ASK_NAME and open conversation (called when sub exists, no onboarding)."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        context.user_data["user_id"] = user.id
    await query.answer()
    await query.edit_message_text(
        messages.ASK_NAME, reply_markup=keyboards.back_only(allow_forward=True)
    )
    return S.ASK_NAME


# ---------------------------------------------------------------------------
# ASK_NAME
# ---------------------------------------------------------------------------

async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    assert update.message and context.user_data is not None
    name = (update.message.text or "").strip()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.set_full_name(session, user_id, name)
    await update.message.reply_text(
        messages.CONSENT_WARNING,
        reply_markup=keyboards.consent_keyboard(),
        parse_mode="Markdown",
    )
    return S.ASK_GMAIL_CONSENT


async def back_from_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(messages.WELCOME, reply_markup=keyboards.welcome_menu())
    return ConversationHandler.END


async def forward_from_name(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Skip the name step if the user already has one saved."""
    query = update.callback_query
    assert query is not None and context.user_data is not None
    user_id: int | None = context.user_data.get("user_id")
    has_name = False
    if user_id is not None:
        async with context.bot_data["session_scope"]() as session:
            user = await repos.load_user(session, user_id)
        has_name = bool(user and user.full_name)
    if not has_name:
        await query.answer(messages.FORWARD_FIELD_EMPTY, show_alert=True)
        return S.ASK_NAME
    await query.answer()
    await query.edit_message_text(
        messages.CONSENT_WARNING,
        reply_markup=keyboards.consent_keyboard(),
        parse_mode="Markdown",
    )
    return S.ASK_GMAIL_CONSENT


# ---------------------------------------------------------------------------
# ASK_GMAIL_CONSENT
# ---------------------------------------------------------------------------

async def handle_consent_accept(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.ASK_GMAIL_ADDRESS,
        reply_markup=keyboards.back_only(allow_forward=True),
    )
    return S.ASK_GMAIL_ADDRESS


async def handle_consent_decline(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(messages.WELCOME, reply_markup=keyboards.welcome_menu())
    return ConversationHandler.END


async def back_from_consent(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.ASK_NAME, reply_markup=keyboards.back_only(allow_forward=True)
    )
    return S.ASK_NAME


# ---------------------------------------------------------------------------
# ASK_GMAIL_ADDRESS
# ---------------------------------------------------------------------------

async def handle_gmail_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message and context.user_data is not None
    address = (update.message.text or "").strip().lower()
    if "@" not in address or "." not in address.split("@")[-1]:
        await update.message.reply_text(
            messages.INVALID_EMAIL, reply_markup=keyboards.back_only()
        )
        return S.ASK_GMAIL_ADDRESS
    context.user_data["pending_gmail"] = address
    user_id: int | None = context.user_data.get("user_id")
    if user_id is not None:
        async with context.bot_data["session_scope"]() as session:
            await repos.set_gmail_address(session, user_id, address)
    has_existing = await _has_existing_app_password(context, address)
    await update.message.reply_text(
        messages.APP_PASSWORD_INSTRUCTIONS,
        reply_markup=keyboards.app_password_keyboard(has_existing=has_existing),
        parse_mode="Markdown",
    )
    return S.ASK_APP_PASSWORD


async def _has_existing_app_password(
    context: ContextTypes.DEFAULT_TYPE, gmail_address: str
) -> bool:
    """True only if the same Gmail address already has a saved app password."""
    assert context.user_data is not None
    user_id: int | None = context.user_data.get("user_id")
    if user_id is None:
        return False
    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    if user is None or user.gmail_app_password_enc is None:
        return False
    return (user.gmail_address or "").lower() == gmail_address


async def forward_from_gmail_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Skip Gmail address step if one is already saved — reuse it as pending."""
    query = update.callback_query
    assert query is not None and context.user_data is not None
    user_id: int | None = context.user_data.get("user_id")
    saved = ""
    if user_id is not None:
        async with context.bot_data["session_scope"]() as session:
            user = await repos.load_user(session, user_id)
        saved = (user.gmail_address or "") if user else ""
    if not saved:
        await query.answer(messages.FORWARD_FIELD_EMPTY, show_alert=True)
        return S.ASK_GMAIL_ADDRESS
    await query.answer()
    context.user_data["pending_gmail"] = saved.lower()
    has_existing = await _has_existing_app_password(context, saved.lower())
    await query.edit_message_text(
        messages.APP_PASSWORD_INSTRUCTIONS,
        reply_markup=keyboards.app_password_keyboard(has_existing=has_existing),
        parse_mode="Markdown",
    )
    return S.ASK_APP_PASSWORD


async def back_from_gmail_address(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.CONSENT_WARNING,
        reply_markup=keyboards.consent_keyboard(),
        parse_mode="Markdown",
    )
    return S.ASK_GMAIL_CONSENT


# ---------------------------------------------------------------------------
# ASK_APP_PASSWORD
# ---------------------------------------------------------------------------

async def handle_app_password(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message and context.user_data is not None
    raw = (update.message.text or "").strip()
    password = raw.replace(" ", "")

    with suppress(Exception):
        await update.message.delete()

    if len(password) != 16:
        await update.message.reply_text(
            messages.APP_PASSWORD_INVALID_LENGTH,
            reply_markup=keyboards.back_only(),
            parse_mode="Markdown",
        )
        return S.ASK_APP_PASSWORD

    user_id: int = context.user_data["user_id"]
    gmail = context.user_data.get("pending_gmail", "")
    async with context.bot_data["session_scope"]() as session:
        await repos.set_gmail(
            session, user_id, address=gmail, app_password_plaintext=password
        )

    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    picked = {s.specialty_keyword for s in (user.specialties if user else [])}
    context.user_data["pending_specialties"] = picked

    await update.message.reply_text(
        messages.APP_PASSWORD_SAVED + "\n\n" + messages.ASK_SPECIALTIES_NO_CAP,
        reply_markup=keyboards.specialties_keyboard(picked),
    )
    return S.ASK_SPECIALTIES


async def back_from_app_password(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.ASK_GMAIL_ADDRESS,
        reply_markup=keyboards.back_only(allow_forward=True),
    )
    return S.ASK_GMAIL_ADDRESS


# ---------------------------------------------------------------------------
# ASK_SPECIALTIES
# ---------------------------------------------------------------------------

async def handle_specialty_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    keyword = (query.data or "").removeprefix("cb:sp:")
    picked: set[str] = set(context.user_data.get("pending_specialties") or set())
    if keyword in picked:
        picked.discard(keyword)
    else:
        picked.add(keyword)
    context.user_data["pending_specialties"] = picked
    await query.edit_message_reply_markup(keyboards.specialties_keyboard(picked))
    return S.ASK_SPECIALTIES


async def handle_specialties_done(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    picked: set[str] = set(context.user_data.get("pending_specialties") or set())
    if not picked:
        await query.answer(messages.SPECIALTIES_NEED_AT_LEAST_ONE, show_alert=True)
        return S.ASK_SPECIALTIES
    await query.answer()

    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.replace_specialties(session, user_id, list(picked))

    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    picked_states = {s.state_code for s in (user.states if user else [])}
    context.user_data["pending_states"] = picked_states

    await query.edit_message_text(
        messages.ASK_STATES_NO_CAP,
        reply_markup=keyboards.states_keyboard(picked_states),
    )
    return S.ASK_STATES


async def back_from_specialties(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    pending_gmail = context.user_data.get("pending_gmail", "")
    has_existing = (
        await _has_existing_app_password(context, pending_gmail)
        if pending_gmail
        else False
    )
    await query.edit_message_text(
        messages.APP_PASSWORD_INSTRUCTIONS,
        reply_markup=keyboards.app_password_keyboard(has_existing=has_existing),
        parse_mode="Markdown",
    )
    return S.ASK_APP_PASSWORD


async def handle_app_password_skip(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """User reuses the previously stored app password — skip the input step."""
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    picked = {s.specialty_keyword for s in (user.specialties if user else [])}
    context.user_data["pending_specialties"] = picked
    await query.edit_message_text(
        messages.APP_PASSWORD_SKIPPED_NOTICE
        + "\n\n"
        + messages.ASK_SPECIALTIES_NO_CAP,
        reply_markup=keyboards.specialties_keyboard(picked),
    )
    return S.ASK_SPECIALTIES


# ---------------------------------------------------------------------------
# ASK_STATES
# ---------------------------------------------------------------------------

async def handle_state_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    code = (query.data or "").removeprefix("cb:st:")
    picked: set[str] = set(context.user_data.get("pending_states") or set())
    if code in picked:
        picked.discard(code)
    else:
        picked.add(code)
    context.user_data["pending_states"] = picked
    await query.edit_message_reply_markup(keyboards.states_keyboard(picked))
    return S.ASK_STATES


async def handle_states_done(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    picked: set[str] = set(context.user_data.get("pending_states") or set())
    if not picked:
        await query.answer(messages.STATES_NEED_AT_LEAST_ONE, show_alert=True)
        return S.ASK_STATES
    await query.answer()

    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.replace_states(session, user_id, list(picked))

    await query.edit_message_text(
        messages.ASK_EMAIL_SUBJECT,
        reply_markup=keyboards.back_only(allow_forward=True),
        parse_mode="Markdown",
    )
    return S.ASK_EMAIL_SUBJECT


async def back_from_states(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    picked = set(context.user_data.get("pending_specialties") or set())
    await query.edit_message_text(
        messages.ASK_SPECIALTIES_NO_CAP,
        reply_markup=keyboards.specialties_keyboard(picked),
    )
    return S.ASK_SPECIALTIES


# ---------------------------------------------------------------------------
# ASK_EMAIL_SUBJECT
# ---------------------------------------------------------------------------

async def handle_email_subject(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message and context.user_data is not None
    subject = (update.message.text or "").strip()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.upsert_draft(session, user_id, subject_template=subject)
    await update.message.reply_text(
        messages.ASK_EMAIL_BODY,
        reply_markup=keyboards.back_only(allow_forward=True),
        parse_mode="Markdown",
    )
    return S.ASK_EMAIL_BODY


async def back_from_email_subject(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    picked = set(context.user_data.get("pending_states") or set())
    await query.edit_message_text(
        messages.ASK_STATES_NO_CAP,
        reply_markup=keyboards.states_keyboard(picked),
    )
    return S.ASK_STATES


async def forward_from_email_subject(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Skip subject step if a saved draft already has one."""
    query = update.callback_query
    assert query is not None and context.user_data is not None
    user_id: int | None = context.user_data.get("user_id")
    has_subject = False
    if user_id is not None:
        async with context.bot_data["session_scope"]() as session:
            user = await repos.load_user(session, user_id)
        has_subject = bool(
            user and user.email_draft and user.email_draft.subject_template
        )
    if not has_subject:
        await query.answer(messages.FORWARD_FIELD_EMPTY, show_alert=True)
        return S.ASK_EMAIL_SUBJECT
    await query.answer()
    await query.edit_message_text(
        messages.ASK_EMAIL_BODY,
        reply_markup=keyboards.back_only(allow_forward=True),
        parse_mode="Markdown",
    )
    return S.ASK_EMAIL_BODY


# ---------------------------------------------------------------------------
# ASK_EMAIL_BODY
# ---------------------------------------------------------------------------

async def handle_email_body(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message and context.user_data is not None
    body = (update.message.text or "").strip()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.upsert_draft(session, user_id, body_template=body)

    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    attachments = (
        (user.email_draft.attachments_meta if user and user.email_draft else None) or []
    )
    await update.message.reply_text(
        messages.ASK_ATTACHMENTS,
        reply_markup=keyboards.attachments_keyboard(attachments),
        parse_mode="Markdown",
    )
    return S.ASK_ATTACHMENTS


async def back_from_email_body(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    await query.edit_message_text(
        messages.ASK_EMAIL_SUBJECT,
        reply_markup=keyboards.back_only(allow_forward=True),
        parse_mode="Markdown",
    )
    return S.ASK_EMAIL_SUBJECT


async def forward_from_email_body(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Skip body step if a saved draft already has one."""
    query = update.callback_query
    assert query is not None and context.user_data is not None
    user_id: int | None = context.user_data.get("user_id")
    has_body = False
    metas: list[dict[str, Any]] = []
    if user_id is not None:
        async with context.bot_data["session_scope"]() as session:
            user = await repos.load_user(session, user_id)
        if user and user.email_draft:
            has_body = bool(user.email_draft.body_template)
            metas = user.email_draft.attachments_meta or []
    if not has_body:
        await query.answer(messages.FORWARD_FIELD_EMPTY, show_alert=True)
        return S.ASK_EMAIL_BODY
    await query.answer()
    await query.edit_message_text(
        messages.ASK_ATTACHMENTS,
        reply_markup=keyboards.attachments_keyboard(metas),
        parse_mode="Markdown",
    )
    return S.ASK_ATTACHMENTS


# ---------------------------------------------------------------------------
# ASK_ATTACHMENTS
# ---------------------------------------------------------------------------

_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024  # 10 MB


async def handle_attachment(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    assert update.message and update.message.document and context.user_data is not None
    doc = update.message.document

    if doc.mime_type != "application/pdf":
        await update.message.reply_text(messages.ATTACHMENT_REJECTED_TYPE)
        return S.ASK_ATTACHMENTS
    if (doc.file_size or 0) > _MAX_ATTACHMENT_BYTES:
        await update.message.reply_text(messages.ATTACHMENT_REJECTED_SIZE)
        return S.ASK_ATTACHMENTS

    user_id: int = context.user_data["user_id"]
    filename = doc.file_name or "attachment.pdf"
    async with context.bot_data["session_scope"]() as session:
        draft = await repos.append_attachment(
            session,
            user_id,
            filename=filename,
            file_id=doc.file_id,
            mime=doc.mime_type or "application/pdf",
            size=doc.file_size or 0,
        )
    await update.message.reply_text(
        messages.ATTACHMENT_SAVED.format(
            filename=filename,
            size_kb=round((doc.file_size or 0) / 1024),
        ),
        reply_markup=keyboards.attachments_keyboard(draft.attachments_meta or []),
        parse_mode="Markdown",
    )
    return S.ASK_ATTACHMENTS


async def handle_attachment_remove(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    raw = (query.data or "").removeprefix("cb:rm:")
    try:
        idx = int(raw)
    except ValueError:
        return S.ASK_ATTACHMENTS
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        draft = await repos.remove_attachment_at(session, user_id, idx)
    await query.edit_message_reply_markup(
        keyboards.attachments_keyboard(draft.attachments_meta or [])
    )
    return S.ASK_ATTACHMENTS


async def handle_attachments_done(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    metas = (
        (user.email_draft.attachments_meta if user and user.email_draft else None) or []
    )
    if not metas:
        await query.answer(messages.ATTACHMENTS_NEED_AT_LEAST_ONE, show_alert=True)
        return S.ASK_ATTACHMENTS
    await query.answer()
    await query.edit_message_text(
        messages.CONFIRM_PROMPT,
        reply_markup=keyboards.confirm_keyboard(),
        parse_mode="Markdown",
    )
    return S.CONFIRM


async def back_from_attachments(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.ASK_EMAIL_BODY,
        reply_markup=keyboards.back_only(allow_forward=True),
        parse_mode="Markdown",
    )
    return S.ASK_EMAIL_BODY


# ---------------------------------------------------------------------------
# CONFIRM
# ---------------------------------------------------------------------------

async def handle_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        await repos.mark_onboarded(session, user_id)
    scheduler = context.bot_data.get("scheduler")
    if scheduler is not None:
        await scheduler.activate_user(user_id)
    await query.edit_message_text(
        messages.ONBOARDING_DONE,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
    return ConversationHandler.END


async def back_from_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    query = update.callback_query
    assert query is not None and context.user_data is not None
    await query.answer()
    user_id: int = context.user_data["user_id"]
    async with context.bot_data["session_scope"]() as session:
        user = await repos.load_user(session, user_id)
    metas = (
        (user.email_draft.attachments_meta if user and user.email_draft else None) or []
    )
    await query.edit_message_text(
        messages.ASK_ATTACHMENTS,
        reply_markup=keyboards.attachments_keyboard(metas),
        parse_mode="Markdown",
    )
    return S.ASK_ATTACHMENTS
