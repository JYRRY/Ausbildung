"""Check the Bundesagentur API once; exit 1 and optionally alert on failure.

Runs without the database, Redis or the bot — only network access — so it
can be scheduled from GitHub Actions before a server exists::

    python -m jyry.scripts.ba_health             # print the result
    python -m jyry.scripts.ba_health --notify    # also message the admins

Reads ``BA_API_BASE`` / ``BA_API_KEY`` (optional, defaults built in) and, for
``--notify``, ``TELEGRAM_BOT_TOKEN`` plus ``TELEGRAM_ADMIN_IDS``
(comma-separated numeric chat ids).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys

from jyry.config import Settings
from jyry.payments.notify import send_telegram_notice
from jyry.services.ba_health import check_ba, format_alert, format_status
from jyry.services.bundesagentur import BundesagenturClient


def _ba_settings() -> Settings:
    # Only the two BA fields are read by the client; model_construct skips
    # the required bot/database settings this script never touches.
    defaults = Settings.model_fields
    return Settings.model_construct(
        ba_api_base=os.environ.get("BA_API_BASE") or defaults["ba_api_base"].default,
        ba_api_key=os.environ.get("BA_API_KEY") or defaults["ba_api_key"].default,
    )


def _admin_ids(raw: str) -> list[int]:
    return [int(part) for part in raw.replace(" ", "").split(",") if part]


async def _main(notify: bool) -> int:
    async with BundesagenturClient(_ba_settings()) as client:
        report = await check_ba(client)
    print(format_status(report))

    if not report.ok and notify:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        admins = _admin_ids(os.environ.get("TELEGRAM_ADMIN_IDS", ""))
        if not token or not admins:
            print("--notify: TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_IDS missing", file=sys.stderr)
        for chat_id in admins:
            delivered = await send_telegram_notice(
                token=token, chat_id=chat_id, text=format_alert(report), parse_mode=None
            )
            if not delivered:
                print(f"--notify: delivery to {chat_id} failed", file=sys.stderr)
    return 0 if report.ok else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--notify", action="store_true", help="message TELEGRAM_ADMIN_IDS on failure"
    )
    args = parser.parse_args()
    sys.exit(asyncio.run(_main(args.notify)))


if __name__ == "__main__":
    main()
