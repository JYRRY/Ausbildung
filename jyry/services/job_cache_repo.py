"""Repository over the ``job_cache`` table.

Holds enriched Bundesagentur postings keyed by employer reference (the BA
``kundennummerHash`` or a SHA-256 fallback when that hash is null). The cache
is consulted before any detail fetch so a single posting is enriched at most
once per ``BA_CACHE_TTL_SECONDS``.

PostgreSQL is the production target; SQLite (in-memory) backs the tests.
Both support ``INSERT ... ON CONFLICT DO UPDATE`` with compatible SQLAlchemy
APIs, dispatched via the active dialect's ``insert`` constructor.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Insert as InsertDML

from jyry.db.models import JobCache


def fallback_employer_ref(employer_name: str | None) -> str:
    """Derive a stable employer reference when the BA hash is missing."""
    name = (employer_name or "").strip().lower()
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()
    return f"sha:{digest[:32]}"


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _build_upsert(session: AsyncSession, values: dict[str, Any]) -> InsertDML:
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        stmt = pg_insert(JobCache).values(**values)
        update_cols = {k: stmt.excluded[k] for k in values if k != "kundennummer"}
        update_cols["fetched_at"] = func.now()
        return stmt.on_conflict_do_update(
            index_elements=[JobCache.kundennummer],
            set_=update_cols,
        )
    if dialect == "sqlite":
        stmt = sqlite_insert(JobCache).values(**values)
        update_cols = {k: stmt.excluded[k] for k in values if k != "kundennummer"}
        update_cols["fetched_at"] = func.now()
        return stmt.on_conflict_do_update(
            index_elements=[JobCache.kundennummer],
            set_=update_cols,
        )
    raise NotImplementedError(f"job_cache upsert not supported on dialect: {dialect!r}")


async def get_fresh(
    session: AsyncSession, employer_ref: str, ttl: timedelta
) -> JobCache | None:
    """Return the cache row for ``employer_ref`` if it was fetched within ``ttl``."""
    cutoff = _utcnow() - ttl
    stmt = select(JobCache).where(
        JobCache.kundennummer == employer_ref,
        JobCache.fetched_at >= cutoff,
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def upsert(
    session: AsyncSession,
    *,
    employer_ref: str,
    raw: dict[str, Any],
    email: str | None,
    company: str | None,
    title: str | None,
    location: str | None,
    state_code: str | None,
    specialty_keyword: str | None,
) -> None:
    """Insert or refresh the cache row keyed by ``employer_ref``."""
    values: dict[str, Any] = {
        "kundennummer": employer_ref,
        "company_name": company,
        "job_title": title,
        "location": location,
        "state_code": state_code,
        "specialty_keyword": specialty_keyword,
        "email": email,
        "raw_data": raw,
        "fetched_at": func.now(),
    }
    await session.execute(_build_upsert(session, values))


async def purge_stale(session: AsyncSession, ttl: timedelta) -> int:
    """Delete rows older than ``ttl``. Returns the deleted-row count."""
    cutoff = _utcnow() - ttl
    result = await session.execute(delete(JobCache).where(JobCache.fetched_at < cutoff))
    return result.rowcount or 0
