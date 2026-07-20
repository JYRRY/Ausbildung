"""Cross-origin (Framer) auth support: CORS origins from settings, Bearer-token
acceptance alongside the session cookie, and configurable cookie Domain/SameSite.
"""
from __future__ import annotations

import pytest
from fastapi import HTTPException, Response

from jyry.config import Settings
from jyry.db.models import User
from jyry.webapp.auth.jwt import issue_session, set_session_cookie
from jyry.webapp.deps import _bearer_token, get_current_user


def _settings(**over) -> Settings:
    # conftest already exports TELEGRAM_BOT_TOKEN / FERNET_KEY / DATABASE_URL.
    over.setdefault("WEB_JWT_SECRET", "test-secret-value-padded-to-32-plus-bytes")
    return Settings(**over)


# --- CORS origin parsing ---------------------------------------------------


def test_cors_origins_split_strips_slash_and_blanks():
    s = _settings(WEB_CORS_ORIGINS="https://a.com/, https://b.com , ")
    assert s.web_cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_default_empty():
    assert _settings().web_cors_origins == []


# --- Bearer header parsing -------------------------------------------------


@pytest.mark.parametrize(
    "header,expected",
    [
        ("Bearer abc.def.ghi", "abc.def.ghi"),
        ("bearer lower.scheme", "lower.scheme"),  # scheme is case-insensitive
        ("Basic something", None),  # wrong scheme
        ("Bearer   ", None),  # empty token
        ("no-scheme-token", None),
        (None, None),
        ("", None),
    ],
)
def test_bearer_token_parsing(header, expected):
    assert _bearer_token(header) == expected


# --- Session cookie scope --------------------------------------------------


def test_session_cookie_carries_domain_and_samesite_none():
    s = _settings(WEB_COOKIE_DOMAIN=".jyrygroup.com", WEB_COOKIE_SAMESITE="none")
    resp = Response()
    set_session_cookie(resp, settings=s, token="TOK")
    header = resp.headers.get("set-cookie")
    assert "Domain=.jyrygroup.com" in header
    assert "SameSite=none" in header
    assert "Secure" in header  # SameSite=None requires Secure
    assert "HttpOnly" in header


def test_session_cookie_default_is_lax_host_only():
    s = _settings()  # defaults: lax, no domain
    resp = Response()
    set_session_cookie(resp, settings=s, token="TOK")
    header = resp.headers.get("set-cookie")
    assert "SameSite=lax" in header
    assert "Domain=" not in header


# --- get_current_user: cookie OR Bearer ------------------------------------


async def _make_user(db_session) -> User:
    user = User(email="u@example.com", google_oauth_sub="sub-xyz")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def test_get_current_user_accepts_bearer_token(db_session):
    s = _settings()
    user = await _make_user(db_session)
    token = issue_session(settings=s, user_id=user.id, is_admin=False)

    got = await get_current_user(
        settings=s,
        session=db_session,
        jyry_session=None,
        authorization=f"Bearer {token}",
    )
    assert got.id == user.id


async def test_get_current_user_accepts_cookie(db_session):
    s = _settings()
    user = await _make_user(db_session)
    token = issue_session(settings=s, user_id=user.id, is_admin=False)

    got = await get_current_user(
        settings=s,
        session=db_session,
        jyry_session=token,
        authorization=None,
    )
    assert got.id == user.id


async def test_get_current_user_rejects_when_no_credentials(db_session):
    s = _settings()
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            settings=s, session=db_session, jyry_session=None, authorization=None
        )
    assert exc.value.status_code == 401


async def test_get_current_user_rejects_bad_bearer(db_session):
    s = _settings()
    await _make_user(db_session)
    with pytest.raises(HTTPException) as exc:
        await get_current_user(
            settings=s,
            session=db_session,
            jyry_session=None,
            authorization="Bearer not-a-jwt",
        )
    assert exc.value.status_code == 401
