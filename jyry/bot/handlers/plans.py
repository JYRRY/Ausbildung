"""Plan selection callback handlers."""
from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from jyry.bot import keyboards, messages, repos


async def cb_plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        await repos.grant_free_trial(session, user.id)
        full = await repos.load_user(session, user.id)

    if full and full.onboarding_complete:
        await query.edit_message_text(
            messages.PLAN_FREE_ACTIVATED + "\n\n" + messages.MAIN_MENU_TITLE,
            reply_markup=keyboards.main_menu(is_active=full.is_active),
        )
        return

    if full:
        context.user_data["user_id"] = full.id
    await query.edit_message_text(
        messages.PLAN_FREE_ACTIVATED + "\n\n" + messages.ASK_NAME,
        reply_markup=keyboards.back_only(),
    )


async def cb_plan_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Stub — M5 will add real Lemon Squeezy checkout URLs."""
    query = update.callback_query
    assert query is not None
    await query.answer()
    await query.edit_message_text(
        messages.PLAN_CHECKOUT_PLACEHOLDER,
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
