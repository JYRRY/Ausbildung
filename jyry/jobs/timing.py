"""Pure helpers for picking the *next* scheduler tick time.

Kept I/O-free so the cadence math can be exhaustively unit-tested.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def end_of_local_day(now: datetime, tz: ZoneInfo) -> datetime:
    """Return the moment local-midnight rolls over (start of next local day)."""
    local_now = now.astimezone(tz)
    next_day = (local_now + timedelta(days=1)).date()
    boundary_local = datetime.combine(next_day, datetime.min.time(), tzinfo=tz)
    return boundary_local.astimezone(now.tzinfo) if now.tzinfo else boundary_local


def next_run_at_midnight(now: datetime, tz: ZoneInfo) -> datetime:
    """Schedule the next tick at the next local-midnight (quota refill point)."""
    return end_of_local_day(now, tz)


def next_run_for_quota(
    *,
    now: datetime,
    remaining_quota: int,
    min_interval: timedelta,
    jitter: timedelta,
    tz: ZoneInfo,
    rng: random.Random | None = None,
) -> datetime:
    """Spread ``remaining_quota`` sends across (now → end-of-day].

    Floors at ``min_interval`` so we never fire faster than that. Adds a
    symmetric ±``jitter`` so the cadence looks human.
    """
    if remaining_quota <= 0:
        return next_run_at_midnight(now, tz)

    horizon = end_of_local_day(now, tz) - now
    if horizon <= timedelta(0):
        return next_run_at_midnight(now, tz)

    even_step = horizon / remaining_quota
    interval = max(min_interval, even_step)

    rng = rng or random.SystemRandom()
    if jitter > timedelta(0):
        offset_seconds = rng.uniform(-jitter.total_seconds(), jitter.total_seconds())
        interval = interval + timedelta(seconds=offset_seconds)

    interval = max(interval, timedelta(seconds=1))
    return now + interval


def transient_retry_after(
    attempt: int, schedule: tuple[int, ...]
) -> timedelta | None:
    """Return the back-off for retry #``attempt`` (1-indexed) or ``None``.

    ``None`` means the schedule is exhausted — the caller should give up
    on this row and continue with the regular cadence.
    """
    if attempt < 1 or attempt > len(schedule):
        return None
    return timedelta(seconds=schedule[attempt - 1])
