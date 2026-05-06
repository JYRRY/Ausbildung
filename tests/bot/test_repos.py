"""Tests for jyry.bot.repos — round-trip CRUD + helpers."""

from __future__ import annotations

from datetime import UTC

import fakeredis.aioredis
import pytest
import pytest_asyncio
from sqlalchemy import select

from jyry.bot import repos
from jyry.db.enums import ApplicationStatus, Plan, SubscriptionStatus
from jyry.db.models import Application, Subscription, User, UserSpecialty, UserState
from jyry.services.crypto import decrypt_secret
from jyry.services.rate_limiter import DailyQuotaLimiter


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture
async def limiter(redis, settings):
    return DailyQuotaLimiter(redis, settings)


@pytest.mark.asyncio
async def test_get_or_create_user_inserts_then_returns_same_row(db_session):
    a = await repos.get_or_create_user(db_session, telegram_id=1234)
    b = await repos.get_or_create_user(db_session, telegram_id=1234)
    assert a.id == b.id
    assert b.language.value == "de"
    rows = (await db_session.execute(select(User))).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_set_full_name_strips_and_persists(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=1)
    await repos.set_full_name(db_session, user.id, "  Alice  Test  ")
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.full_name == "Alice  Test"  # only outer strip


@pytest.mark.asyncio
async def test_set_gmail_encrypts_app_password(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=2)
    await repos.set_gmail(
        db_session,
        user.id,
        address="USER@Gmail.com",
        app_password_plaintext="abcd efgh ijkl mnop",
    )
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.gmail_address == "user@gmail.com"  # lower-cased
    assert refreshed.gmail_app_password_enc is not None
    assert b"abcd efgh" not in refreshed.gmail_app_password_enc
    assert decrypt_secret(refreshed.gmail_app_password_enc) == "abcd efgh ijkl mnop"


@pytest.mark.asyncio
async def test_replace_specialties_overwrites_previous_set(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=3)
    await repos.replace_specialties(db_session, user.id, ["Bäcker", "Koch"])
    await repos.replace_specialties(db_session, user.id, ["Mechatroniker"])
    rows = (
        await db_session.execute(
            select(UserSpecialty.specialty_keyword).where(UserSpecialty.user_id == user.id)
        )
    ).scalars().all()
    assert rows == ["Mechatroniker"]


@pytest.mark.asyncio
async def test_replace_states_overwrites_previous_set(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=4)
    await repos.replace_states(db_session, user.id, ["BY", "BE"])
    await repos.replace_states(db_session, user.id, ["NW"])
    rows = (
        await db_session.execute(
            select(UserState.state_code).where(UserState.user_id == user.id)
        )
    ).scalars().all()
    assert rows == ["NW"]


@pytest.mark.asyncio
async def test_upsert_draft_inserts_then_updates(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=5)
    await repos.upsert_draft(db_session, user.id, body_template="hello")
    await repos.upsert_draft(db_session, user.id, body_template="hello v2")
    refreshed = await repos.upsert_draft(db_session, user.id)
    assert refreshed.body_template == "hello v2"


@pytest.mark.asyncio
async def test_append_attachment_then_remove(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=6)
    await repos.append_attachment(
        db_session, user.id, filename="cv.pdf", file_id="F1", mime="application/pdf", size=1234
    )
    await repos.append_attachment(
        db_session, user.id, filename="z.pdf", file_id="F2", mime="application/pdf", size=2222
    )
    # Re-adding the same file_id is a no-op.
    draft = await repos.append_attachment(
        db_session, user.id, filename="cv.pdf", file_id="F1", mime="application/pdf", size=1234
    )
    assert len(draft.attachments_meta) == 2

    after_remove = await repos.remove_attachment(db_session, user.id, "F1")
    ids = [m["telegram_file_id"] for m in after_remove.attachments_meta]
    assert ids == ["F2"]


@pytest.mark.asyncio
async def test_mark_onboarded_and_set_active(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=7)
    await repos.mark_onboarded(db_session, user.id)
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.onboarding_complete is True
    assert refreshed.is_active is True

    await repos.set_active(db_session, user.id, is_active=False)
    refreshed = (
        await db_session.execute(select(User).where(User.id == user.id))
    ).scalar_one()
    assert refreshed.is_active is False


@pytest.mark.asyncio
async def test_grant_free_trial_creates_then_resets(db_session):
    user = await repos.get_or_create_user(db_session, telegram_id=8)
    sub = await repos.grant_free_trial(db_session, user.id)
    assert sub.plan is Plan.FREE
    assert sub.status is SubscriptionStatus.ACTIVE
    assert sub.expires_at is not None

    # Re-granting refreshes expiry.
    sub2 = await repos.grant_free_trial(db_session, user.id)
    assert sub2.expires_at >= sub.started_at
    rows = (
        await db_session.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalars().all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_status_summary_counts_sent_applications(db_session, limiter):
    user = await repos.get_or_create_user(db_session, telegram_id=9)
    await repos.grant_free_trial(db_session, user.id)
    db_session.add_all(
        [
            Application(
                user_id=user.id,
                kundennummer=f"k{i}",
                email_to=f"x{i}@y.de",
                email_subject="s",
                status=ApplicationStatus.SENT.value,
            )
            for i in range(3)
        ]
        + [
            Application(
                user_id=user.id,
                kundennummer="kQ",
                email_to="q@y.de",
                email_subject="s",
                status=ApplicationStatus.QUEUED.value,
            )
        ]
    )
    await db_session.commit()
    await limiter.try_consume(user_id=user.id, quota=5)

    summary = await repos.status_summary(db_session, limiter, user.id)
    assert summary.plan == "free"
    assert summary.total_sent == 3
    assert summary.sent_today == 1
    assert summary.remaining_today == 4
    assert summary.is_active is True


@pytest.mark.asyncio
async def test_has_active_subscription_false_when_expired(db_session):
    from datetime import datetime, timedelta

    user = await repos.get_or_create_user(db_session, telegram_id=10)
    db_session.add(
        Subscription(
            user_id=user.id,
            plan=Plan.FREE,
            status=SubscriptionStatus.ACTIVE,
            started_at=datetime.now(tz=UTC) - timedelta(days=10),
            expires_at=datetime.now(tz=UTC) - timedelta(days=1),
            daily_quota=5,
            emails_sent_today=0,
        )
    )
    await db_session.commit()
    full_user = await repos.load_user(db_session, user.id)
    assert full_user is not None
    assert repos.has_active_subscription(full_user) is False
