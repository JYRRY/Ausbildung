"""Top-level /start handler and menu-routing callbacks."""
from __future__ import annotations

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
        await query.edit_message_text(messages.ASK_NAME, reply_markup=keyboards.back_only())
        return OnboardingState.ASK_NAME

    await query.edit_message_text(
        messages.MAIN_MENU_TITLE,
        reply_markup=keyboards.main_menu(is_active=full.is_active),
    )
    return ConversationHandler.END


async def cb_back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
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
