"""Tests for jyry.payments.webhook — HMAC verification and event routing."""

from __future__ import annotations

import hashlib
import hmac
import json
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


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _ls_payload(
    event: str,
    *,
    tg_id: int,
    ls_sub_id: str = "sub-1",
    variant_id: str = "var-plus",
    customer_id: str = "cust-1",
    status: str = "active",
    renews_at: str | None = None,
    ends_at: str | None = None,
) -> bytes:
    data: dict = {
        "meta": {
            "event_name": event,
            "custom_data": {"telegram_id": str(tg_id)},
        },
        "data": {
            "id": ls_sub_id,
            "type": "subscriptions",
            "attributes": {
                "variant_id": variant_id,
                "customer_id": customer_id,
                "status": status,
                "renews_at": renews_at,
                "ends_at": ends_at,
            },
        },
    }
    return json.dumps(data).encode()


# ---------------------------------------------------------------------------
# HMAC verification
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_no_secret_accepts_any_request(client):
    """When LEMONSQUEEZY_WEBHOOK_SECRET is not set, requests pass through."""
    body = _ls_payload("unknown_event", tg_id=1)
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_signature_rejected(monkeypatch, client, settings):
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", _make_secret("mysecret"))
    from jyry.payments import webhook as wh_module

    monkeypatch.setattr(wh_module, "get_settings", lambda: settings)

    body = _ls_payload("subscription_created", tg_id=2)
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": "badsig"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_valid_signature_accepted(monkeypatch, client, settings):
    secret = "mysecret"
    monkeypatch.setattr(settings, "lemonsqueezy_webhook_secret", _make_secret(secret))
    from jyry.payments import webhook as wh_module

    monkeypatch.setattr(wh_module, "get_settings", lambda: settings)

    body = _ls_payload("subscription_created", tg_id=3)
    sig = _sign(secret, body)
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_invalid_json_returns_400(client):
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=b"not-json",
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Event routing → DB state
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscription_created_upserts_db(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "lemonsqueezy_variant_plus", "var-plus")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    body = _ls_payload(
        "subscription_created",
        tg_id=100,
        ls_sub_id="sub-42",
        variant_id="var-plus",
        customer_id="cust-100",
        status="active",
        renews_at="2026-06-01T00:00:00Z",
    )
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).join(Subscription.user).where(
                Subscription.lemonsqueezy_subscription_id == "sub-42"
            )
        )
    ).scalar_one()
    assert sub.plan == Plan.PLUS
    assert sub.status == SubscriptionStatus.ACTIVE
    assert sub.lemonsqueezy_customer_id == "cust-100"
    assert sub.expires_at is not None


@pytest.mark.asyncio
async def test_subscription_cancelled_sets_status(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "lemonsqueezy_variant_plus", "var-plus")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    ends = (datetime.now(tz=UTC) + timedelta(days=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = _ls_payload(
        "subscription_cancelled",
        tg_id=101,
        ls_sub_id="sub-43",
        variant_id="var-plus",
        status="cancelled",
        ends_at=ends,
    )
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == "sub-43"
            )
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.CANCELLED
    assert sub.expires_at is not None


@pytest.mark.asyncio
async def test_subscription_expired_sets_status(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "lemonsqueezy_variant_pro", "var-pro")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    body = _ls_payload(
        "subscription_expired",
        tg_id=102,
        ls_sub_id="sub-44",
        variant_id="var-pro",
        status="expired",
    )
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == "sub-44"
            )
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.EXPIRED


@pytest.mark.asyncio
async def test_payment_failed_sets_past_due(client, db_session, monkeypatch, settings):
    monkeypatch.setattr(settings, "lemonsqueezy_variant_max", "var-max")
    from jyry.payments import handlers as h_module

    monkeypatch.setattr(h_module, "get_settings", lambda: settings)

    body = _ls_payload(
        "subscription_payment_failed",
        tg_id=103,
        ls_sub_id="sub-45",
        variant_id="var-max",
        status="past_due",
    )
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200

    sub = (
        await db_session.execute(
            select(Subscription).where(
                Subscription.lemonsqueezy_subscription_id == "sub-45"
            )
        )
    ).scalar_one()
    assert sub.status == SubscriptionStatus.PAST_DUE


@pytest.mark.asyncio
async def test_unknown_event_returns_200(client):
    body = _ls_payload("order_created", tg_id=104)
    resp = await client.post(
        "/webhook/lemonsqueezy",
        content=body,
        headers={"Content-Type": "application/json"},
    )
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_missing_telegram_id_ignored(client, db_session):
    payload = {
        "meta": {"event_name": "subscription_created", "custom_data": {}},
        "data": {
            "id": "sub-99",
            "type": "subscriptions",
            "attributes": {
                "variant_id": "var-plus",
                "customer_id": "cust-99",
                "status": "active",
                "renews_at": None,
                "ends_at": None,
            },
        },
    }
    resp = await client.post(
        "/webhook/lemonsqueezy",
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
        lemonsqueezy_subscription_id="ls-1",
        lemonsqueezy_customer_id="cust-200",
        daily_quota=30,
    )
    assert sub.plan == Plan.PLUS
    assert sub.daily_quota == 30
    assert sub.lemonsqueezy_subscription_id == "ls-1"

    sub2 = await repos.upsert_subscription(
        db_session,
        telegram_id=200,
        plan=Plan.PRO,
        status=SubscriptionStatus.ACTIVE,
        expires_at=datetime(2027, 3, 31, tzinfo=UTC),
        lemonsqueezy_subscription_id="ls-1",
        lemonsqueezy_customer_id="cust-200",
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
