"""Per-user daily-quota counter backed by Redis.

Each user has a daily quota (5 / 30 / 100 depending on plan). The limiter
tracks consumption atomically so two scheduler ticks racing on the same
user can never overshoot. The counter key embeds the date in the project
timezone (``Settings.timezone`` — Europe/Berlin in production), so the
quota naturally resets at local midnight without an explicit cron.

The check-and-increment runs as a Lua script inside Redis, returning the
remaining quota after the increment, or ``-1`` when the request would
exceed the quota. Lua keeps the GET / compare / INCR sequence atomic,
which a Python-level transaction can't guarantee under WATCH races.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import TYPE_CHECKING, Final

from jyry.config import Settings

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

_KEY_PREFIX: Final[str] = "jyry:quota:user"
_KEY_TTL_SECONDS: Final[int] = 60 * 60 * 36  # 36h: clears two days after a missed reset

_CONSUME_LUA: Final[str] = """
local key = KEYS[1]
local quota = tonumber(ARGV[1])
local ttl = tonumber(ARGV[2])
local current = tonumber(redis.call('GET', key) or '0')
if current >= quota then
    return -1
end
local after = redis.call('INCR', key)
redis.call('EXPIRE', key, ttl)
return quota - after
"""


def _today_key(user_id: int, settings: Settings) -> str:
    today = datetime.now(tz=settings.tz).date().isoformat()
    return f"{_KEY_PREFIX}:{user_id}:{today}"


class DailyQuotaLimiter:
    """Atomic per-user daily counter."""

    def __init__(self, redis: Redis[str], settings: Settings) -> None:
        self._redis = redis
        self._settings = settings
        self._consume_script = redis.register_script(_CONSUME_LUA)

    async def usage(self, user_id: int) -> int:
        """Return the number of sends already booked today for ``user_id``."""
        raw = await self._redis.get(_today_key(user_id, self._settings))
        return int(raw) if raw is not None else 0

    async def remaining(self, user_id: int, quota: int) -> int:
        used = await self.usage(user_id)
        return max(0, quota - used)

    async def try_consume(self, user_id: int, quota: int) -> int | None:
        """Atomically book one send.

        Returns the remaining quota *after* this send on success, or
        ``None`` when the user is already at their daily limit.
        """
        if quota <= 0:
            return None
        result = await self._consume_script(
            keys=[_today_key(user_id, self._settings)],
            args=[quota, _KEY_TTL_SECONDS],
        )
        remaining = int(result)
        if remaining < 0:
            return None
        return remaining

    async def reset(self, user_id: int) -> None:
        """Clear today's counter (used after a plan change)."""
        await self._redis.delete(_today_key(user_id, self._settings))
