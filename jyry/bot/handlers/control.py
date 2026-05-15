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


async def cb_send_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a test email using the saved draft — bypasses BA and quota."""
    from jyry.services.gmail_sender import SendOutcome

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
        result = await send_test_email(
            user_id=user.id,
            settings=settings,
            session=session,
            fetcher=fetcher,
        )

    if result.outcome is SendOutcome.SENT:
        target = settings.test_redirect_email or (user.gmail_address or "")
        await query.edit_message_text(
            messages.TEST_EMAIL_SENT.format(
                to=target, subject="Musterfirma GmbH"
            ),
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
    else:
        await query.edit_message_text(
            messages.TEST_EMAIL_FAILED.format(detail=result.detail or "unbekannt"),
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
