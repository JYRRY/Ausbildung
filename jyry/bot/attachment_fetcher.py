"""Real :class:`AttachmentFetcher` backed by the Telegram CDN.

The bot stores only the ``file_id`` per attachment in the user's draft;
this fetcher resolves the id to a file path on the Telegram CDN, downloads
the bytes into memory, and returns them with a best-effort MIME guess.
"""

from __future__ import annotations

import logging
import mimetypes
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from telegram import Bot

logger = logging.getLogger(__name__)


def _guess_mime(file_path: str | None, filename: str | None = None) -> str:
    target = filename or file_path or ""
    guess, _ = mimetypes.guess_type(target)
    return guess or "application/octet-stream"


class TelegramAttachmentFetcher:
    """Implements :class:`jyry.services.send_pending.AttachmentFetcher`."""

    def __init__(self, bot: Bot) -> None:
        self._bot = bot

    async def fetch(self, file_id: str) -> tuple[bytes, str]:
        file = await self._bot.get_file(file_id)
        buf = bytearray()
        await file.download_to_memory(buf)  # type: ignore[arg-type]
        return bytes(buf), _guess_mime(file.file_path)
