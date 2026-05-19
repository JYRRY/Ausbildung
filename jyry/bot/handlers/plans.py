"""Plan selection callback handlers."""
from __future__ import annotations

import logging

from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from jyry.bot import keyboards, messages, repos
from jyry.bot.keyboards import CB
from jyry.bot.states import OnboardingState
from jyry.config import get_settings
from jyry.constants import PLAN_PRICES
from jyry.db.enums import SubscriptionStatus

logger = logging.getLogger(__name__)


_PLAN_RANK: dict[str, int] = {"free": 0, "plus": 1, "pro": 2, "max": 3}

_CB_TO_PLAN: dict[str, str] = {
    CB["plan_plus"]: "plus",
    CB["plan_pro"]: "pro",
    CB["plan_max"]: "max",
    CB["plan_upgrade_confirm_plus"]: "plus",
    CB["plan_upgrade_confirm_pro"]: "pro",
    CB["plan_upgrade_confirm_max"]: "max",
}


def _variant_id_for(settings, plan: str) -> str | None:
    return {
        "plus": settings.lemonsqueezy_variant_plus,
        "pro": settings.lemonsqueezy_variant_pro,
        "max": settings.lemonsqueezy_variant_max,
    }.get(plan)


async def cb_plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
            reply_markup=keyboards.main_menu(
                is_active=full.is_active,
                show_templates=repos.can_use_templates(full),
            ),
        )
        return ConversationHandler.END

    if full:
        context.user_data["user_id"] = full.id
        if full.full_name:
            from jyry.bot.handlers.start import _resume_onboarding

            return await _resume_onboarding(query, context, full)

    await query.edit_message_text(
        messages.PLAN_FREE_ACTIVATED + "\n\n" + messages.ASK_NAME,
        reply_markup=keyboards.back_only(allow_forward=True),
    )
    return OnboardingState.ASK_NAME


