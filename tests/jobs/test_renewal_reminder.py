"""Tests for jyry.jobs.renewal_reminder.run_renewal_reminder."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

import pytest

from jyry.bot import repos
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.jobs import renewal_reminder as rr_module
from jyry.jobs.renewal_reminder import run_renewal_reminder


@asynccontextmanager
async def _scope_factory(session) -> AsyncIterator:
    yield session


def _make_scope(session):
    def _scope():
        return _scope_factory(session)

    return _scope


@pytest.mark.asyncio
async def test_sends_reminder_for_active_paid_in_window(
    db_session, monkeypatch
) -> None:
    sent_calls: list[dict] = []

    async def _fake_send(*, token, chat_id, text, parse_mode="Markdown"):
        sent_calls.append(
            {"token": token, "chat_id": chat_id, "text": text}
        )
        return True

    monkeypatch.setattr(rr_module, "send_telegram_notice", _fake_send)

    now = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    # 3.5 days from now → within [now+3d, now+4d) window.
    in_window = now + timedelta(days=3, hours=12)
    await repos.upsert_subscription(
        db_session,
        telegram_id=5001,
        plan=Plan.PLUS,
        status=SubscriptionStatus.ACTIVE,
        expires_at=in_window,
        lemonsqueezy_subscription_id="sub-w",
        lemonsqueezy_customer_id="cust-w",
        daily_quota=30,
    )
    await db_session.commit()

    count = await run_renewal_reminder(
        token="t", session_scope=_make_scope(db_session), now=now
    )
    assert count == 1
    assert len(sent_calls) == 1
    assert sent_calls[0]["chat_id"] == 5001
    assert "Plus" in sent_calls[0]["text"]
    assert "14,99" in sent_calls[0]["text"]
    assert "3 Tagen" in sent_calls[0]["text"]


@pytest.mark.asyncio
async def test_skips_free_plan(db_session, monkeypatch) -> None:
    sent_calls: list[dict] = []

    async def _fake_send(**kwargs):
        sent_calls.append(kwargs)
        return True

    monkeypatch.setattr(rr_module, "send_telegram_notice", _fake_send)

    now = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    await repos.upsert_subscription(
        db_session,
        telegram_id=5002,
        plan=Plan.FREE,
        status=SubscriptionStatus.ACTIVE,
        expires_at=now + timedelta(days=3, hours=6),
        lemonsqueezy_subscription_id=None,
        lemonsqueezy_customer_id=None,
        daily_quota=5,
    )
    await db_session.commit()

    count = await run_renewal_reminder(
        token="t", session_scope=_make_scope(db_session), now=now
    )
    assert count == 0
    assert sent_calls == []


@pytest.mark.asyncio
async def test_skips_cancelled_status(db_session, monkeypatch) -> None:
    sent_calls: list[dict] = []

    async def _fake_send(**kwargs):
        sent_calls.append(kwargs)
        return True

    monkeypatch.setattr(rr_module, "send_telegram_notice", _fake_send)

    now = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    await repos.upsert_subscription(
        db_session,
        telegram_id=5003,
        plan=Plan.PRO,
        status=SubscriptionStatus.CANCELLED,
        expires_at=now + timedelta(days=3, hours=6),
        lemonsqueezy_subscription_id="sub-c",
        lemonsqueezy_customer_id="cust-c",
        daily_quota=100,
    )
    await db_session.commit()

    count = await run_renewal_reminder(
        token="t", session_scope=_make_scope(db_session), now=now
    )
    assert count == 0
    assert sent_calls == []


@pytest.mark.asyncio
async def test_skips_outside_window(db_session, monkeypatch) -> None:
    sent_calls: list[dict] = []

    async def _fake_send(**kwargs):
        sent_calls.append(kwargs)
        return True

    monkeypatch.setattr(rr_module, "send_telegram_notice", _fake_send)

    now = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    # Too far ahead (10 days).
    await repos.upsert_subscription(
        db_session,
        telegram_id=5004,
        plan=Plan.MAX,
        status=SubscriptionStatus.ACTIVE,
        expires_at=now + timedelta(days=10),
        lemonsqueezy_subscription_id="sub-far",
        lemonsqueezy_customer_id="cust-far",
        daily_quota=100,
    )
    # Already past renewal (1 day).
    await repos.upsert_subscription(
        db_session,
        telegram_id=5005,
        plan=Plan.PLUS,
        status=SubscriptionStatus.ACTIVE,
        expires_at=now + timedelta(days=1),
        lemonsqueezy_subscription_id="sub-near",
        lemonsqueezy_customer_id="cust-near",
        daily_quota=30,
    )
    await db_session.commit()

    count = await run_renewal_reminder(
        token="t", session_scope=_make_scope(db_session), now=now
    )
    assert count == 0
    assert sent_calls == []


@pytest.mark.asyncio
async def test_counts_only_successful_sends(db_session, monkeypatch) -> None:
    async def _fake_send(**kwargs):
        # Fail every send.
        return False

    monkeypatch.setattr(rr_module, "send_telegram_notice", _fake_send)

    now = datetime(2026, 5, 13, 9, 0, tzinfo=UTC)
    await repos.upsert_subscription(
        db_session,
        telegram_id=5006,
        plan=Plan.MAX,
        status=SubscriptionStatus.ACTIVE,
        expires_at=now + timedelta(days=3, hours=2),
        lemonsqueezy_subscription_id="sub-fail",
        lemonsqueezy_customer_id="cust-fail",
        daily_quota=100,
    )
    await db_session.commit()

    count = await run_renewal_reminder(
        token="t", session_scope=_make_scope(db_session), now=now
    )
    assert count == 0
