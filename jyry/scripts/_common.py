"""Shared helpers for the manual operational scripts."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.db.models import User


class UserLookupError(Exception):
    """Raised when --user-id / --email can't be resolved to exactly one user."""


async def resolve_user(
    session: AsyncSession,
    *,
    user_id: int | None = None,
    email: str | None = None,
) -> User:
    """Resolve exactly one user by id (preferred) or login/Gmail email.

    The same address can belong to more than one row (e.g. a Telegram
    account *and* a separate web signup share a Gmail), so an ambiguous
    ``--email`` is rejected with a hint to use ``--user-id`` instead.
    """
    if user_id is not None:
        user = (
            await session.execute(select(User).where(User.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            raise UserLookupError(f"no user with id={user_id}")
        return user

    if email:
        needle = email.strip().lower()
        users = list(
            (
                await session.execute(
                    select(User)
                    .where(or_(User.email == needle, User.gmail_address == needle))
                    .order_by(User.id)
                )
            )
            .scalars()
            .all()
        )
        if not users:
            raise UserLookupError(f"no user found with email/gmail = {email!r}")
        if len(users) > 1:
            candidates = ", ".join(
                f"#{u.id}(tg={u.telegram_id}, onboarding={u.onboarding_complete})"
                for u in users
            )
            raise UserLookupError(
                f"{len(users)} users match {email!r}: {candidates}. "
                f"Re-run with --user-id <id> to pick one."
            )
        return users[0]

    raise UserLookupError("provide either --user-id or --email")
