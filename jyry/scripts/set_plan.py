"""Manually set a user's subscription plan — launch-prep / test tool.

Puts the account on a paid (or free) plan with an ACTIVE subscription so the
sender uses that plan's daily quota, without going through Paddle. Handy for
testing each plan one day at a time before flipping payments to production.

Usage (on the server, inside the venv)::

    python -m jyry.scripts.set_plan --user-id 1 --plan plus
    python -m jyry.scripts.set_plan --email you@example.com --plan pro --days 30
    python -m jyry.scripts.set_plan --user-id 1 --plan max --reset-quota

The same Gmail can belong to more than one account (a Telegram signup *and*
a web signup), so prefer ``--user-id`` when the email is ambiguous.

``--reset-quota`` clears today's Redis send counter so you can re-run a plan's
full daily burst on the same calendar day.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import UTC, datetime, timedelta

import redis.asyncio as redis_asyncio

from jyry.bot import repos
from jyry.config import get_settings
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.enums import Plan, SubscriptionStatus
from jyry.db.session import async_session_factory, dispose_engine
from jyry.scripts._common import UserLookupError, resolve_user
from jyry.services.rate_limiter import _today_key


async def _run(
    user_id: int | None,
    email: str | None,
    plan_value: str,
    days: int,
    reset_quota: bool,
) -> int:
    settings = get_settings()
    plan = Plan(plan_value)
    quota = PLAN_DAILY_QUOTA[plan_value]
    expires_at = datetime.now(tz=UTC) + timedelta(days=days)

    factory = async_session_factory()
    async with factory() as session:
        try:
            user = await resolve_user(session, user_id=user_id, email=email)
        except UserLookupError as exc:
            print(f"❌ {exc}")
            return 1

        sub = await repos.upsert_subscription(
            session,
            user_id=user.id,
            plan=plan,
            status=SubscriptionStatus.ACTIVE,
            expires_at=expires_at,
            paddle_subscription_id=None,
            paddle_customer_id=None,
            daily_quota=quota,
        )
        await session.commit()

        print(
            f"✅ user #{user.id} ({user.email or user.gmail_address}) -> "
            f"plan={plan.value} quota={quota}/day "
            f"status={sub.status.value if hasattr(sub.status, 'value') else sub.status} "
            f"expires={expires_at.date().isoformat()}"
        )
        if not user.is_active:
            print(
                "⚠️  is_active=False — sending is paused. Resume it from the "
                "dashboard (Versand toggle) or the bot to start the test run."
            )

        if reset_quota:
            r = redis_asyncio.from_url(settings.redis_url, decode_responses=True)
            try:
                deleted = await r.delete(_today_key(user.id, settings))
            finally:
                await r.aclose()
            print(
                "🔄 today's quota counter "
                + ("cleared" if deleted else "was already empty")
            )

    await dispose_engine()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Set a user's subscription plan.")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--user-id", type=int, help="exact user id (preferred)")
    target.add_argument("--email", help="login email or Gmail address")
    parser.add_argument(
        "--plan",
        required=True,
        choices=sorted(PLAN_DAILY_QUOTA.keys()),
        help="plan to grant (free/plus/pro/max)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="days until the subscription expires (default: 30)",
    )
    parser.add_argument(
        "--reset-quota",
        action="store_true",
        help="also clear today's Redis send counter for this user",
    )
    args = parser.parse_args()
    raise SystemExit(
        asyncio.run(
            _run(args.user_id, args.email, args.plan, args.days, args.reset_quota)
        )
    )


if __name__ == "__main__":
    main()
