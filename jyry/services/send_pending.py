"""Single-shot dispatcher: take one user, send one application.

Wires the rest of the M2/M3 stack together for *one* outbound email:

1. Daily quota check via :class:`DailyQuotaLimiter` (atomic Redis INCR).
2. Pull the user's current draft + specialties + states from the DB.
3. Iterate :func:`iter_ready_postings` until we find an employer the user
   has *not* already contacted, claim it via :func:`deduper.try_claim`.
4. Resolve attachments (Telegram ``file_id`` -> bytes) through an injected
   ``AttachmentFetcher`` so this layer stays testable without a live bot.
5. Send via :class:`GmailSender`. On TRANSIENT failures the row stays
   ``QUEUED`` (the scheduler will re-poll later); on PERMANENT failures it
   is flipped to ``FAILED``; on success it is flipped to ``SENT``.

The function is intentionally synchronous-ish in shape (one user, one
email) so the M3.e scheduler can fan out one ``asyncio.Task`` per user
without overlapping flushes on the same session.
"""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Protocol

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.models import EmailDraft, User
from jyry.services import deduper
from jyry.services.crypto import CryptoError, decrypt_secret
from jyry.services.gmail_sender import (
    Attachment,
    GmailSender,
    SendOutcome,
    SendResult,
)
from jyry.services.job_finder import iter_ready_postings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from jyry.config import Settings
    from jyry.services.bundesagentur import BundesagenturClient
    from jyry.services.rate_limiter import DailyQuotaLimiter

logger = logging.getLogger(__name__)


class DispatchOutcome(enum.Enum):
    SENT = "sent"
    QUOTA_EXHAUSTED = "quota_exhausted"
    NO_POSTING_FOUND = "no_posting_found"
    USER_NOT_READY = "user_not_ready"
    TRANSIENT_FAILURE = "transient_failure"
    PERMANENT_FAILURE = "permanent_failure"


@dataclass(frozen=True, slots=True)
class DispatchResult:
    outcome: DispatchOutcome
    application_id: int | None = None
    detail: str | None = None
    company: str | None = None
    job_title: str | None = None


class AttachmentFetcher(Protocol):
    """Resolves a Telegram ``file_id`` to attachment bytes + MIME."""

    async def fetch(self, file_id: str) -> tuple[bytes, str]: ...


def _render_template(template: str, *, posting_company: str | None) -> str:
    return template.replace("{{company}}", posting_company or "").strip()


async def _load_user_with_relations(session: AsyncSession, user_id: int) -> User | None:
    stmt = (
        select(User)
        .where(User.id == user_id)
        .options(
            selectinload(User.email_draft),
            selectinload(User.specialties),
            selectinload(User.states),
            selectinload(User.subscription),
        )
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


def _user_quota(user: User) -> int:
    sub = user.subscription
    if sub is None or sub.plan is None:
        return PLAN_DAILY_QUOTA["free"]
    plan_value = sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)
    return PLAN_DAILY_QUOTA.get(plan_value, PLAN_DAILY_QUOTA["free"])


async def _resolve_attachments(
    draft: EmailDraft, fetcher: AttachmentFetcher
) -> list[Attachment]:
    attachments: list[Attachment] = []
    for meta in draft.attachments_meta or []:
        file_id = meta.get("telegram_file_id")
        filename = meta.get("filename") or "attachment.bin"
        if not file_id:
            continue
        try:
            content, mime = await fetcher.fetch(file_id)
        except Exception as exc:
            logger.warning(
                "attachment fetch failed file=%s reason=%s",
                filename,
                f"{type(exc).__name__}: {exc}",
            )
            continue
        attachments.append(
            Attachment(filename=filename, content=content, mime_type=mime)
        )
    return attachments


