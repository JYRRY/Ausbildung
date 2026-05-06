"""Lemon Squeezy event dispatch — maps webhook events to DB mutations."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from jyry.bot import repos
from jyry.config import get_settings
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.enums import Plan, SubscriptionStatus


def _parse_plan(variant_id: str) -> Plan:
    settings = get_settings()
    variant_map: dict[str | None, Plan] = {
        settings.lemonsqueezy_variant_basic: Plan.BASIC,
        settings.lemonsqueezy_variant_pro: Plan.PRO,
        settings.lemonsqueezy_variant_max: Plan.MAX,
    }
    return variant_map.get(variant_id, Plan.BASIC)


def _parse_status(ls_status: str) -> SubscriptionStatus:
    return {
        "active": SubscriptionStatus.ACTIVE,
        "on_trial": SubscriptionStatus.ACTIVE,
        "paused": SubscriptionStatus.ACTIVE,
        "past_due": SubscriptionStatus.PAST_DUE,
        "unpaid": SubscriptionStatus.PAST_DUE,
        "cancelled": SubscriptionStatus.CANCELLED,
        "expired": SubscriptionStatus.EXPIRED,
    }.get(ls_status, SubscriptionStatus.ACTIVE)


def _get_telegram_id(payload: dict[str, Any]) -> int | None:
    custom = payload.get("meta", {}).get("custom_data", {})
    tg = custom.get("telegram_id")
    if tg is None:
        return None
    try:
        return int(tg)
    except (ValueError, TypeError):
        return None


def _parse_expires_at(attrs: dict[str, Any]) -> datetime | None:
    ends_at_str = attrs.get("ends_at")
    renews_at_str = attrs.get("renews_at")
    raw = ends_at_str or renews_at_str
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
    if tg_id is None:
        return

    data = payload.get("data", {})
    attrs = data.get("attributes", {})
    ls_sub_id = str(data.get("id", ""))
    variant_id = str(attrs.get("variant_id", ""))
    ls_customer_id = str(attrs.get("customer_id", ""))
    ls_status = attrs.get("status", "active")

    plan = _parse_plan(variant_id)
    sub_status = status_override if status_override is not None else _parse_status(ls_status)
    expires_at = _parse_expires_at(attrs)
    daily_quota = PLAN_DAILY_QUOTA.get(plan.value, PLAN_DAILY_QUOTA["free"])

    await repos.upsert_subscription(
        session,
        telegram_id=tg_id,
        plan=plan,
        status=sub_status,
        expires_at=expires_at,
        lemonsqueezy_subscription_id=ls_sub_id or None,
        lemonsqueezy_customer_id=ls_customer_id or None,
        daily_quota=daily_quota,
    )


async def dispatch_event(
    session: AsyncSession, event_name: str, payload: dict[str, Any]
) -> None:
    if event_name in {
        "subscription_created",
        "subscription_updated",
        "subscription_payment_success",
    }:
        await _upsert_from_payload(session, payload)
    elif event_name == "subscription_cancelled":
        await _upsert_from_payload(
            session, payload, status_override=SubscriptionStatus.CANCELLED
        )
    elif event_name == "subscription_expired":
        await _upsert_from_payload(
            session, payload, status_override=SubscriptionStatus.EXPIRED
        )
    elif event_name == "subscription_payment_failed":
        await _upsert_from_payload(
            session, payload, status_override=SubscriptionStatus.PAST_DUE
        )
    # Unknown events are silently ignored
