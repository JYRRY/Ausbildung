"""FastAPI dependencies shared across all dashboard routes."""
from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyry.config import Settings, get_settings
from jyry.db.models import User
from jyry.db.session import session_scope
from jyry.webapp.auth.jwt import decode_session


async def get_db() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


def get_app_settings() -> Settings:
    return get_settings()


async def get_current_user(
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_db),
    jyry_session: str | None = Cookie(default=None, alias="jyry_session"),
) -> User:
    if not jyry_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    payload = decode_session(settings=settings, token=jyry_session)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session"
        )
    try:
        user_id = int(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed session"
        ) from exc

    user = (
        await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.subscription),
                selectinload(User.specialties),
                selectinload(User.states),
                selectinload(User.email_draft),
            )
        )
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists"
        )
    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin only"
        )
    return user
