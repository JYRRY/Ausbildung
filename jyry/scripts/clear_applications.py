"""Delete a user's ``applications`` rows — pre-launch cleanup tool.

During test runs every redirected email still claims a real Bundesagentur
employer for the account (UNIQUE on user_id+kundennummer) and marks it SENT,
so production would later *skip* those employers. Run this once, after testing
and before going live, to wipe the test history so every employer is contacted
fresh.

Usage (on the server, inside the venv)::

    python -m jyry.scripts.clear_applications --email you@example.com          # dry run
    python -m jyry.scripts.clear_applications --email you@example.com --yes    # actually delete
"""

from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import delete, func, select

from jyry.db.models import Application
from jyry.db.session import async_session_factory, dispose_engine
from jyry.scripts._common import find_user_by_email


async def _run(email: str, confirm: bool) -> int:
    factory = async_session_factory()
    async with factory() as session:
        user = await find_user_by_email(session, email)
        if user is None:
            print(f"❌ no user found with email/gmail = {email!r}")
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
    parser.add_argument("--email", required=True, help="login email or Gmail address")
    parser.add_argument(
        "--yes",
        action="store_true",
        help="actually delete (omit for a dry run)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(_run(args.email, args.yes)))


if __name__ == "__main__":
    main()
