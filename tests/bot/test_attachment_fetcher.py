"""Tests for jyry.bot.attachment_fetcher.TelegramAttachmentFetcher."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from jyry.bot.attachment_fetcher import TelegramAttachmentFetcher


@pytest.mark.asyncio
async def test_fetch_returns_bytes_and_mime_from_pdf_path():
    bot = MagicMock()
    file_obj = MagicMock()
    file_obj.file_path = "documents/cv.pdf"

    async def _download(buffer):
        buffer.write(b"%PDF-1.4 test")

    file_obj.download_to_memory = AsyncMock(side_effect=_download)
    bot.get_file = AsyncMock(return_value=file_obj)

    fetcher = TelegramAttachmentFetcher(bot)
    content, mime = await fetcher.fetch("FILE-123")

    bot.get_file.assert_awaited_once_with("FILE-123")
    assert content == b"%PDF-1.4 test"
    assert mime == "application/pdf"


@pytest.mark.asyncio
async def test_fetch_falls_back_to_octet_stream_for_unknown_extension():
    bot = MagicMock()
    file_obj = MagicMock()
    file_obj.file_path = "documents/blob.unknownext"

    async def _download(buffer):
        buffer.write(b"raw")

    file_obj.download_to_memory = AsyncMock(side_effect=_download)
    bot.get_file = AsyncMock(return_value=file_obj)

    fetcher = TelegramAttachmentFetcher(bot)
    _, mime = await fetcher.fetch("FILE-Y")
    assert mime == "application/octet-stream"


@pytest.mark.asyncio
async def test_fetch_handles_missing_file_path():
    bot = MagicMock()
    file_obj = MagicMock()
    file_obj.file_path = None

    async def _download(buffer):
        buffer.write(b"x")

    file_obj.download_to_memory = AsyncMock(side_effect=_download)
    bot.get_file = AsyncMock(return_value=file_obj)

    fetcher = TelegramAttachmentFetcher(bot)
    _, mime = await fetcher.fetch("FILE-Z")
    assert mime == "application/octet-stream"