async def cb_plan_paid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Either start a fresh checkout (no active sub) or show an upgrade
    confirmation screen (active paid sub on a lower tier)."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    settings = get_settings()
    tg_id = update.effective_user.id
    cb_data = query.data or ""
    target_plan = _CB_TO_PLAN.get(cb_data)

    if target_plan is None or settings.lemonsqueezy_api_key is None:
        await query.edit_message_text(
            messages.PLAN_CHECKOUT_PLACEHOLDER,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        current_plan = repos.plan_value(full) if full else "free"
        has_ls_sub = bool(
            full
            and full.subscription
            and full.subscription.lemonsqueezy_subscription_id
            and full.subscription.status == SubscriptionStatus.ACTIVE
        )

    current_rank = _PLAN_RANK.get(current_plan, 0)
    target_rank = _PLAN_RANK[target_plan]

    if has_ls_sub and current_rank > 0:
        if target_rank <= current_rank:
            # Defensive — UI shouldn't surface these buttons in the first place.
            await query.edit_message_text(
                messages.PLAN_ALREADY_MAX
                if current_plan == "max"
                else messages.PLANS_TITLE_ACTIVE.format(
                    plan=current_plan.capitalize()
                ),
                reply_markup=keyboards.plans_menu(current_plan=current_plan),
                parse_mode="Markdown",
            )
            return

        await query.edit_message_text(
            messages.PLAN_UPGRADE_CONFIRM.format(
                current_plan=current_plan.capitalize(),
                target_plan=target_plan.capitalize(),
                target_price=PLAN_PRICES.get(target_plan, "?"),
            ),
            reply_markup=keyboards.upgrade_confirm_keyboard(target_plan),
            parse_mode="Markdown",
        )
        return

    # No active paid sub: regular checkout flow.
    variant_id = _variant_id_for(settings, target_plan)
    if variant_id is None:
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
        logger.exception(
            "Checkout URL generation failed tg_id=%s variant=%s", tg_id, variant_id
        )
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


async def cb_plan_upgrade_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """User confirmed the upgrade — PATCH the LS subscription to the new
    variant. LS prorates the difference and charges the saved card."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    settings = get_settings()
    tg_id = update.effective_user.id
    target_plan = _CB_TO_PLAN.get(query.data or "")
    variant_id = _variant_id_for(settings, target_plan) if target_plan else None

    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    ls_sub_id = (
        full.subscription.lemonsqueezy_subscription_id
        if full and full.subscription
        else None
    )
    if (
        target_plan is None
        or variant_id is None
        or ls_sub_id is None
        or settings.lemonsqueezy_api_key is None
    ):
        await query.edit_message_text(
            messages.PLAN_UPGRADE_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import lemonsqueezy

    try:
        await lemonsqueezy.update_subscription_variant(
            settings, subscription_id=ls_sub_id, variant_id=variant_id
        )
    except Exception:
        logger.exception(
            "LS upgrade failed tg_id=%s sub=%s variant=%s",
            tg_id,
            ls_sub_id,
            variant_id,
        )
        await query.edit_message_text(
            messages.PLAN_UPGRADE_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    # The DB row will be updated by the `subscription_updated` webhook; the
    # message here is just user-facing confirmation.
    await query.edit_message_text(
        messages.PLAN_UPGRADE_SUCCESS.format(target_plan=target_plan.capitalize()),
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )


_RETENTION_BENEFITS: dict[str, str] = {
    "pro": (
        "• 100 E-Mails pro Tag (statt 30)\n"
        "• Alle Berufe (statt nur 3)\n"
        "• Alle 16 Bundesländer (statt nur 6)\n"
        "• Zugang zu allen Bewerbungs-Vorlagen"
    ),
    "max": (
        "• Längere Laufzeit: 6 Monate auf einmal — günstiger pro Monat\n"
        "• 24/7-Priority-Support\n"
        "• Alles aus dem Pro-Tarif inklusive"
    ),
}


def _retention_offer_for(current_plan: str) -> tuple[str, str] | None:
    """Return (target_plan, delta_price_str) to suggest at cancel time, or
    None if no meaningful upgrade can be offered (i.e. user is on Max)."""
    if current_plan == "plus":
        # Plus 14,99/mo  vs  Pro 29,99/3 months → roughly 10/mo → no upgrade
        # is *cheaper*, so frame the delta against the headline price.
        return ("pro", "15,00")
    if current_plan == "pro":
        return ("max", "69,01")
    return None


async def cb_plan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """First step of cancellation: show a retention offer pitching an upgrade
    instead. Max users skip straight to the cancel-confirm screen because
    there's no higher tier to upsell."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        current_plan = repos.plan_value(full) if full else "free"

    offer = _retention_offer_for(current_plan)
    if offer is None:
        await query.edit_message_text(
            messages.PLAN_CANCEL_CONFIRM.format(plan=current_plan.capitalize()),
            reply_markup=keyboards.cancel_confirm_keyboard(),
            parse_mode="Markdown",
        )
        return

    target_plan, delta = offer
    await query.edit_message_text(
        messages.PLAN_RETENTION_OFFER.format(
            current_plan=current_plan.capitalize(),
            target_plan=target_plan.capitalize(),
            delta=delta,
            benefits=_RETENTION_BENEFITS[target_plan],
        ),
        reply_markup=keyboards.retention_keyboard(target_plan),
        parse_mode="Markdown",
    )


async def cb_plan_cancel_proceed(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """User declined the retention offer — show the real cancel-confirm
    screen with the auto-renewal / end-of-period notice."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)
        current_plan = repos.plan_value(full) if full else "free"

    await query.edit_message_text(
        messages.PLAN_CANCEL_CONFIRM.format(plan=current_plan.capitalize()),
        reply_markup=keyboards.cancel_confirm_keyboard(),
        parse_mode="Markdown",
    )


async def cb_plan_cancel_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    settings = get_settings()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    ls_sub_id = (
        full.subscription.lemonsqueezy_subscription_id
        if full and full.subscription
        else None
    )
    current_plan = repos.plan_value(full) if full else "free"

    if ls_sub_id is None or settings.lemonsqueezy_api_key is None:
        await query.edit_message_text(
            messages.PLAN_CANCEL_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import lemonsqueezy

    try:
        await lemonsqueezy.cancel_subscription(settings, subscription_id=ls_sub_id)
    except Exception:
        logger.exception("LS cancel failed tg_id=%s sub=%s", tg_id, ls_sub_id)
        await query.edit_message_text(
            messages.PLAN_CANCEL_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    await query.edit_message_text(
        messages.PLAN_CANCEL_SUCCESS.format(plan=current_plan.capitalize()),
        reply_markup=keyboards.back_to_main_only(),
        parse_mode="Markdown",
    )
