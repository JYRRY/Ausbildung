"""Mutations on the user's profile fields and operational state."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.bot import repos
from jyry.db.models import User
from jyry.services.crypto import encrypt_secret
from jyry.webapp.deps import get_current_user, get_db
from jyry.webapp.schemas import (
    ActivePatch,
    AppPasswordPatch,
    NotificationPatch,
    ProfilePatch,
)

router = APIRouter(prefix="/api", tags=["profile"])


@router.patch("/profile")
async def patch_profile(
    body: ProfilePatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # gmail_address is intentionally NOT editable: it is pinned to the Google
    # login email at sign-in time (see routes/auth.py). Only the display name
    # can be changed here.
    if body.full_name is not None:
        user.full_name = body.full_name.strip() or None
    if body.postal_street is not None:
        user.postal_street = body.postal_street.strip() or None
    if body.postal_plz_city is not None:
        user.postal_plz_city = body.postal_plz_city.strip() or None
    if body.phone is not None:
        user.phone = body.phone.strip() or None
    await session.commit()
    return {"ok": True}


@router.put("/profile/app-password")
async def put_app_password(
    body: AppPasswordPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    # Google App Passwords are exactly 16 characters, shown grouped as 4×4
    # with spaces. Accept spaced or unspaced input by stripping whitespace,
    # then require exactly 16 — anything else won't authenticate over SMTP.
    cleaned = "".join(body.app_password.split())
    if len(cleaned) != 16:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App-Passwort muss genau 16 Zeichen lang sein.",
        )
    user.gmail_app_password_enc = encrypt_secret(cleaned)
    await session.commit()
    return {"ok": True}


@router.put("/notifications")
async def put_notifications(
    body: NotificationPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    if body.mode not in repos.NOTIFICATION_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"mode must be one of {repos.NOTIFICATION_MODES}",
        )
    user.notification_mode = body.mode
    await session.commit()
    return {"ok": True}


@router.put("/active")
async def put_active(
    body: ActivePatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> dict:
    user.is_active = body.is_active
    await session.commit()
    return {"ok": True}
