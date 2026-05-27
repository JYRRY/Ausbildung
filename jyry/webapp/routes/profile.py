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


@router.patch("/profile", status_code=204)
async def patch_profile(
    body: ProfilePatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    if body.full_name is not None:
        user.full_name = body.full_name.strip() or None
    if body.gmail_address is not None:
        address = body.gmail_address.strip().lower() or None
        if address and ("@" not in address or "." not in address.split("@")[-1]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Ungültige Gmail-Adresse",
            )
        user.gmail_address = address
    await session.commit()


@router.put("/profile/app-password", status_code=204)
async def put_app_password(
    body: AppPasswordPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    cleaned = body.app_password.replace(" ", "").strip()
    if len(cleaned) < 12:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="App-Passwort sieht zu kurz aus (mind. 12 Zeichen)",
        )
    user.gmail_app_password_enc = encrypt_secret(cleaned)
    await session.commit()


@router.put("/notifications", status_code=204)
async def put_notifications(
    body: NotificationPatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    if body.mode not in repos.NOTIFICATION_MODES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"mode must be one of {repos.NOTIFICATION_MODES}",
        )
    user.notification_mode = body.mode
    await session.commit()


@router.put("/active", status_code=204)
async def put_active(
    body: ActivePatch,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> None:
    user.is_active = body.is_active
    await session.commit()
