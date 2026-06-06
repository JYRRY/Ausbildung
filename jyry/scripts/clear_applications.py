"""Delete a user's ``applications`` rows — pre-launch cleanup tool.

During test runs every redirected email still claims a real Bundesagentur
employer for the account (UNIQUE on user_id+kundennummer) and marks it SENT,
so production would later *skip* those employers. Run this once, after testing
and before going live, to wipe the test history so every employer is contacted
fresh.

Usage (on the server, inside the venv)::

    python -m jyry.scripts.clear_applications --user-id 1            # dry run
    python -m jyry.scripts.clear_applications --user-id 1 --yes      # actually delete

The same Gmail can belong to more than one account, so prefer ``--user-id``
when ``--email`` is ambiguous.
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, func, select

from jyry.db.models import Application
from jyry.db.session import async_session_factory, dispose_engine
from jyry.scripts._common import UserLookupError, resolve_user


async def _run(user_id: int | None, email: str | None, confirm: bool) -> int:
    factory = async_session_factory()
    async with factory() as session:
        try:
            user = await resolve_user(session, user_id=user_id, email=email)
        except UserLookupError as exc:
            print(f"❌ {exc}")
            return 1

        count = (
            await session.execute(
                select(func.count(Application.id)).where(
                    Application.user_id == user.id
                )
            )
        ).scalar_one()

        label = user.email or user.gmail_address
        if count == 0:
            print(f"✅ user #{user.id} ({label}) has no applications — nothing to do")
            return 0

        if not confirm:
            print(
                f"🔎 dry run: user #{user.id} ({label}) has {count} application "
                f"row(s). Re-run with --yes to delete them."
            )
            return 0

        await session.execute(
            delete(Application).where(Application.user_id == user.id)
        )
        await session.commit()
        print(f"🗑️  deleted {count} application row(s) for user #{user.id} ({label})")

    await dispose_engine()
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Delete a user's applications history (pre-launch cleanup)."
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--user-id", type=int, help="exact user id (preferred)")
    target.add_argument("--email", help="login email or Gmail address")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually delete (omit for a dry run)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.user_id, args.email, args.yes)))


if __name__ == "__main__":
    main()
