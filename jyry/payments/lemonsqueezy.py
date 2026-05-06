"""Lemon Squeezy API client — checkout URL generation."""
from __future__ import annotations

import httpx

from jyry.config import Settings

_LS_API_BASE = "https://api.lemonsqueezy.com/v1"


async def create_checkout_url(
    settings: Settings,
    *,
    variant_id: str,
    telegram_id: int,
) -> str:
    """Create a Lemon Squeezy checkout session and return the redirect URL."""
    assert settings.lemonsqueezy_api_key is not None, "API key not configured"
    assert settings.lemonsqueezy_store_id is not None, "Store ID not configured"

    api_key = settings.lemonsqueezy_api_key.get_secret_value()

    payload = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "checkout_data": {
                    "custom": {
                        "telegram_id": str(telegram_id),
                    }
                },
            },
            "relationships": {
                "store": {
                    "data": {
                        "type": "stores",
                        "id": settings.lemonsqueezy_store_id,
                    }
                },
                "variant": {
                    "data": {
                        "type": "variants",
                        "id": variant_id,
                    }
                },
            },
        }
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            f"{_LS_API_BASE}/checkouts",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/vnd.api+json",
                "Content-Type": "application/vnd.api+json",
            },
            json=payload,
        )
        resp.raise_for_status()

    return str(resp.json()["data"]["attributes"]["url"])
