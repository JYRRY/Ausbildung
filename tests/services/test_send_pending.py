"""Tests for jyry.services.send_pending."""

from __future__ import annotations

import fakeredis.aioredis
import httpx
import pytest
import pytest_asyncio
import respx
from aiosmtplib.errors import SMTPResponseException
from sqlalchemy import select

from jyry.db.enums import ApplicationStatus, Language, Plan, SubscriptionStatus
from jyry.db.models import (
    Application,
    EmailDraft,
    Subscription,
    User,
    UserSpecialty,
    UserState,
)
from jyry.services.bundesagentur import BundesagenturClient
from jyry.services.crypto import encrypt_secret
from jyry.services.rate_limiter import DailyQuotaLimiter
from jyry.services.send_pending import DispatchOutcome, dispatch_one
from tests.conftest import load_fixture

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"


class _StubFetcher:
    def __init__(self, payload: tuple[bytes, str] | None = None) -> None:
        self._payload = payload or (b"%PDF-1.4 fake-cv", "application/pdf")
        self.calls: list[str] = []

    async def fetch(self, file_id: str) -> tuple[bytes, str]:
        self.calls.append(file_id)
        return self._payload


@pytest_asyncio.fixture
async def redis():
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest_asyncio.fixture
async def limiter(redis, settings):
    return DailyQuotaLimiter(redis, settings)


async def _seed_full_user(
    session,
    *,
    plan: Plan = Plan.FREE,
    onboarding_complete: bool = True,
    with_draft: bool = True,
    specialties: list[str] | None = None,
    states: list[str] | None = None,
    attachments: list[dict] | None = None,
) -> User:
    user = User(
        telegram_id=10,
        full_name="Alice Test",
        gmail_address="alice@gmail.com",
        gmail_app_password_enc=encrypt_secret("super-secret-pw"),
        language=Language.AR,
        is_active=True,
        onboarding_complete=onboarding_complete,
    )
    session.add(user)
    await session.flush()
    sub = Subscription(
        user_id=user.id,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        daily_quota=5,
        emails_sent_today=0,
    )
    session.add(sub)
    if with_draft:
        draft = EmailDraft(
            user_id=user.id,
            subject_template="Bewerbung um Ausbildung bei {{company}}",
            body_template="Sehr geehrte Damen und Herren der {{company}}, …",
            attachments_meta=attachments or [],
        )
        session.add(draft)
    for kw in specialties or ["Bäcker"]:
        session.add(UserSpecialty(user_id=user.id, specialty_keyword=kw))
    for st in states or ["BY"]:
        session.add(UserState(user_id=user.id, state_code=st))
    await session.commit()
    await session.refresh(user)
    return user


def _empty_search() -> dict:
    return {"stellenangebote": [], "maxErgebnisse": 0, "page": 1, "size": 100}


def _detail_route(router, hash_id: str, fixture: str):
    return router.get(f"{BASE}/pc/v4/jobdetails/{hash_id}").mock(
        return_value=httpx.Response(200, json=load_fixture(fixture))
    )


@pytest.mark.asyncio
async def test_user_not_ready_when_onboarding_incomplete(
    settings, db_session, limiter
):
    await _seed_full_user(db_session, onboarding_complete=False)
    user_id = (await db_session.execute(select(User.id))).scalar_one()
    async with BundesagenturClient(settings) as client:
        result = await dispatch_one(
            user_id=user_id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=_StubFetcher(),
        )
    assert result.outcome is DispatchOutcome.USER_NOT_READY


@pytest.mark.asyncio
async def test_quota_exhausted_returns_specific_outcome(
    settings, db_session, redis, limiter
):
    user = await _seed_full_user(db_session)
    # Pre-fill quota for free plan (5 sends/day).
    for _ in range(5):
        await limiter.try_consume(user_id=user.id, quota=5)

    async with BundesagenturClient(settings) as client:
        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=_StubFetcher(),
        )
    assert result.outcome is DispatchOutcome.QUOTA_EXHAUSTED


