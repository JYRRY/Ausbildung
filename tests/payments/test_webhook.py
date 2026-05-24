"""Tests for jyry.payments.webhook — Paddle signature verification and event routing."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from jyry.bot import repos
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.models import Subscription
from jyry.payments.webhook import _db_session, app


@pytest_asyncio.fixture
async def client(db_session) -> AsyncIterator[AsyncClient]:
    async def _override() -> AsyncIterator:
        yield db_session

    app.dependency_overrides[_db_session] = _override
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


def _sign(secret: str, body: bytes, ts: int | None = None) -> str:
    """Build a Paddle-Signature header value."""
    if ts is None:
        ts = int(time.time())
    signed = f"{ts}:".encode() + body
    h = hmac.new(secret.encode(), signed, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h}"


def _paddle_payload(
    event_type: str,
    *,
    tg_id: int,
    sub_id: str = "sub_1",
    price_id: str = "pri_plus",
    customer_id: str = "cust_1",
    status: str = "active",
    period_ends_at: str | None = None,
    canceled_at: str | None = None,
) -> bytes:
    data: dict = {
        "event_type": event_type,
        "data": {
            "id": sub_id,
            "status": status,
            "customer_id": customer_id,
            "custom_data": {"telegram_id": str(tg_id)},
            "items": [
                {
                    "price": {"id": price_id},
                    "quantity": 1,
                }
            ],
            "current_billing_period": (
                {"ends_at": period_ends_at} if period_ends_at else None
            ),
            "canceled_at": canceled_at,
        },
    }
    return json.dumps(data).encode()


# ---------------------------------------------------------------------------
# Signature verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_secret_accepts_any_request(client):
    """When PADDLE_WEBHOOK_SECRET is not set, requests pass through."""
    body = _paddle_payload("unknown.event", tg_id=1)
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_signature_rejected(monkeypatch, client, settings):
    monkeypatch.setattr(settings, "paddle_webhook_secret", _make_secret("mysecret"))
    from jyry.payments import webhook as wh_module

    monkeypatch.setattr(wh_module, "get_settings", lambda: settings)

    body = _paddle_payload("subscription.created", tg_id=2)
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={
            "Content-Type": "application/json",
            "Paddle-Signature": "ts=1;h1=deadbeef",
        },
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_signature_accepted(monkeypatch, client, settings):
    secret = "mysecret"
    monkeypatch.setattr(settings, "paddle_webhook_secret", _make_secret(secret))
    from jyry.payments import webhook as wh_module

    monkeypatch.setattr(wh_module, "get_settings", lambda: settings)

    body = _paddle_payload("subscription.created", tg_id=3)
    sig = _sign(secret, body)
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json", "Paddle-Signature": sig},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_json_returns_400(client):
    resp = await client.post(
        "/webhook/paddle",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Event routing → DB state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_created_upserts_db(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "paddle_price_plus", "pri_plus")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    body = _paddle_payload(
        "subscription.created",
        tg_id=100,
        sub_id="sub_42",
        price_id="pri_plus",
        customer_id="cust_100",
        status="active",
        period_ends_at="2026-06-01T00:00:00Z",
    )
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).join(Subscription.user).where(
                Subscription.paddle_subscription_id == "sub_42"
            )
        )
    ).scalar_one()
    assert sub.plan == Plan.PLUS
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.paddle_customer_id == "cust_100"
    assert sub.expires_at is not None


@pytest.mark.asyncio
async def test_subscription_created_sends_telegram_notice(
    client, db_session, monkeypatch, settings
):
    monkeypatch.setattr(settings, "paddle_price_plus", "pri_plus")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    calls: list[dict] = []

    async def _fake_send(*, token, chat_id, text, parse_mode="Markdown"):
        calls.append({"token": token, "chat_id": chat_id, "text": text})
        return True

    monkeypatch.setattr(h_module, "send_telegram_notice", _fake_send)

    body = _paddle_payload(
        "subscription.created",
        tg_id=500,
        sub_id="sub_500",
        price_id="pri_plus",
    )
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert len(calls) == 1
    assert calls[0]["chat_id"] == 500
    assert "Plus" in calls[0]["text"]
    assert "30 Bewerbungen/Tag" in calls[0]["text"]
    assert "Status" in calls[0]["text"]


@pytest.mark.asyncio
async def test_subscription_updated_does_not_send_notice(
    client, db_session, monkeypatch, settings
):
    monkeypatch.setattr(settings, "paddle_price_pro", "pri_pro")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    calls: list[dict] = []

    async def _fake_send(**kwargs):
        calls.append(kwargs)
        return True

    monkeypatch.setattr(h_module, "send_telegram_notice", _fake_send)

    body = _paddle_payload(
        "subscription.updated",
        tg_id=501,
        sub_id="sub_501",
        price_id="pri_pro",
    )
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    assert calls == []


@pytest.mark.asyncio
async def test_subscription_canceled_sets_status(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "paddle_price_plus", "pri_plus")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    ends = (datetime.now(tz=UTC) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = _paddle_payload(
        "subscription.canceled",
        tg_id=101,
        sub_id="sub_43",
        price_id="pri_plus",
        status="canceled",
        period_ends_at=ends,
    )
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.paddle_subscription_id == "sub_43"
            )
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.CANCELLED
    assert sub.expires_at is not None


@pytest.mark.asyncio
async def test_payment_failed_sets_past_due(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "paddle_price_max", "pri_max")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    body = _paddle_payload(
        "subscription.past_due",
        tg_id=103,
        sub_id="sub_45",
        price_id="pri_max",
        status="past_due",
    )
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.paddle_subscription_id == "sub_45"
            )
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_unknown_event_returns_200(client):
    body = _paddle_payload("transaction.completed", tg_id=104)
    resp = await client.post(
        "/webhook/paddle",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_telegram_id_ignored(client, db_session):
    payload = {
        "event_type": "subscription.created",
        "data": {
            "id": "sub_99",
            "status": "active",
            "customer_id": "cust_99",
            "custom_data": {},
            "items": [{"price": {"id": "pri_plus"}, "quantity": 1}],
        },
    }
    resp = await client.post(
        "/webhook/paddle",
        content=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200
    result = await db_session.execute(select(Subscription))
    assert result.scalars().all() == []


# ---------------------------------------------------------------------------
# repos.upsert_subscription round-trip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upsert_subscription_creates_and_updates(db_session):
    sub = await repos.upsert_subscription(
        db_session,
        telegram_id=200,
        plan=Plan.PLUS,
        status=SubscriptionStatus.ACTIVE,
        expires_at=datetime(2026, 12, 31, tzinfo=UTC),
        paddle_subscription_id="sub_1",
        paddle_customer_id="cust_200",
        daily_quota=30,
    )
    assert sub.plan == Plan.PLUS
    assert sub.daily_quota == 30
    assert sub.paddle_subscription_id == "sub_1"

    sub2 = await repos.upsert_subscription(
        db_session,
        telegram_id=200,
        plan=Plan.PRO,
        status=SubscriptionStatus.ACTIVE,
        expires_at=datetime(2027, 3, 31, tzinfo=UTC),
        paddle_subscription_id="sub_1",
        paddle_customer_id="cust_200",
        daily_quota=100,
    )
    assert sub2.id == sub.id
    assert sub2.plan == Plan.PRO
    assert sub2.daily_quota == 100


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_secret(value: str):
    from pydantic import SecretStr

    return SecretStr(value)
