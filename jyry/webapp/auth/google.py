"""Google OAuth flow — scopes openid/email/profile only.

This is the *authentication* path. Sending still goes through SMTP + the
user's App Password. We deliberately stay away from any gmail.* scope so
Google's CASA verification does not apply.
"""
from __future__ import annotations

import secrets
from urllib.parse import urlencode

import httpx

from jyry.config import Settings

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = ("openid", "email", "profile")


def redirect_uri(settings: Settings) -> str:
    return f"{settings.web_public_url.rstrip('/')}/api/auth/google/callback"


def make_state() -> str:
    """Opaque CSRF token written to a short-lived cookie before redirect."""
    return secrets.token_urlsafe(32)


def build_authorize_url(*, settings: Settings, state: str) -> str:
    if settings.google_client_id is None:
        raise RuntimeError("GOOGLE_CLIENT_ID is not configured")
    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri(settings),
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"


async def exchange_code(*, settings: Settings, code: str) -> dict:
    """Exchange the OAuth code for an access token + userinfo."""
    if settings.google_client_id is None or settings.google_client_secret is None:
        raise RuntimeError("Google OAuth is not configured")

    async with httpx.AsyncClient(timeout=15) as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.google_client_id,
                "client_secret": settings.google_client_secret.get_secret_value(),
                "redirect_uri": redirect_uri(settings),
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        token = token_resp.json()

        userinfo_resp = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {token['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
