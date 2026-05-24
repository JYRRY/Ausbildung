"""Paddle Billing API client — checkout URLs, subscription updates, signature verification."""
from __future__ import annotations

import hashlib
import hmac
import time

import httpx
from pydantic import SecretStr

from jyry.config import Settings


async def create_checkout_url(
    settings: Settings,
    *,
    price_id: str,
    telegram_id: int,
) -> str:
    """Create a Paddle transaction and return its hosted checkout URL.

    The Telegram user ID is stashed in ``custom_data`` so subsequent
    ``subscription.*`` webhook events can be attributed back to the user.
    """
    assert settings.paddle_api_key is not None, "Paddle API key not configured"

    payload = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "custom_data": {"telegram_id": str(telegram_id)},
        "collection_mode": "automatic",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.paddle_api_base}/transactions",
            headers=_headers(settings),
            json=payload,
        )
        resp.raise_for_status()

    return str(resp.json()["data"]["checkout"]["url"])


async def update_subscription_price(
    settings: Settings,
    *,
    subscription_id: str,
    price_id: str,
) -> None:
    """Switch a live subscription to a new price with immediate proration.

    Paddle charges the prorated delta to the saved payment method on the spot
    when ``proration_billing_mode`` is ``prorated_immediately``.
    """
    assert settings.paddle_api_key is not None, "Paddle API key not configured"

    payload = {
        "items": [{"price_id": price_id, "quantity": 1}],
        "proration_billing_mode": "prorated_immediately",
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.patch(
            f"{settings.paddle_api_base}/subscriptions/{subscription_id}",
            headers=_headers(settings),
            json=payload,
        )
        resp.raise_for_status()


async def cancel_subscription(
    settings: Settings,
    *,
    subscription_id: str,
) -> None:
    """Cancel auto-renewal at the end of the current period. Paddle keeps the
    subscription active until ``current_billing_period.ends_at`` and then
    transitions it to ``canceled``."""
    assert settings.paddle_api_key is not None, "Paddle API key not configured"

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{settings.paddle_api_base}/subscriptions/{subscription_id}/cancel",
            headers=_headers(settings),
            json={"effective_from": "next_billing_period"},
        )
        resp.raise_for_status()


def verify_signature(
    secret: SecretStr,
    header: str,
    body: bytes,
    *,
    max_age_seconds: int = 300,
) -> bool:
    """Verify a Paddle webhook signature.

    Paddle's ``Paddle-Signature`` header has the form ``ts=<unix>;h1=<hex>``.
    The signed payload is ``<ts>:<raw_body>`` and the digest is HMAC-SHA256
    with the endpoint's signing secret.

    Rejects timestamps older than ``max_age_seconds`` to neutralise replay
    attacks where an attacker captures a valid request and replays it later.
    """
    parts = dict(
        part.split("=", 1) for part in header.split(";") if "=" in part
    )
    ts = parts.get("ts")
    h1 = parts.get("h1")
    if ts is None or h1 is None:
        return False

    try:
        ts_int = int(ts)
    except ValueError:
        return False

    if abs(time.time() - ts_int) > max_age_seconds:
        return False

    signed_payload = f"{ts}:".encode() + body
    expected = hmac.new(
        secret.get_secret_value().encode(),
        signed_payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(h1, expected)


def _headers(settings: Settings) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.paddle_api_key.get_secret_value()}",  # type: ignore[union-attr]
        "Content-Type": "application/json",
        "Paddle-Version": "1",
    }
