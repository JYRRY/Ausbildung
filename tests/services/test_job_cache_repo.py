"""Tests for jyry.services.job_cache_repo."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

from jyry.db.models import JobCache
from jyry.services.job_cache_repo import (
    fallback_employer_ref,
    get_fresh,
    purge_stale,
    upsert,
)


def _backdate(seconds: int) -> datetime:
    return datetime.now(tz=timezone.utc) - timedelta(seconds=seconds)


@pytest.mark.asyncio
async def test_upsert_inserts_new_row(db_session):
    await upsert(
        db_session,
        employer_ref="kn-1",
        raw={"hashId": "X"},
        email="bewerbung@firma.de",
        company="Firma GmbH",
        title="Ausbildung",
        location="München",
        state_code="BY",
        specialty_keyword="Bäcker",
    )
    await db_session.commit()

    row = (
        await db_session.execute(select(JobCache).where(JobCache.kundennummer == "kn-1"))
    ).scalar_one()
    assert row.email == "bewerbung@firma.de"
    assert row.company_name == "Firma GmbH"
    assert row.state_code == "BY"
    assert row.raw_data == {"hashId": "X"}


@pytest.mark.asyncio
async def test_upsert_updates_existing_row_on_conflict(db_session):
    await upsert(
        db_session,
        employer_ref="kn-1",
        raw={"v": 1},
        email=None,
        company="Old",
        title=None,
        location=None,
        state_code=None,
        specialty_keyword=None,
    )
    await upsert(
        db_session,
        employer_ref="kn-1",
        raw={"v": 2},
        email="bewerbung@neu.de",
        company="New",
        title="Ausbildung",
        location="Berlin",
        state_code="BE",
        specialty_keyword="Verkäufer",
    )
    await db_session.commit()

    rows = (await db_session.execute(select(JobCache))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.email == "bewerbung@neu.de"
    assert row.company_name == "New"
    assert row.raw_data == {"v": 2}


@pytest.mark.asyncio
async def test_get_fresh_returns_row_within_ttl(db_session):
    await upsert(
        db_session,
        employer_ref="kn-fresh",
        raw={},
        email="x@y.de",
        company=None,
        title=None,
        location=None,
        state_code=None,
        specialty_keyword=None,
    )
    await db_session.commit()

    row = await get_fresh(db_session, "kn-fresh", ttl=timedelta(hours=24))
    assert row is not None
    assert row.kundennummer == "kn-fresh"


@pytest.mark.asyncio
async def test_get_fresh_returns_none_when_stale(db_session):
    await upsert(
        db_session,
        employer_ref="kn-stale",
        raw={},
        email="x@y.de",
        company=None,
        title=None,
        location=None,
        state_code=None,
        specialty_keyword=None,
    )
    await db_session.execute(
        update(JobCache)
        .where(JobCache.kundennummer == "kn-stale")
        .values(fetched_at=_backdate(seconds=2 * 24 * 3600))
    )
    await db_session.commit()

    row = await get_fresh(db_session, "kn-stale", ttl=timedelta(hours=24))
    assert row is None


@pytest.mark.asyncio
async def test_get_fresh_missing_returns_none(db_session):
    row = await get_fresh(db_session, "nope", ttl=timedelta(hours=24))
    assert row is None


@pytest.mark.asyncio
async def test_purge_stale_drops_only_old_rows(db_session):
    await upsert(
        db_session,
        employer_ref="keep",
        raw={},
        email=None,
        company=None,
        title=None,
        location=None,
        state_code=None,
        specialty_keyword=None,
    )
    await upsert(
        db_session,
        employer_ref="drop",
        raw={},
        email=None,
        company=None,
        title=None,
        location=None,
        state_code=None,
        specialty_keyword=None,
    )
    await db_session.execute(
        update(JobCache)
        .where(JobCache.kundennummer == "drop")
        .values(fetched_at=_backdate(seconds=2 * 24 * 3600))
    )
    await db_session.commit()

    deleted = await purge_stale(db_session, ttl=timedelta(hours=24))
    await db_session.commit()
    assert deleted == 1

    remaining = (
        (await db_session.execute(select(JobCache.kundennummer))).scalars().all()
    )
    assert remaining == ["keep"]


def test_fallback_employer_ref_is_stable_and_normalised():
    assert fallback_employer_ref("Acme GmbH") == fallback_employer_ref("  acme gmbh  ")
    a = fallback_employer_ref("Firma A")
    b = fallback_employer_ref("Firma B")
    assert a != b
    assert a.startswith("sha:")
    assert len(a) == len("sha:") + 32


def test_fallback_employer_ref_handles_none():
    assert fallback_employer_ref(None).startswith("sha:")
