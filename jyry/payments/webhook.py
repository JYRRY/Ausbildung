"""Paddle webhook receiver — signature-verified FastAPI app."""
from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from jyry.config import get_settings
from jyry.db.session import session_scope
from jyry.payments import paddle
from jyry.payments.handlers import dispatch_event

logger = logging.getLogger(__name__)

app = FastAPI(title="JYRY AI Webhook", docs_url=None, redoc_url=None)


async def _db_session() -> AsyncIterator[AsyncSession]:
    async with session_scope() as session:
        yield session


@app.post("/webhook/paddle")
async def paddle_webhook(
    request: Request,
    session: AsyncSession = Depends(_db_session),
) -> dict[str, bool]:
    body = await request.body()

    settings = get_settings()
    secret = settings.paddle_webhook_secret
    if secret is not None:
        sig_header = request.headers.get("Paddle-Signature", "")
        if not paddle.verify_signature(secret, sig_header, body):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid signature",
            )

    try:
        payload: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON",
        ) from exc

    event_type: str = payload.get("event_type", "")
    logger.info("Received Paddle event: %s", event_type)

    await dispatch_event(session, event_type, payload)

    return {"ok": True}


def run() -> None:
    logging.basicConfig(
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    uvicorn.run(
        "jyry.payments.webhook:app",
        host=settings.webhook_host,
        port=settings.webhook_port,
        reload=False,
    )
