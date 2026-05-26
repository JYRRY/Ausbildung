"""Plan selection callback handlers."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from telegram import Update
from telegram.ext import ContextTypes, ConversationHandler

from jyry.bot import keyboards, messages, repos
from jyry.bot.keyboards import CB
from jyry.bot.states import OnboardingState
from jyry.config import get_settings
from jyry.constants import PLAN_PRICES
from jyry.db.enums import ApplicationStatus, SubscriptionStatus
from jyry.db.models import Application

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


def _price_id_for(settings, plan: str) -> str | None:
    return {
        "plus": settings.paddle_price_plus,
        "pro": settings.paddle_price_pro,
        "max": settings.paddle_price_max,
    }.get(plan)


async def cb_plan_free(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    assert context.user_data is not None
    await query.answer()
    tg_id = update.effective_user.id
    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        try:
            await repos.grant_free_trial(session, user.id)
        except repos.FreeTrialAlreadyUsedError:
            await query.edit_message_text(
                messages.FREE_TRIAL_ALREADY_USED,
                reply_markup=keyboards.plans_menu(current_plan=None),
                parse_mode="Markdown",
            )
            return ConversationHandler.END
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

    if target_plan is None or settings.paddle_api_key is None:
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
        has_paid_sub = bool(
            full
            and full.subscription
            and full.subscription.paddle_subscription_id
            and full.subscription.status == SubscriptionStatus.ACTIVE
        )

    current_rank = _PLAN_RANK.get(current_plan, 0)
    target_rank = _PLAN_RANK[target_plan]

    if has_paid_sub and current_rank > 0:
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
    price_id = _price_id_for(settings, target_plan)
    if price_id is None:
        await query.edit_message_text(
            messages.PLAN_CHECKOUT_PLACEHOLDER,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import paddle

    try:
        url = await paddle.create_checkout_url(
            settings, price_id=price_id, telegram_id=tg_id
        )
    except Exception:
        logger.exception(
            "Checkout URL generation failed tg_id=%s price=%s", tg_id, price_id
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
    """User confirmed the upgrade — PATCH the Paddle subscription to the new
    price. Paddle prorates the difference and charges the saved card."""
    query = update.callback_query
    assert query is not None and update.effective_user is not None
    await query.answer()

    settings = get_settings()
    tg_id = update.effective_user.id
    target_plan = _CB_TO_PLAN.get(query.data or "")
    price_id = _price_id_for(settings, target_plan) if target_plan else None

    async with context.bot_data["session_scope"]() as session:
        user = await repos.get_or_create_user(session, tg_id)
        full = await repos.load_user(session, user.id)

    paddle_sub_id = (
        full.subscription.paddle_subscription_id
        if full and full.subscription
        else None
    )
    if (
        target_plan is None
        or price_id is None
        or paddle_sub_id is None
        or settings.paddle_api_key is None
    ):
        await query.edit_message_text(
            messages.PLAN_UPGRADE_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import paddle

    try:
        await paddle.update_subscription_price(
            settings, subscription_id=paddle_sub_id, price_id=price_id
        )
    except Exception:
        logger.exception(
            "Paddle upgrade failed tg_id=%s sub=%s price=%s",
            tg_id,
            paddle_sub_id,
            price_id,
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

# Numeric headline prices (euro) — kept separate from the German-formatted
# string in constants.PLAN_PRICES so we can do arithmetic without parsing.
_PLAN_PRICE_EUR: dict[str, float] = {
    "plus": 14.99,
    "pro": 29.99,
    "max": 99.00,
}


def _next_tier(current_plan: str) -> str | None:
    return {"plus": "pro", "pro": "max"}.get(current_plan)


def _format_eur(value: float) -> str:
    """German-formatted euro amount like '7,49'. Always two decimals, comma
    as the decimal separator. Negative or near-zero amounts clamp to 0,00."""
    if value < 0.005:
        return "0,00"
    return f"{value:.2f}".replace(".", ",")


def _remaining_fraction(sub) -> float:
    """Fraction of the current billing cycle the user has *not yet* consumed.

    Returns 1.0 for a brand-new sub, ~0.0 for one about to expire, and 1.0
    as a safe default if the timestamps are missing or malformed.
    """
    if not sub or not sub.expires_at or not sub.started_at:
        return 1.0
    started = sub.started_at
    expires = sub.expires_at
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if expires.tzinfo is None:
        expires = expires.replace(tzinfo=UTC)
    total = (expires - started).total_seconds()
    if total <= 0:
        return 1.0
    remaining = (expires - datetime.now(tz=UTC)).total_seconds()
    return max(0.0, min(1.0, remaining / total))


async def _sent_email_count(session, user_id: int) -> int:
    return (
        await session.execute(
            select(func.count(Application.id)).where(
                Application.user_id == user_id,
                Application.status == ApplicationStatus.SENT.value,
            )
        )
    ).scalar_one()


async def _retention_offer(
    session, full_user
) -> tuple[str, str] | None:
    """Decide which upgrade to pitch at cancel time and what price delta
    to advertise.

    Pricing rules (Arabic spec from the user):
      * If the user has *not used the bot at all* (zero sent emails), we
        quote the full headline price difference between plans.
      * Otherwise we prorate that headline difference by the share of the
        current paid period the user still has left — that is roughly what
        Paddle will actually charge on the PATCH.
    """
    current_plan = repos.plan_value(full_user) if full_user else "free"
    target_plan = _next_tier(current_plan)
    if target_plan is None:
        return None

    full_delta = _PLAN_PRICE_EUR[target_plan] - _PLAN_PRICE_EUR[current_plan]
    sent = await _sent_email_count(session, full_user.id) if full_user else 0
    if sent == 0:
        return target_plan, _format_eur(full_delta)

    fraction = _remaining_fraction(full_user.subscription if full_user else None)
    return target_plan, _format_eur(full_delta * fraction)


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
        offer = await _retention_offer(session, full)

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

    paddle_sub_id = (
        full.subscription.paddle_subscription_id
        if full and full.subscription
        else None
    )
    current_plan = repos.plan_value(full) if full else "free"

    if paddle_sub_id is None or settings.paddle_api_key is None:
        await query.edit_message_text(
            messages.PLAN_CANCEL_FAILED,
            reply_markup=keyboards.back_to_main_only(),
            parse_mode="Markdown",
        )
        return

    from jyry.payments import paddle

    try:
        await paddle.cancel_subscription(settings, subscription_id=paddle_sub_id)
    except Exception:
        logger.exception("Paddle cancel failed tg_id=%s sub=%s", tg_id, paddle_sub_id)
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
