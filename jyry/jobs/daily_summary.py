"""Daily job: send an end-of-day summary to users on the 'daily' notification mode.

Scheduled once per day in the evening (Europe/Berlin). For every user with
``notification_mode == 'daily'`` who actually sent at least one application
today, push a single Telegram message with the count and the specialties they
applied for. Days where the user sent zero applications produce no message
(so the bot doesn't spam empty days).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from jyry.bot import messages
from jyry.db.models import Subscription, User
from jyry.payments.notify import send_telegram_notice

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

SessionScope = Callable[[], AbstractAsyncContextManager["AsyncSession"]]


async def run_daily_summary(
    *,
    token: str,
    session_scope: SessionScope,
) -> int:
    """Push one summary per opted-in user with non-zero sends today.

    Returns the number of summaries successfully delivered.
    """
    async with session_scope() as session:
        rows = await session.execute(
            select(User)
            .options(
                selectinload(User.specialties),
                selectinload(User.subscription),
            )
            .where(User.notification_mode == "daily")
        )
        users = list(rows.scalars())

    sent = 0
    for user in users:
        if user.telegram_id is None:
            continue
        sub: Subscription | None = user.subscription
        sent_today = sub.emails_sent_today if sub is not None else 0
        if sent_today <= 0:
            continue
        specialties = (
            ", ".join(s.specialty_keyword for s in user.specialties) or "—"
        )
        text = messages.NOTIFICATION_DAILY_SUMMARY.format(
            sent_today=sent_today, specialties=specialties
        )
        ok = await send_telegram_notice(
            token=token, chat_id=user.telegram_id, text=text
        )
        if ok:
            sent += 1
            logger.info(
                "daily summary sent: user_id=%s tg=%s sent_today=%s",
                user.id,
                user.telegram_id,
                sent_today,
            )
        else:
            logger.warning(
                "daily summary failed: user_id=%s tg=%s",
                user.id,
                user.telegram_id,
            )
    return sent
