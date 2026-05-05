"""Tests for jyry.services.rate_limiter."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import fakeredis.aioredis
import pytest
import pytest_asyncio

from jyry.services.rate_limiter import DailyQuotaLimiter


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture
async def limiter(redis, settings):
    return DailyQuotaLimiter(redis, settings)


@pytest.mark.asyncio
async def test_first_consume_returns_quota_minus_one(limiter):
    remaining = await limiter.try_consume(user_id=1, quota=5)
    assert remaining == 4
    assert await limiter.usage(1) == 1


@pytest.mark.asyncio
async def test_consume_decrements_until_quota_then_rejects(limiter):
    remainings = []
    for _ in range(5):
        remainings.append(await limiter.try_consume(user_id=1, quota=5))
    assert remainings == [4, 3, 2, 1, 0]
    # Sixth attempt is rejected.
    assert await limiter.try_consume(user_id=1, quota=5) is None
    assert await limiter.usage(1) == 5


@pytest.mark.asyncio
async def test_zero_or_negative_quota_always_rejects(limiter):
    assert await limiter.try_consume(user_id=1, quota=0) is None
    assert await limiter.try_consume(user_id=1, quota=-3) is None
    assert await limiter.usage(1) == 0


@pytest.mark.asyncio
async def test_users_are_independent(limiter):
    assert await limiter.try_consume(user_id=1, quota=2) == 1
    assert await limiter.try_consume(user_id=2, quota=2) == 1
    assert await limiter.usage(1) == 1
    assert await limiter.usage(2) == 1


@pytest.mark.asyncio
async def test_remaining_reflects_usage(limiter):
    await limiter.try_consume(user_id=42, quota=10)
    await limiter.try_consume(user_id=42, quota=10)
    assert await limiter.remaining(42, 10) == 8


@pytest.mark.asyncio
async def test_reset_clears_today_counter(limiter):
    for _ in range(3):
        await limiter.try_consume(user_id=7, quota=5)
    assert await limiter.usage(7) == 3
    await limiter.reset(7)
    assert await limiter.usage(7) == 0
    # Fresh quota is available after reset.
    assert await limiter.try_consume(user_id=7, quota=5) == 4


@pytest.mark.asyncio
async def test_counter_keyed_by_local_date(redis, settings, monkeypatch):
    """A new local date must give the user a fresh quota."""
    tz = ZoneInfo(settings.timezone)
    fixed_today = datetime(2026, 5, 5, 14, 0, tzinfo=tz)
    fixed_tomorrow = fixed_today + timedelta(days=1)

    class _Clock:
        value = fixed_today

    def fake_now(tz=None):
        return _Clock.value

    monkeypatch.setattr(
        "jyry.services.rate_limiter.datetime",
        type("D", (), {"now": staticmethod(fake_now)}),
    )
    limiter = DailyQuotaLimiter(redis, settings)

    for _ in range(5):
        await limiter.try_consume(user_id=1, quota=5)
    assert await limiter.try_consume(user_id=1, quota=5) is None

    _Clock.value = fixed_tomorrow
    # New day -> different key -> quota replenishes without explicit reset.
    assert await limiter.try_consume(user_id=1, quota=5) == 4
