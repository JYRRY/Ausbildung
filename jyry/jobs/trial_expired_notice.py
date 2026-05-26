"""Daily job: notify Free users whose 3-day trial just expired.

Scans for ``ACTIVE`` Free subscriptions whose ``expires_at`` is in the past,
sends a one-time Telegram notice, and flips the status to ``EXPIRED`` so the
notice fires at most once per trial.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from jyry.bot import messages
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.models import Subscription
from jyry.payments.notify import send_telegram_notice

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SessionScope = Callable[[], AbstractAsyncContextManager["AsyncSession"]]


async def run_trial_expired_notice(
    *,
    token: str,
    session_scope: SessionScope,
    now: datetime | None = None,
) -> int:
    """Send a one-time trial-expired notice and mark the subscription EXPIRED.

    Returns the number of notices successfully sent.
    """
    now = now or datetime.now(tz=UTC)

    async with session_scope() as session:
        rows = await session.execute(
            select(Subscription)
            .options(selectinload(Subscription.user))
            .where(
                Subscription.plan == Plan.FREE,
                Subscription.status == SubscriptionStatus.ACTIVE,
                Subscription.expires_at.is_not(None),
                Subscription.expires_at < now,
            )
        )
        subs = list(rows.scalars())

        sent = 0
        for sub in subs:
            if sub.user is None or sub.user.telegram_id is None:
                sub.status = SubscriptionStatus.EXPIRED
                continue
            ok = await send_telegram_notice(
                token=token,
                chat_id=sub.user.telegram_id,
                text=messages.FREE_TRIAL_EXPIRED_NOTICE,
            )
            sub.status = SubscriptionStatus.EXPIRED
            if ok:
                sent += 1
                logger.info(
                    "trial expired notice sent: user_id=%s tg=%s",
                    sub.user_id,
                    sub.user.telegram_id,
                )
            else:
                logger.warning(
                    "trial expired notice failed: user_id=%s tg=%s",
                    sub.user_id,
                    sub.user.telegram_id,
                )
        await session.commit()
    return sent
