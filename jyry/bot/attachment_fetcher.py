"""Real :class:`AttachmentFetcher` backed by the Telegram CDN.

The bot stores only the ``file_id`` per attachment in the user's draft;
this fetcher resolves the id to a file path on the Telegram CDN, downloads
the bytes into memory, and returns them with a best-effort MIME guess.
"""

from __future__ import annotations

import logging
import mimetypes
from io import BytesIO
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
        # PTB streams chunks via ``out.write(chunk)`` — bytearray has no
        # ``.write`` method, so we use a real BytesIO buffer.
        buf = BytesIO()
        await file.download_to_memory(buf)
        return buf.getvalue(), _guess_mime(file.file_path)
