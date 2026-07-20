"""Session JWT — signed once on login, sent back on every request via cookie.

We deliberately keep the JWT tiny (sub + is_admin + exp). All other user data
is freshly loaded from the DB per request — that way a flipped is_admin or a
banned user takes effect on the next request, not after token expiry.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Response

from jyry.config import Settings

_ALGORITHM = "HS256"


def issue_session(*, settings: Settings, user_id: int, is_admin: bool) -> str:
    """Mint a session JWT for ``user_id``."""
    now = datetime.now(tz=UTC)
    payload = {
        "sub": str(user_id),
        "is_admin": is_admin,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.web_session_days)).timestamp()),
    }
    return jwt.encode(
        payload, settings.web_jwt_secret.get_secret_value(), algorithm=_ALGORITHM
    )


def decode_session(*, settings: Settings, token: str) -> dict | None:
    """Return the JWT payload or ``None`` if invalid / expired."""
    try:
        return jwt.decode(
            token,
            settings.web_jwt_secret.get_secret_value(),
            algorithms=[_ALGORITHM],
        )
    except jwt.PyJWTError:
        return None


def set_session_cookie(
    response: Response, *, settings: Settings, token: str
) -> None:
    # SameSite=None requires Secure per the spec; force it on so the cookie is
    # not silently dropped even in a non-prod cross-site test.
    secure = settings.env != "development" or settings.web_cookie_samesite == "none"
    response.set_cookie(
        key=settings.web_session_cookie,
        value=token,
        max_age=settings.web_session_days * 24 * 3600,
        httponly=True,
        secure=secure,
        samesite=settings.web_cookie_samesite,
        path="/",
        domain=settings.web_cookie_domain,
    )


def clear_session_cookie(response: Response, *, settings: Settings) -> None:
    secure = settings.env != "development" or settings.web_cookie_samesite == "none"
    response.delete_cookie(
        key=settings.web_session_cookie,
        path="/",
        secure=secure,
        samesite=settings.web_cookie_samesite,
        domain=settings.web_cookie_domain,
    )
