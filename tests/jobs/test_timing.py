"""Tests for jyry.jobs.timing — pure functions, no I/O, no clocks needed."""

from __future__ import annotations

import random
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from jyry.jobs.timing import (
    end_of_local_day,
    next_run_at_midnight,
    next_run_for_quota,
    transient_retry_after,
)

BERLIN = ZoneInfo("Europe/Berlin")


def _berlin(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=BERLIN)


def test_end_of_local_day_returns_next_midnight():
    now = _berlin(2026, 5, 5, 14, 30)
    eod = end_of_local_day(now, BERLIN)
    assert eod == _berlin(2026, 5, 6, 0, 0)


def test_end_of_local_day_handles_dst_spring_forward():
    """Last Sunday of March 2026 — Berlin clocks jump 02:00 → 03:00."""
    before = _berlin(2026, 3, 28, 14, 0)  # Saturday
    eod = end_of_local_day(before, BERLIN)
    assert eod == _berlin(2026, 3, 29, 0, 0)


def test_next_run_for_quota_spreads_across_remaining_day():
    now = _berlin(2026, 5, 5, 14, 0)  # 10h until midnight
    nxt = next_run_for_quota(
        now=now,
        remaining_quota=100,
        min_interval=timedelta(seconds=60),
        jitter=timedelta(0),
        tz=BERLIN,
    )
    delta = nxt - now
    # 10h / 100 = 6 minutes
    assert timedelta(minutes=5) < delta < timedelta(minutes=7)


def test_next_run_for_quota_floors_at_min_interval():
    now = _berlin(2026, 5, 5, 23, 50)  # 10 minutes left
    nxt = next_run_for_quota(
        now=now,
        remaining_quota=100,
        min_interval=timedelta(seconds=60),
        jitter=timedelta(0),
        tz=BERLIN,
    )
    delta = nxt - now
    # Even step would be 6s; the floor must dominate.
    assert delta >= timedelta(seconds=60)


def test_next_run_for_quota_jitter_stays_within_bounds():
    now = _berlin(2026, 5, 5, 14, 0)
    rng = random.Random(42)
    even_step = (end_of_local_day(now, BERLIN) - now) / 100  # 6 min
    for _ in range(50):
        nxt = next_run_for_quota(
            now=now,
            remaining_quota=100,
            min_interval=timedelta(seconds=60),
            jitter=timedelta(seconds=20),
            tz=BERLIN,
            rng=rng,
        )
        delta = nxt - now
        # within even_step ± 20s, but never below 1s.
        assert delta >= timedelta(seconds=1)
        assert delta <= even_step + timedelta(seconds=21)


def test_next_run_for_quota_zero_quota_routes_to_midnight():
    now = _berlin(2026, 5, 5, 14, 0)
    nxt = next_run_for_quota(
        now=now,
        remaining_quota=0,
        min_interval=timedelta(seconds=60),
        jitter=timedelta(seconds=20),
        tz=BERLIN,
    )
    assert nxt == _berlin(2026, 5, 6, 0, 0)


def test_next_run_for_quota_handles_utc_input():
    """Caller may pass a UTC `now`; the result must still be UTC-aware."""
    now_utc = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)  # 14:00 Berlin
    nxt = next_run_for_quota(
        now=now_utc,
        remaining_quota=10,
        min_interval=timedelta(seconds=60),
        jitter=timedelta(0),
        tz=BERLIN,
    )
    assert nxt.tzinfo is not None
    assert nxt > now_utc


def test_next_run_at_midnight_matches_end_of_local_day():
    now = _berlin(2026, 5, 5, 14, 0)
    assert next_run_at_midnight(now, BERLIN) == end_of_local_day(now, BERLIN)


@pytest.mark.parametrize(
    ("attempt", "expected_seconds"),
    [(1, 300), (2, 1800), (3, 7200)],
)
def test_transient_retry_after_returns_each_step(attempt, expected_seconds):
    schedule = (300, 1800, 7200)
    delta = transient_retry_after(attempt, schedule)
    assert delta == timedelta(seconds=expected_seconds)


def test_transient_retry_after_exhausted_returns_none():
    schedule = (300, 1800, 7200)
    assert transient_retry_after(4, schedule) is None
    assert transient_retry_after(0, schedule) is None
