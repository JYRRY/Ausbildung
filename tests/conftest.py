"""Shared pytest fixtures: in-memory SQLite DB, settings override, respx mock."""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from cryptography.fernet import Fernet
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from jyry.config import Settings, get_settings
from jyry.db.base import Base
from jyry.services.bundesagentur import encode_job_code

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Detail-endpoint codes of the three postings in ba_search_page.json.
CODE_A = encode_job_code("10000-1234567890-S")  # posting carries a good email
CODE_B = encode_job_code("10000-2222222222-S")  # no email in the posting
CODE_C = encode_job_code("10000-3333333333-S")  # only generic emails


def _set_test_env() -> None:
    os.environ.setdefault("JYRY_ENV", "testing")
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test-token:dummy")
    os.environ.setdefault("FERNET_KEY", Fernet.generate_key().decode())
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
    os.environ.setdefault("REDIS_URL", "redis://127.0.0.1:6379/15")


_set_test_env()


@pytest.fixture(scope="session")
def settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest_asyncio.fixture
async def db_session() -> AsyncIterator[AsyncSession]:
    """Fresh in-memory SQLite per test, with the full schema created."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)
    async with factory() as session:
        yield session
    await engine.dispose()


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
