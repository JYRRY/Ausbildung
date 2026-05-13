"""Outbound Telegram notification helper for the webhook process.

The webhook runs in a separate process from ``jyry-bot`` and does not have
access to a PTB ``Application`` instance, so we call the Telegram Bot API
directly via HTTP.
"""

from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)

_API_BASE = "https://api.telegram.org"
_TIMEOUT = httpx.Timeout(10.0)


async def send_telegram_notice(
    *, token: str, chat_id: int, text: str, parse_mode: str = "Markdown"
) -> bool:
    """Send a single message via the Telegram Bot API.

    Returns True on HTTP 2xx with ``ok=true``; False otherwise. Never raises —
    notification failures must not break the webhook 200 response.
    """
    url = f"{_API_BASE}/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            logger.warning(
                "telegram notice failed: chat_id=%s status=%s body=%s",
                chat_id,
                resp.status_code,
                resp.text[:300],
            )
            return False
        body = resp.json()
        if not body.get("ok", False):
            logger.warning("telegram notice not ok: chat_id=%s body=%s", chat_id, body)
            return False
        return True
    except Exception:  # pragma: no cover — defensive
        logger.exception("telegram notice raised: chat_id=%s", chat_id)
        return False
