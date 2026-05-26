"""Status, pause, resume and test-send callback handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from jyry.bot import keyboards, messages, repos
from jyry.config import get_settings
from jyry.services.send_pending import send_test_email

logger = logging.getLogger(__name__)


async def cb_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    limiter = context.bot_data["limiter"]
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        summary = await repos.status_summary(session, limiter, user.id)
    text = messages.STATUS_TEMPLATE.format(
        plan=summary.plan.capitalize(),
        daily_quota=summary.daily_quota,
        sent_today=summary.sent_today,
        remaining=summary.remaining_today,
        total_sent=summary.total_sent,
        state=messages.STATUS_STATE_ACTIVE if summary.is_active else messages.STATUS_STATE_PAUSED,
    )
    await query.edit_message_text(
        text,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )


async def cb_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        await repos.set_active(session, user.id, is_active=False)
    scheduler = context.bot_data.get("scheduler")
    if scheduler is not None:
        scheduler.deactivate_user(user.id)
    await query.edit_message_text(
        messages.PAUSED_NOTICE,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )


async def cb_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        await repos.set_active(session, user.id, is_active=True)
    scheduler = context.bot_data.get("scheduler")
    if scheduler is not None:
        await scheduler.activate_user(user.id)
    await query.edit_message_text(
        messages.RESUMED_NOTICE,
        reply_markup=keyboards.back_to_main_only(),
    )


async def _set_notifications(
    update: Update, context: ContextTypes.DEFAULT_TYPE, *, enabled: bool
) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        await repos.set_notifications_enabled(session, user.id, enabled=enabled)
        full = await repos.load_user(session, user.id)
    confirm = (
        messages.NOTIFICATIONS_ENABLED_CONFIRM
        if enabled
        else messages.NOTIFICATIONS_DISABLED_CONFIRM
    )
    if full and full.onboarding_complete:
        await query.edit_message_text(
            confirm + "\n\n" + messages.MAIN_MENU_TITLE,
            reply_markup=keyboards.main_menu(
                is_active=full.is_active,
                show_templates=repos.can_use_templates(full),
                notifications_enabled=enabled,
            ),
        )
    else:
        await query.edit_message_text(
            confirm,
            reply_markup=keyboards.back_to_main_only(),
        )


async def cb_notifications_enable(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await _set_notifications(update, context, enabled=True)


async def cb_notifications_disable(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    await _set_notifications(update, context, enabled=False)


async def cb_notifications_toggle(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
    current = bool(full and full.notifications_enabled)
    await _set_notifications(update, context, enabled=not current)


async def cb_send_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send 5 test emails back-to-back — bypasses BA and quota."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()
    tg_id = update.effective_user.id
    settings = get_settings()
    fetcher = context.bot_data["attachment_fetcher"]
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        if not user.onboarding_complete:
            await query.edit_message_text(
                messages.TEST_EMAIL_NOT_READY,
                reply_markup=keyboards.back_to_main_only(),
                parse_mode="Markdown",
            )
            return
        gmail_address = user.gmail_address or ""

    # Acknowledge first so the chat shows progress, then fan-out the burst.
    await query.edit_message_text(
        messages.TEST_EMAIL_STARTING,
        reply_markup=None,
        parse_mode="Markdown",
    )

    async with context.bot_data["session_scope"]() as session:
        sent, failure = await send_test_email(
            user_id=user.id,
            settings=settings,
            session=session,
            fetcher=fetcher,
        )

    target = settings.test_redirect_email or gmail_address
    if sent and failure is None:
        text = messages.TEST_EMAIL_SENT.format(to=target, count=sent)
    elif sent and failure is not None:
        text = messages.TEST_EMAIL_PARTIAL.format(
            sent=sent, to=target, detail=failure.detail or "unbekannt"
        )
    else:
        detail = failure.detail if failure else "unbekannt"
        text = messages.TEST_EMAIL_FAILED.format(detail=detail)

    await query.edit_message_text(
        text,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
