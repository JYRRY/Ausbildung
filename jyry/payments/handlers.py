"""Paddle event dispatch — maps webhook events to DB mutations."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jyry.bot import messages, repos
from jyry.config import get_settings
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.payments.notify import send_telegram_notice

logger = logging.getLogger(__name__)


def _parse_plan(price_id: str) -> Plan:
    settings = get_settings()
    price_map: dict[str | None, Plan] = {
        settings.paddle_price_plus: Plan.PLUS,
        settings.paddle_price_pro: Plan.PRO,
        settings.paddle_price_max: Plan.MAX,
    }
    return price_map.get(price_id, Plan.PLUS)


def _parse_status(paddle_status: str) -> SubscriptionStatus:
    return {
        "active": SubscriptionStatus.ACTIVE,
        "trialing": SubscriptionStatus.ACTIVE,
        "paused": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "canceled": SubscriptionStatus.CANCELLED,
    }.get(paddle_status, SubscriptionStatus.ACTIVE)


def _get_telegram_id(payload: dict[str, Any]) -> int | None:
    custom = payload.get("data", {}).get("custom_data") or {}
    tg = custom.get("telegram_id")
    if tg is None:
        return None
    try:
        return int(tg)
    except (ValueError, TypeError):
        return None


def _get_user_id(payload: dict[str, Any]) -> int | None:
    """Web checkouts stash the User.id alongside (or instead of) telegram_id."""
    custom = payload.get("data", {}).get("custom_data") or {}
    uid = custom.get("user_id")
    if uid is None:
        return None
    try:
        return int(uid)
    except (ValueError, TypeError):
        return None


def _first_price_id(data: dict[str, Any]) -> str:
    items = data.get("items") or []
    if not items:
        return ""
    price = items[0].get("price") or {}
    return str(price.get("id", ""))


def _parse_expires_at(data: dict[str, Any]) -> datetime | None:
    period = data.get("current_billing_period") or {}
    raw = period.get("ends_at") or data.get("canceled_at") or data.get("next_billed_at")
    if not raw:
        return None
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


async def _upsert_from_payload(
    session: AsyncSession,
    payload: dict[str, Any],
    *,
    status_override: SubscriptionStatus | None = None,
) -> None:
    tg_id = _get_telegram_id(payload)
    user_id = _get_user_id(payload)
    if tg_id is None and user_id is None:
        return

    data = payload.get("data", {})
    paddle_sub_id = str(data.get("id", ""))
    price_id = _first_price_id(data)
    paddle_customer_id = str(data.get("customer_id", ""))
    paddle_status = data.get("status", "active")

    plan = _parse_plan(price_id)
    sub_status = status_override if status_override is not None else _parse_status(paddle_status)
    expires_at = _parse_expires_at(data)
    daily_quota = PLAN_DAILY_QUOTA.get(plan.value, PLAN_DAILY_QUOTA["free"])

    await repos.upsert_subscription(
        session,
        telegram_id=tg_id,
        user_id=user_id,
        plan=plan,
        status=sub_status,
        expires_at=expires_at,
        paddle_subscription_id=paddle_sub_id or None,
        paddle_customer_id=paddle_customer_id or None,
        daily_quota=daily_quota,
    )


async def _notify_subscription_activated(payload: dict[str, Any]) -> None:
    """Send a Telegram confirmation after a fresh ``subscription.created``."""
    tg_id = _get_telegram_id(payload)
    if tg_id is None:
        return
    data = payload.get("data", {})
    plan = _parse_plan(_first_price_id(data))
    daily_quota = PLAN_DAILY_QUOTA.get(plan.value, PLAN_DAILY_QUOTA["free"])
    settings = get_settings()
    token = settings.telegram_bot_token.get_secret_value()
    if not token:
        return
    text = messages.SUBSCRIPTION_ACTIVATED_NOTICE.format(
        plan=plan.value.capitalize(),
        daily_quota=daily_quota,
    )
    await send_telegram_notice(token=token, chat_id=tg_id, text=text)


async def dispatch_event(
    session: AsyncSession, event_type: str, payload: dict[str, Any]
) -> None:
    if event_type == "subscription.created":
        await _upsert_from_payload(session, payload)
        await _notify_subscription_activated(payload)
    elif event_type in {"subscription.updated", "subscription.resumed"}:
        await _upsert_from_payload(session, payload)
    elif event_type == "subscription.canceled":
        await _upsert_from_payload(
            session, payload, status_override=SubscriptionStatus.CANCELLED
        )
    elif event_type == "subscription.past_due":
        await _upsert_from_payload(
            session, payload, status_override=SubscriptionStatus.PAST_DUE
        )
    elif event_type == "subscription.paused":
        await _upsert_from_payload(session, payload)
    # transaction.completed and unknown events: ignored — the bot reacts to
    # subscription state transitions, not individual charge events.
