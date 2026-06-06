"""Shared helpers for the manual operational scripts."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.db.models import User


async def find_user_by_email(session: AsyncSession, email: str) -> User | None:
    """Look up a user by login email *or* Gmail sending address.

    Web signups store the address in ``email``; Telegram-only users may only
    have ``gmail_address`` set, so we match either to be forgiving.
    """
    needle = email.strip().lower()
    result = await session.execute(
        select(User).where(
            or_(
                User.email == needle,
                User.gmail_address == needle,
            )
        )
    )
    return result.scalars().first()
