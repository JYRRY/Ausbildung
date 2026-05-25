"""Tests for jyry.payments.paddle and the Paddle-wired cb_plan_paid."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
import respx
from httpx import Response
from pydantic import SecretStr

from jyry.bot import messages
from jyry.bot.handlers import plans as plans_handler
from jyry.bot.keyboards import CB
from jyry.config import Settings
from jyry.payments import paddle

_API_BASE = "https://sandbox-api.paddle.com"


# ---------------------------------------------------------------------------
# create_checkout_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_returns_url():
    settings = _settings(api_key="k")
    respx.post(f"{_API_BASE}/transactions").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "id": "txn_1",
                    "checkout": {"url": "https://pay.paddle.com/c/abc123"},
                }
            },
        )
    )

    url = await paddle.create_checkout_url(
        settings, price_id="pri_plus", telegram_id=42
    )

    assert url == "https://pay.paddle.com/c/abc123"


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_sends_telegram_id_and_price():
    settings = _settings(api_key="k")
    captured: list[dict] = []

    def _capture(request):
        captured.append(json.loads(request.content))
        return Response(
            200,
            json={"data": {"id": "txn_1", "checkout": {"url": "https://x"}}},
        )

    respx.post(f"{_API_BASE}/transactions").mock(side_effect=_capture)

    await paddle.create_checkout_url(settings, price_id="pri_pro", telegram_id=99)

    body = captured[0]
    assert body["items"] == [{"price_id": "pri_pro", "quantity": 1}]
    assert body["custom_data"] == {"telegram_id": "99"}


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_sends_bearer_auth():
    settings = _settings(api_key="topsecret")
    captured: list[httpx.Request] = []

    def _capture(request):
        captured.append(request)
        return Response(
            200, json={"data": {"id": "t", "checkout": {"url": "https://x"}}}
        )

    respx.post(f"{_API_BASE}/transactions").mock(side_effect=_capture)

    await paddle.create_checkout_url(settings, price_id="pri", telegram_id=1)

    assert captured[0].headers["authorization"] == "Bearer topsecret"


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_raises_on_http_error():
    settings = _settings(api_key="k")
    respx.post(f"{_API_BASE}/transactions").mock(
        return_value=Response(401, json={"error": {"detail": "Unauthorized"}})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await paddle.create_checkout_url(
            settings, price_id="pri_plus", telegram_id=1
        )


# ---------------------------------------------------------------------------
# update_subscription_price / cancel_subscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_update_subscription_price_patches_with_proration():
    settings = _settings(api_key="k")
    captured: list[dict] = []

    def _capture(request):
        captured.append(json.loads(request.content))
        return Response(200, json={"data": {"id": "sub_1"}})

    respx.patch(f"{_API_BASE}/subscriptions/sub_1").mock(side_effect=_capture)

    await paddle.update_subscription_price(
        settings, subscription_id="sub_1", price_id="pri_pro"
    )

    body = captured[0]
    assert body["items"] == [{"price_id": "pri_pro", "quantity": 1}]
    assert body["proration_billing_mode"] == "prorated_immediately"


@pytest.mark.asyncio
@respx.mock
async def test_update_subscription_price_raises_on_http_error():
    settings = _settings(api_key="k")
    respx.patch(f"{_API_BASE}/subscriptions/sub_1").mock(
        return_value=Response(422, json={"error": {}})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await paddle.update_subscription_price(
            settings, subscription_id="sub_1", price_id="pri_pro"
        )


@pytest.mark.asyncio
@respx.mock
async def test_cancel_subscription_posts_next_billing_period():
    settings = _settings(api_key="k")
    captured: list[dict] = []

    def _capture(request):
        captured.append(json.loads(request.content))
        return Response(200, json={"data": {"id": "sub_9"}})

    route = respx.post(f"{_API_BASE}/subscriptions/sub_9/cancel").mock(
        side_effect=_capture
    )

    await paddle.cancel_subscription(settings, subscription_id="sub_9")

    assert route.called
    assert captured[0] == {"effective_from": "next_billing_period"}


@pytest.mark.asyncio
@respx.mock
async def test_cancel_subscription_raises_on_http_error():
    settings = _settings(api_key="k")
    respx.post(f"{_API_BASE}/subscriptions/sub_9/cancel").mock(
        return_value=Response(404, json={})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await paddle.cancel_subscription(settings, subscription_id="sub_9")


# ---------------------------------------------------------------------------
# verify_signature
# ---------------------------------------------------------------------------


def _build_signature(secret: str, body: bytes, ts: int | None = None) -> str:
    if ts is None:
        ts = int(time.time())
    signed = f"{ts}:".encode() + body
    h = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h}"


def test_verify_signature_accepts_valid():
    secret = "wh_secret"
    body = b'{"event_type":"subscription.created"}'
    header = _build_signature(secret, body)
    assert paddle.verify_signature(SecretStr(secret), header, body) is True


def test_verify_signature_rejects_tampered_body():
    secret = "wh_secret"
    body = b'{"event_type":"subscription.created"}'
    header = _build_signature(secret, body)
    tampered = b'{"event_type":"subscription.canceled"}'
    assert paddle.verify_signature(SecretStr(secret), header, tampered) is False


def test_verify_signature_rejects_wrong_secret():
    body = b"{}"
    header = _build_signature("real_secret", body)
    assert (
        paddle.verify_signature(SecretStr("wrong_secret"), header, body) is False
    )


def test_verify_signature_rejects_stale_timestamp():
    secret = "wh_secret"
    body = b"{}"
    old_ts = int(time.time()) - 3600  # 1h old, far past max_age_seconds=300
    header = _build_signature(secret, body, ts=old_ts)
    assert paddle.verify_signature(SecretStr(secret), header, body) is False


def test_verify_signature_rejects_malformed_header():
    assert paddle.verify_signature(SecretStr("k"), "garbage", b"{}") is False
    assert paddle.verify_signature(SecretStr("k"), "ts=abc;h1=xyz", b"{}") is False
    assert paddle.verify_signature(SecretStr("k"), "", b"{}") is False


# ---------------------------------------------------------------------------
# cb_plan_paid — real URL path
# ---------------------------------------------------------------------------


def _make_callback_update(tg_id: int, cb_data: str) -> MagicMock:
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = tg_id
    update.callback_query = MagicMock()
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    update.callback_query.data = cb_data
    return update


def _make_context(session) -> MagicMock:
    @asynccontextmanager
    async def _scope():
        yield session

    ctx = MagicMock()
    ctx.bot_data = {"session_scope": _scope}
    ctx.user_data = {}
    return ctx


@pytest.mark.asyncio
async def test_cb_plan_paid_placeholder_when_no_api_key(db_session, monkeypatch):
    from jyry.bot.handlers import plans as ph

    monkeypatch.setattr(ph, "get_settings", lambda: _make_settings(api_key=None))

    update = _make_callback_update(tg_id=10, cb_data=CB["plan_plus"])
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_PLACEHOLDER


@pytest.mark.asyncio
@respx.mock
async def test_cb_plan_paid_shows_checkout_link(db_session, monkeypatch):
    from jyry.bot.handlers import plans as ph

    s = _make_settings(api_key="k", price_plus="pri_b")
    monkeypatch.setattr(ph, "get_settings", lambda: s)

    respx.post(f"{_API_BASE}/transactions").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "id": "txn",
                    "checkout": {"url": "https://checkout.test/abc"},
                }
            },
        )
    )

    update = _make_callback_update(tg_id=11, cb_data=CB["plan_plus"])
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_READY
    kb = update.callback_query.edit_message_text.call_args[1]["reply_markup"]
    first_btn = kb.inline_keyboard[0][0]
    assert first_btn.url == "https://checkout.test/abc"


@pytest.mark.asyncio
@respx.mock
async def test_cb_plan_paid_fallback_on_api_error(db_session, monkeypatch):
    from jyry.bot.handlers import plans as ph

    s = _make_settings(api_key="k", price_pro="pri_p")
    monkeypatch.setattr(ph, "get_settings", lambda: s)

    respx.post(f"{_API_BASE}/transactions").mock(
        return_value=Response(500, json={})
    )

    update = _make_callback_update(tg_id=12, cb_data=CB["plan_pro"])
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_PLACEHOLDER


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(*, api_key: str) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.paddle_api_base = _API_BASE
    s.paddle_api_key = SecretStr(api_key)
    return s


def _make_settings(
    *,
    api_key: str | None = None,
    price_plus: str | None = None,
    price_pro: str | None = None,
    price_max: str | None = None,
) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.paddle_api_base = _API_BASE
    s.paddle_api_key = SecretStr(api_key) if api_key else None
    s.paddle_price_plus = price_plus
    s.paddle_price_pro = price_pro
    s.paddle_price_max = price_max
    return s
