"""Daily job: warn paid subscribers ~3 days before LS auto-renewal.

Scans the ``subscriptions`` table for rows whose ``expires_at`` falls in a
24-hour window roughly 3 days ahead of *now*, then sends one Telegram message
per user via the Bot API. The job is scheduled once per day (cron in
``JyryScheduler.add_daily_cron``); the window matches the cadence so each
subscription gets at most one reminder per renewal cycle.

Free / cancelled / past-due subscriptions are skipped — only ACTIVE paid
plans (PLUS, PRO, MAX) auto-renew.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from jyry.bot import messages
from jyry.constants import PLAN_PRICES
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.models import Subscription
from jyry.payments.notify import send_telegram_notice

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SessionScope = Callable[[], AbstractAsyncContextManager["AsyncSession"]]


async def run_renewal_reminder(
    *,
    token: str,
    session_scope: SessionScope,
    now: datetime | None = None,
) -> int:
    """Send a 3-day pre-renewal reminder to eligible subscribers.

    Returns the number of reminders successfully sent.
    """
    now = now or datetime.now(tz=UTC)
    window_start = now + timedelta(days=3)
    window_end = now + timedelta(days=4)

    async with session_scope() as session:
        rows = await session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.plan.in_([Plan.PLUS, Plan.PRO, Plan.MAX]),
                Subscription.expires_at.is_not(None),
                Subscription.expires_at >= window_start,
                Subscription.expires_at < window_end,
            )
        )
        subs = list(rows.scalars())

    sent = 0
    for sub in subs:
        if sub.user is None or sub.user.telegram_id is None:
            continue
        plan_value = sub.plan.value if isinstance(sub.plan, Plan) else str(sub.plan)
        price = PLAN_PRICES.get(plan_value)
        if price is None:
            continue
        text = messages.RENEWAL_REMINDER.format(
            plan=plan_value.capitalize(),
            price=price,
        )
        ok = await send_telegram_notice(
            token=token, chat_id=sub.user.telegram_id, text=text
        )
        if ok:
            sent += 1
            logger.info(
                "renewal reminder sent: user_id=%s tg=%s plan=%s expires_at=%s",
                sub.user_id,
                sub.user.telegram_id,
                plan_value,
                sub.expires_at,
            )
        else:
            logger.warning(
                "renewal reminder failed: user_id=%s tg=%s",
                sub.user_id,
                sub.user.telegram_id,
            )
    return sent
