"""Web-side Paddle checkout: build a hosted URL and 302 the user to it.

Mirrors the bot's flow (jyry.bot.handlers.plans.cb_plan_paid) but runs in
the FastAPI dashboard process. The hosted Paddle checkout itself handles
payment + T&Cs; the existing webhook (jyry.payments.webhook) is what
actually flips the user's subscription row.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse

from jyry.config import Settings
from jyry.db.models import User
from jyry.payments import paddle
from jyry.webapp.deps import get_app_settings, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["checkout"])

_PLANS = {"plus", "pro", "max"}


def _price_id_for(settings: Settings, plan: str) -> str | None:
    return {
        "plus": settings.paddle_price_plus,
        "pro": settings.paddle_price_pro,
        "max": settings.paddle_price_max,
    }.get(plan)


@router.get("/checkout")
async def checkout(
    plan: str = Query(..., description="plus | pro | max"),
    settings: Settings = Depends(get_app_settings),
    user: User = Depends(get_current_user),
) -> RedirectResponse:
    if plan not in _PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"plan must be one of {sorted(_PLANS)}",
        )

    price_id = _price_id_for(settings, plan)
    if price_id is None or settings.paddle_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Paddle is not configured on this environment.",
        )

    try:
        url = await paddle.create_checkout_url(
            settings, price_id=price_id, user_id=user.id
        )
    except Exception:
        logger.exception(
            "Paddle checkout failed user_id=%s plan=%s", user.id, plan
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Konnte Bezahlseite nicht erstellen — bitte später erneut versuchen.",
        ) from None

    return RedirectResponse(url=url, status_code=302)
