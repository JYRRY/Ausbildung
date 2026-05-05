"""Claim a (user_id, employer) pair in ``applications``.

Backed by the ``UNIQUE(user_id, kundennummer)`` constraint added in M1, so
even with two scheduler workers racing on the same user the same employer
is contacted at most once. The claim row starts in ``QUEUED`` and is
flipped to ``SENT`` / ``FAILED`` once the SMTP attempt is done.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.dml import Insert as InsertDML

from jyry.db.enums import ApplicationStatus
from jyry.db.models import Application


def _build_claim_insert(session: AsyncSession, values: dict[str, Any]) -> InsertDML:
    dialect = session.bind.dialect.name if session.bind is not None else ""
    if dialect == "postgresql":
        pg_stmt = pg_insert(Application).values(**values)
        return pg_stmt.on_conflict_do_nothing(
            index_elements=[Application.user_id, Application.kundennummer]
        )
    if dialect == "sqlite":
        sl_stmt = sqlite_insert(Application).values(**values)
        return sl_stmt.on_conflict_do_nothing(
            index_elements=[Application.user_id, Application.kundennummer]
        )
    raise NotImplementedError(f"deduper not supported on dialect: {dialect!r}")


async def try_claim(
    session: AsyncSession,
    *,
    user_id: int,
    kundennummer: str,
    company_name: str | None,
    job_title: str | None,
    email_to: str,
    email_subject: str,
) -> Application | None:
    """Insert a QUEUED application row.

    Returns the new ``Application`` on success, or ``None`` when this
    employer was already contacted by this user (the UNIQUE conflict is
    swallowed silently — that's the whole point).
    """
    values: dict[str, Any] = {
        "user_id": user_id,
        "kundennummer": kundennummer,
        "company_name": company_name,
        "job_title": job_title,
        "email_to": email_to,
        "email_subject": email_subject,
        "status": ApplicationStatus.QUEUED.value,
    }
    result = await session.execute(_build_claim_insert(session, values))
    if int(getattr(result, "rowcount", 0) or 0) == 0:
        return None

    row = await session.execute(
        select(Application).where(
            Application.user_id == user_id,
            Application.kundennummer == kundennummer,
        )
    )
    return row.scalar_one()


async def mark_sent(
    session: AsyncSession,
    application_id: int,
    *,
    sent_at: datetime,
) -> None:
    await session.execute(
        update(Application)
        .where(Application.id == application_id)
        .values(status=ApplicationStatus.SENT.value, sent_at=sent_at, error_message=None)
    )


async def mark_failed(
    session: AsyncSession,
    application_id: int,
    *,
    error_message: str,
    bounced: bool = False,
) -> None:
    status = ApplicationStatus.BOUNCED if bounced else ApplicationStatus.FAILED
    await session.execute(
        update(Application)
        .where(Application.id == application_id)
        .values(status=status.value, error_message=error_message[:1000])
    )
