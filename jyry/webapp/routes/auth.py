"""Google OAuth login/logout routes."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.config import Settings
from jyry.db.models import User
from jyry.webapp.auth.google import (
    build_authorize_url,
    exchange_code,
    make_state,
)
from jyry.webapp.auth.jwt import (
    clear_session_cookie,
    issue_session,
    set_session_cookie,
)
from jyry.webapp.deps import get_app_settings, get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])

_STATE_COOKIE = "jyry_oauth_state"


@router.get("/google/login")
async def google_login(
    settings: Settings = Depends(get_app_settings),
) -> Response:
    """Kick off the Google OAuth flow."""
    state = make_state()
    target = build_authorize_url(settings=settings, state=state)
    response = RedirectResponse(url=target, status_code=302)
    response.set_cookie(
        key=_STATE_COOKIE,
        value=state,
        max_age=600,
        httponly=True,
        secure=settings.env != "development",
        samesite="lax",
        path="/api/auth",
    )
    return response


@router.get("/google/callback")
async def google_callback(
    code: str,
    state: str,
    settings: Settings = Depends(get_app_settings),
    session: AsyncSession = Depends(get_db),
    state_cookie: str | None = Cookie(default=None, alias=_STATE_COOKIE),
) -> Response:
    """Handle Google's redirect: exchange code, upsert user, set session cookie."""
    if not state_cookie or state_cookie != state:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Bad OAuth state"
        )

    try:
        userinfo = await exchange_code(settings=settings, code=code)
    except Exception:
        logger.exception("Google token exchange failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail="OAuth exchange failed"
        ) from None

    sub = userinfo.get("sub")
    email = userinfo.get("email")
    if not sub or not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Google did not return sub/email",
        )

    user = (
        await session.execute(select(User).where(User.google_oauth_sub == sub))
    ).scalar_one_or_none()
    if user is None:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()

    now = datetime.now(tz=UTC)
    if user is None:
        user = User(
            google_oauth_sub=sub,
            email=email,
            # Sending is locked to the login account: the Gmail used to sign in
            # IS the address applications are sent from. This prevents one user
            # from reselling the bot under other people's inboxes.
            gmail_address=email,
            google_picture=userinfo.get("picture"),
            full_name=userinfo.get("name"),
            is_active=False,  # gate sending behind the onboarding flow on /app
            onboarding_complete=False,
        )
        session.add(user)
    else:
        user.google_oauth_sub = sub
        user.email = email
        # Keep the sending address pinned to the login email (see above).
        user.gmail_address = email
        if userinfo.get("picture"):
            user.google_picture = userinfo["picture"]
        if not user.full_name and userinfo.get("name"):
            user.full_name = userinfo["name"]
    user.updated_at = now
    await session.commit()
    await session.refresh(user)

    token = issue_session(settings=settings, user_id=user.id, is_admin=user.is_admin)
    redirect = RedirectResponse(
        url=f"{settings.web_public_url.rstrip('/')}/app", status_code=302
    )
    set_session_cookie(redirect, settings=settings, token=token)
    redirect.delete_cookie(key=_STATE_COOKIE, path="/api/auth")
    logger.info(
        "google sign-in: user_id=%s email=%s new=%s",
        user.id,
        email,
        user.created_at == user.updated_at,
    )
    return redirect


@router.post("/logout")
async def logout(
    settings: Settings = Depends(get_app_settings),
) -> Response:
    response = Response(status_code=204)
    clear_session_cookie(response, settings=settings)
    return response
