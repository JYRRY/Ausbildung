"""Tests for jyry.payments.lemonsqueezy and the updated cb_plan_paid."""

from __future__ import annotations

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
from jyry.payments import lemonsqueezy

# ---------------------------------------------------------------------------
# create_checkout_url
# ---------------------------------------------------------------------------


def _settings_with_ls(
    *,
    api_key: str = "test-key",
    store_id: str = "store-1",
    variant_plus: str = "var-plus",
    variant_pro: str = "var-pro",
    variant_max: str = "var-max",
) -> Settings:
    from tests.conftest import _set_test_env

    _set_test_env()
    from jyry.config import get_settings

    get_settings.cache_clear()
    import os

    os.environ["LEMONSQUEEZY_API_KEY"] = api_key
    os.environ["LEMONSQUEEZY_STORE_ID"] = store_id
    os.environ["LEMONSQUEEZY_VARIANT_PLUS"] = variant_plus
    os.environ["LEMONSQUEEZY_VARIANT_PRO"] = variant_pro
    os.environ["LEMONSQUEEZY_VARIANT_MAX"] = variant_max
    s = get_settings()
    get_settings.cache_clear()
    return s


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_returns_url():
    settings = _settings_with_ls()
    respx.post("https://api.lemonsqueezy.com/v1/checkouts").mock(
        return_value=Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "url": "https://jyry.lemonsqueezy.com/checkout/buy/abc123"
                    }
                }
            },
        )
    )

    url = await lemonsqueezy.create_checkout_url(
        settings, variant_id="var-plus", telegram_id=42
    )

    assert url == "https://jyry.lemonsqueezy.com/checkout/buy/abc123"


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_sends_telegram_id():
    import json

    settings = _settings_with_ls()
    captured: list[dict] = []

    def _capture(request, route):
        captured.append(json.loads(request.content))
        return Response(
            200,
            json={
                "data": {
                    "attributes": {
                        "url": "https://example.com/checkout"
                    }
                }
            },
        )

    respx.post("https://api.lemonsqueezy.com/v1/checkouts").mock(side_effect=_capture)

    await lemonsqueezy.create_checkout_url(settings, variant_id="var-pro", telegram_id=99)

    custom = captured[0]["data"]["attributes"]["checkout_data"]["custom"]
    assert custom["telegram_id"] == "99"


# ---------------------------------------------------------------------------
# update_subscription_variant / cancel_subscription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@respx.mock
async def test_update_subscription_variant_patches_with_invoice_immediately():
    import json

    settings = _settings_with_ls()
    captured: list[dict] = []

    def _capture(request, route):
        captured.append(json.loads(request.content))
        return Response(200, json={"data": {"id": "sub-1"}})

    respx.patch("https://api.lemonsqueezy.com/v1/subscriptions/sub-1").mock(
        side_effect=_capture
    )

    await lemonsqueezy.update_subscription_variant(
        settings, subscription_id="sub-1", variant_id="var-pro"
    )

    attrs = captured[0]["data"]["attributes"]
    assert attrs["variant_id"] == "var-pro"
    assert attrs["invoice_immediately"] is True


@pytest.mark.asyncio
@respx.mock
async def test_update_subscription_variant_raises_on_http_error():
    settings = _settings_with_ls()
    respx.patch("https://api.lemonsqueezy.com/v1/subscriptions/sub-1").mock(
        return_value=Response(422, json={"errors": []})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await lemonsqueezy.update_subscription_variant(
            settings, subscription_id="sub-1", variant_id="var-pro"
        )


@pytest.mark.asyncio
@respx.mock
async def test_cancel_subscription_sends_delete():
    settings = _settings_with_ls()
    route = respx.delete(
        "https://api.lemonsqueezy.com/v1/subscriptions/sub-9"
    ).mock(return_value=Response(204))

    await lemonsqueezy.cancel_subscription(settings, subscription_id="sub-9")

    assert route.called


@pytest.mark.asyncio
@respx.mock
async def test_cancel_subscription_raises_on_http_error():
    settings = _settings_with_ls()
    respx.delete("https://api.lemonsqueezy.com/v1/subscriptions/sub-9").mock(
        return_value=Response(404, json={})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await lemonsqueezy.cancel_subscription(settings, subscription_id="sub-9")


@pytest.mark.asyncio
@respx.mock
async def test_create_checkout_url_raises_on_http_error():
    settings = _settings_with_ls()
    respx.post("https://api.lemonsqueezy.com/v1/checkouts").mock(
        return_value=Response(401, json={"errors": [{"detail": "Unauthorized"}]})
    )

    with pytest.raises(httpx.HTTPStatusError):
        await lemonsqueezy.create_checkout_url(
            settings, variant_id="var-plus", telegram_id=1
        )


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

    s = _make_settings(api_key="k", variant_plus="var-b")
    monkeypatch.setattr(ph, "get_settings", lambda: s)

    respx.post("https://api.lemonsqueezy.com/v1/checkouts").mock(
        return_value=Response(
            200,
            json={"data": {"attributes": {"url": "https://checkout.test/abc"}}},
        )
    )

    update = _make_callback_update(tg_id=11, cb_data=CB["plan_plus"])
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_READY
    kb = update.callback_query.edit_message_text.call_args[1]["reply_markup"]
    # First button must be a URL button pointing to the checkout
    first_btn = kb.inline_keyboard[0][0]
    assert first_btn.url == "https://checkout.test/abc"


@pytest.mark.asyncio
@respx.mock
async def test_cb_plan_paid_fallback_on_api_error(db_session, monkeypatch):
    from jyry.bot.handlers import plans as ph

    s = _make_settings(api_key="k", variant_pro="var-p")
    monkeypatch.setattr(ph, "get_settings", lambda: s)

    respx.post("https://api.lemonsqueezy.com/v1/checkouts").mock(
        return_value=Response(500, json={})
    )

    update = _make_callback_update(tg_id=12, cb_data=CB["plan_pro"])
    ctx = _make_context(db_session)

    await plans_handler.cb_plan_paid(update, ctx)

    text = update.callback_query.edit_message_text.call_args[0][0]
    assert text == messages.PLAN_CHECKOUT_PLACEHOLDER


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _make_settings(
    *,
    api_key: str | None = None,
    variant_plus: str | None = None,
    variant_pro: str | None = None,
    variant_max: str | None = None,
) -> MagicMock:
    s = MagicMock(spec=Settings)
    s.lemonsqueezy_api_key = SecretStr(api_key) if api_key else None
    s.lemonsqueezy_store_id = "store-1" if api_key else None
    s.lemonsqueezy_variant_plus = variant_plus
    s.lemonsqueezy_variant_pro = variant_pro
    s.lemonsqueezy_variant_max = variant_max
    return s
