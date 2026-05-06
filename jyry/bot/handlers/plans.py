"""Plan selection callback handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes

from jyry.bot import keyboards, messages, repos
from jyry.bot.keyboards import CB
from jyry.config import get_settings

logger = logging.getLogger(__name__)


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
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    settings = get_settings()
    tg_id = update.effective_user.id
    cb_data = query.data or ""

    variant_map: dict[str, str | None] = {
        CB["plan_basic"]: settings.lemonsqueezy_variant_basic,
        CB["plan_pro"]: settings.lemonsqueezy_variant_pro,
        CB["plan_max"]: settings.lemonsqueezy_variant_max,
    }
    variant_id = variant_map.get(cb_data)

    if variant_id is None or settings.lemonsqueezy_api_key is None:
        await query.edit_message_text(
            messages.PLAN_CHECKOUT_PLACEHOLDER,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import lemonsqueezy

    try:
        url = await lemonsqueezy.create_checkout_url(
            settings, variant_id=variant_id, telegram_id=tg_id
        )
    except Exception:
        logger.exception("Checkout URL generation failed tg_id=%s variant=%s", tg_id, variant_id)
        await query.edit_message_text(
            messages.PLAN_CHECKOUT_PLACEHOLDER,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        messages.PLAN_CHECKOUT_READY,
        reply_markup=keyboards.checkout_keyboard(url),
    )