async def dispatch_one(
    *,
    user_id: int,
    settings: Settings,
    session: AsyncSession,
    ba_client: BundesagenturClient,
    limiter: DailyQuotaLimiter,
    fetcher: AttachmentFetcher,
) -> DispatchResult:
    """Send (at most) one application for ``user_id``."""
    user = await _load_user_with_relations(session, user_id)
    if user is None or not user.onboarding_complete:
        return DispatchResult(DispatchOutcome.USER_NOT_READY, detail="onboarding incomplete")
    if not user.is_active or not user.gmail_address or not user.gmail_app_password_enc:
        return DispatchResult(DispatchOutcome.USER_NOT_READY, detail="gmail credentials missing")
    if user.email_draft is None or not user.email_draft.subject_template:
        return DispatchResult(DispatchOutcome.USER_NOT_READY, detail="email draft missing")
    if not user.specialties or not user.states:
        return DispatchResult(DispatchOutcome.USER_NOT_READY, detail="selection missing")

    sub = user.subscription
    if sub is not None and sub.expires_at is not None:
        expires = sub.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(tz=UTC):
            return DispatchResult(
                DispatchOutcome.USER_NOT_READY, detail="subscription expired"
            )

    quota = _user_quota(user)
    if (remaining_after := await limiter.try_consume(user_id=user_id, quota=quota)) is None:
        return DispatchResult(DispatchOutcome.QUOTA_EXHAUSTED)

    try:
        app_password = decrypt_secret(user.gmail_app_password_enc, settings=settings)
    except CryptoError as exc:
        return DispatchResult(DispatchOutcome.PERMANENT_FAILURE, detail=str(exc))

    specialties = [s.specialty_keyword for s in user.specialties]
    states = [s.state_code for s in user.states]
    ttl = timedelta(seconds=settings.ba_cache_ttl_seconds)

    claimed = None
    posting = None
    async for candidate in iter_ready_postings(
        session,
        ba_client,
        specialties=specialties,
        states=states,
        want=remaining_after + 1,  # at least one more
        ttl=ttl,
    ):
        subject = _render_template(
            user.email_draft.subject_template, posting_company=candidate.company
        )
        claimed = await deduper.try_claim(
            session,
            user_id=user.id,
            kundennummer=candidate.employer_ref,
            company_name=candidate.company,
            job_title=candidate.job_title,
            email_to=candidate.email,
            email_subject=subject,
        )
        if claimed is not None:
            posting = candidate
            break

    if claimed is None or posting is None:
        # Refund the single quota slot we consumed above — we never sent.
        await limiter.refund(user_id)
        return DispatchResult(DispatchOutcome.NO_POSTING_FOUND)
    await session.commit()

    body = _render_template(
        user.email_draft.body_template, posting_company=posting.company
    )
    attachments = await _resolve_attachments(user.email_draft, fetcher)

    sender = GmailSender(
        settings,
        sender_email=user.gmail_address,
        app_password=app_password,
        sender_name=user.full_name,
    )

    actual_to = posting.email
    actual_subject = claimed.email_subject or ""
    if settings.test_redirect_email:
        logger.info(
            "test redirect active: user=%s would_send_to=%s redirecting_to=%s",
            user.id,
            posting.email,
            settings.test_redirect_email,
        )
        actual_to = settings.test_redirect_email
        actual_subject = f"[TEST → {posting.email}] {actual_subject}"

    send_result = await sender.send(
        to_email=actual_to,
        subject=actual_subject,
        body=body,
        attachments=attachments,
    )

    if send_result.outcome is SendOutcome.SENT:
        await deduper.mark_sent(
            session, claimed.id, sent_at=datetime.now(tz=UTC)
        )
        await session.commit()
        return DispatchResult(
            DispatchOutcome.SENT,
            application_id=claimed.id,
            company=claimed.company_name,
            job_title=claimed.job_title,
        )

    if send_result.outcome is SendOutcome.PERMANENT:
        await deduper.mark_failed(
            session,
            claimed.id,
            error_message=send_result.detail or "permanent SMTP failure",
        )
        await session.commit()
        return DispatchResult(
            DispatchOutcome.PERMANENT_FAILURE,
            application_id=claimed.id,
            detail=send_result.detail,
        )

    # TRANSIENT — leave the row QUEUED so the scheduler re-tries.
    return DispatchResult(
        DispatchOutcome.TRANSIENT_FAILURE,
        application_id=claimed.id,
        detail=send_result.detail,
    )


# ---------------------------------------------------------------------------
# Test-send (bypass Bundesagentur)
# ---------------------------------------------------------------------------


async def send_test_email(
    *,
    user_id: int,
    settings: Settings,
    session: AsyncSession,
    fetcher: AttachmentFetcher,
    count: int = 5,
    pause_seconds: float = 2.0,
) -> tuple[int, SendResult | None]:
    """Fire ``count`` test emails back-to-back to demo the Free-trial burst.

    Each iteration uses a different ``Musterfirma`` company name so Gmail
    threads the messages separately. Skips quota, Bundesagentur and the
    applications table entirely. The recipient is ``test_redirect_email``
    when set, otherwise the user's own Gmail. Returns ``(sent_count,
    last_failure)`` — the operator can see how many succeeded and the
    reason if any failed.
    """
    import asyncio

    user = await _load_user_with_relations(session, user_id)
    if user is None:
        return 0, SendResult(SendOutcome.PERMANENT, None, "user not found")
    if not user.gmail_address or not user.gmail_app_password_enc:
        return 0, SendResult(
            SendOutcome.PERMANENT, None, "gmail credentials missing"
        )
    if user.email_draft is None or not user.email_draft.subject_template:
        return 0, SendResult(SendOutcome.PERMANENT, None, "email draft missing")

    try:
        app_password = decrypt_secret(user.gmail_app_password_enc, settings=settings)
    except CryptoError as exc:
        return 0, SendResult(SendOutcome.PERMANENT, None, str(exc))

    attachments = await _resolve_attachments(user.email_draft, fetcher)
    sender = GmailSender(
        settings,
        sender_email=user.gmail_address,
        app_password=app_password,
        sender_name=user.full_name,
    )
    actual_to = settings.test_redirect_email or user.gmail_address

    sent = 0
    last_failure: SendResult | None = None
    for i in range(1, count + 1):
        fake_company = f"Musterfirma {i} GmbH"
        subject = _render_template(
            user.email_draft.subject_template, posting_company=fake_company
        )
        body = _render_template(
            user.email_draft.body_template, posting_company=fake_company
        )
        actual_subject = f"[TEST {i}/{count}] {subject}"
        logger.info(
            "test send %d/%d: user=%s to=%s attachments=%d",
            i,
            count,
            user.id,
            actual_to,
            len(attachments),
        )
        result = await sender.send(
            to_email=actual_to,
            subject=actual_subject,
            body=body,
            attachments=attachments,
        )
        if result.outcome is SendOutcome.SENT:
            sent += 1
        else:
            last_failure = result
            # Don't keep firing if the first attempt failed (likely an auth
            # problem) — surface the real error to the operator instead.
            if sent == 0:
                break
        if i < count:
            await asyncio.sleep(pause_seconds)
    return sent, last_failure
