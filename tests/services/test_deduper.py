"""Tests for jyry.services.deduper."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from jyry.db.enums import ApplicationStatus, Language
from jyry.db.models import Application, User
from jyry.services import deduper


async def _make_user(session, telegram_id: int = 100) -> User:
    user = User(
        telegram_id=telegram_id,
        language=Language.AR,
        is_active=True,
        onboarding_complete=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@pytest.mark.asyncio
async def test_first_claim_creates_queued_row(db_session):
    user = await _make_user(db_session)
    app = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name="Firma A",
        job_title="Ausbildung",
        email_to="bewerbung@firma.de",
        email_subject="Bewerbung",
    )
    await db_session.commit()
    assert app is not None
    assert app.status == ApplicationStatus.QUEUED.value
    assert app.email_to == "bewerbung@firma.de"
    assert app.sent_at is None


@pytest.mark.asyncio
async def test_second_claim_for_same_employer_returns_none(db_session):
    user = await _make_user(db_session)
    first = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name="Firma A",
        job_title=None,
        email_to="x@y.de",
        email_subject="s",
    )
    await db_session.commit()
    assert first is not None

    second = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name="Firma A",
        job_title=None,
        email_to="x@y.de",
        email_subject="s",
    )
    await db_session.commit()
    assert second is None
    rows = (await db_session.execute(select(Application))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_two_users_can_claim_same_employer(db_session):
    a = await _make_user(db_session, telegram_id=1)
    b = await _make_user(db_session, telegram_id=2)
    ra = await deduper.try_claim(
        db_session,
        user_id=a.id,
        kundennummer="kn-shared",
        company_name="Shared GmbH",
        job_title=None,
        email_to="hr@shared.de",
        email_subject="s",
    )
    rb = await deduper.try_claim(
        db_session,
        user_id=b.id,
        kundennummer="kn-shared",
        company_name="Shared GmbH",
        job_title=None,
        email_to="hr@shared.de",
        email_subject="s",
    )
    await db_session.commit()
    assert ra is not None and rb is not None and ra.id != rb.id


@pytest.mark.asyncio
async def test_mark_sent_flips_status_and_sets_timestamp(db_session):
    user = await _make_user(db_session)
    app = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name=None,
        job_title=None,
        email_to="x@y.de",
        email_subject="s",
    )
    await db_session.commit()
    assert app is not None

    when = datetime(2026, 5, 5, 12, 0, tzinfo=UTC)
    await deduper.mark_sent(db_session, app.id, sent_at=when)
    await db_session.commit()
    refreshed = (
        await db_session.execute(select(Application).where(Application.id == app.id))
    ).scalar_one()
    assert refreshed.status == ApplicationStatus.SENT.value
    assert refreshed.sent_at is not None
    assert refreshed.error_message is None


@pytest.mark.asyncio
async def test_mark_failed_records_truncated_error(db_session):
    user = await _make_user(db_session)
    app = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name=None,
        job_title=None,
        email_to="x@y.de",
        email_subject="s",
    )
    await db_session.commit()
    assert app is not None

    big_error = "X" * 5000
    await deduper.mark_failed(db_session, app.id, error_message=big_error)
    await db_session.commit()
    refreshed = (
        await db_session.execute(select(Application).where(Application.id == app.id))
    ).scalar_one()
    assert refreshed.status == ApplicationStatus.FAILED.value
    assert refreshed.error_message is not None
    assert len(refreshed.error_message) == 1000


@pytest.mark.asyncio
async def test_mark_bounced_uses_bounced_status(db_session):
    user = await _make_user(db_session)
    app = await deduper.try_claim(
        db_session,
        user_id=user.id,
        kundennummer="kn-A",
        company_name=None,
        job_title=None,
        email_to="x@y.de",
        email_subject="s",
    )
    await db_session.commit()
    assert app is not None

    await deduper.mark_failed(
        db_session, app.id, error_message="bounced", bounced=True
    )
    await db_session.commit()
    refreshed = (
        await db_session.execute(select(Application).where(Application.id == app.id))
    ).scalar_one()
    assert refreshed.status == ApplicationStatus.BOUNCED.value