@pytest.mark.asyncio
async def test_happy_path_sends_one_application(
    settings, db_session, limiter, mocker
):
    user = await _seed_full_user(
        db_session,
        attachments=[{"telegram_file_id": "TG-FILE-CV", "filename": "cv.pdf"}],
    )
    fetcher = _StubFetcher()

    smtp_send = mocker.patch("aiosmtplib.send", autospec=True)
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=load_fixture("ba_search_page.json")),
                httpx.Response(200, json=_empty_search()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=fetcher,
        )

    assert result.outcome is DispatchOutcome.SENT
    assert result.application_id is not None

    # Application row flipped to SENT.
    app = (
        await db_session.execute(
            select(Application).where(Application.id == result.application_id)
        )
    ).scalar_one()
    assert app.status == ApplicationStatus.SENT.value
    assert app.email_to == "bewerbung@konditorei-mueller.de"
    assert app.sent_at is not None
    assert "Konditorei Müller" in (app.email_subject or "")

    # SMTP got the right recipient + the cv.pdf attachment.
    assert smtp_send.call_count == 1
    msg = smtp_send.call_args.args[0]
    assert msg["To"] == "bewerbung@konditorei-mueller.de"
    assert any(
        a.get_filename() == "cv.pdf" for a in msg.iter_attachments()
    )
    assert fetcher.calls == ["TG-FILE-CV"]

    # Quota was actually consumed.
    assert await limiter.usage(user.id) == 1


@pytest.mark.asyncio
async def test_test_redirect_swaps_recipient_and_prefixes_subject(
    settings, db_session, limiter, mocker, monkeypatch
):
    monkeypatch.setattr(settings, "test_redirect_email", "dev@example.com")
    user = await _seed_full_user(db_session)
    fetcher = _StubFetcher()

    smtp_send = mocker.patch("aiosmtplib.send", autospec=True)
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=load_fixture("ba_search_page.json")),
                httpx.Response(200, json=_empty_search()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=fetcher,
        )

    assert result.outcome is DispatchOutcome.SENT

    # SMTP envelope flipped to redirect inbox; Subject carries the original
    # recipient in the prefix.
    msg = smtp_send.call_args.args[0]
    assert msg["To"] == "dev@example.com"
    assert msg["Subject"].startswith(
        "[TEST → bewerbung@konditorei-mueller.de]"
    )

    # Dedup row keeps the *real* recipient + subject so future runs without
    # the redirect still treat this employer as already-contacted.
    app = (
        await db_session.execute(
            select(Application).where(Application.id == result.application_id)
        )
    ).scalar_one()
    assert app.email_to == "bewerbung@konditorei-mueller.de"
    assert app.email_subject is not None
    assert not app.email_subject.startswith("[TEST")


@pytest.mark.asyncio
async def test_transient_smtp_failure_keeps_row_queued(
    settings, db_session, limiter, mocker
):
    user = await _seed_full_user(db_session)
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPResponseException(421, "Service not available"),
    )
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=load_fixture("ba_search_page.json")),
                httpx.Response(200, json=_empty_search()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=_StubFetcher(),
        )

    assert result.outcome is DispatchOutcome.TRANSIENT_FAILURE
    app = (
        await db_session.execute(
            select(Application).where(Application.id == result.application_id)
        )
    ).scalar_one()
    assert app.status == ApplicationStatus.QUEUED.value
    assert app.sent_at is None


@pytest.mark.asyncio
async def test_permanent_smtp_failure_marks_row_failed(
    settings, db_session, limiter, mocker
):
    user = await _seed_full_user(db_session)
    mocker.patch(
        "aiosmtplib.send",
        side_effect=SMTPResponseException(550, "Mailbox does not exist"),
    )
    async with BundesagenturClient(settings) as client, respx.mock(
        assert_all_called=False
    ) as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            side_effect=[
                httpx.Response(200, json=load_fixture("ba_search_page.json")),
                httpx.Response(200, json=_empty_search()),
            ]
        )
        _detail_route(router, "AAAA-hash-1", "ba_detail_with_email.json")
        _detail_route(router, "BBBB-hash-2", "ba_detail_no_email.json")
        _detail_route(router, "CCCC-hash-3", "ba_detail_generic_email.json")

        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=_StubFetcher(),
        )

    assert result.outcome is DispatchOutcome.PERMANENT_FAILURE
    app = (
        await db_session.execute(
            select(Application).where(Application.id == result.application_id)
        )
    ).scalar_one()
    assert app.status == ApplicationStatus.FAILED.value
    assert app.error_message and "550" in app.error_message


@pytest.mark.asyncio
async def test_no_posting_when_search_is_empty(
    settings, db_session, limiter, mocker
):
    user = await _seed_full_user(db_session)
    mocker.patch("aiosmtplib.send", autospec=True)
    async with BundesagenturClient(settings) as client, respx.mock() as router:
        router.get(f"{BASE}/pc/v4/jobs").mock(
            return_value=httpx.Response(200, json=_empty_search())
        )

        result = await dispatch_one(
            user_id=user.id,
            settings=settings,
            session=db_session,
            ba_client=client,
            limiter=limiter,
            fetcher=_StubFetcher(),
        )
    assert result.outcome is DispatchOutcome.NO_POSTING_FOUND
