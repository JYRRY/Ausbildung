"""Bot-facing DB helpers.

Thin async wrappers over the M1 ORM models that hide the SQLAlchemy
boilerplate from the handler code. Every mutation is autocommitted by the
caller's ``session_scope()``; helpers don't ``commit()`` themselves so
multiple calls in one onboarding step stay atomic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from jyry.config import get_settings
from jyry.constants import PLAN_DAILY_QUOTA
from jyry.db.enums import ApplicationStatus, Language, Plan, SubscriptionStatus
from jyry.db.models import (
    Application,
    EmailDraft,
    Subscription,
    User,
    UserSpecialty,
    UserState,
)
from jyry.services.crypto import encrypt_secret
from jyry.services.rate_limiter import DailyQuotaLimiter


@dataclass(frozen=True, slots=True)
class StatusSummary:
    plan: str
    daily_quota: int
    sent_today: int
    remaining_today: int
    total_sent: int
    is_active: bool


async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    *,
    language: Language = Language.DE,
) -> User:
    existing = (
        await session.execute(select(User).where(User.telegram_id == telegram_id))
    ).scalar_one_or_none()
    if existing is None:
        existing = User(
            telegram_id=telegram_id,
            language=language,
            is_active=True,
            onboarding_complete=False,
        )
        session.add(existing)
        await session.flush()

    if telegram_id in get_settings().telegram_admin_ids:
        await _ensure_admin_subscription(session, existing)
    return existing


async def _ensure_admin_subscription(session: AsyncSession, user: User) -> None:
    """Idempotently grant the user a comp MAX subscription with no expiry."""
    sub = (
        await session.execute(select(Subscription).where(Subscription.user_id == user.id))
    ).scalar_one_or_none()
    quota = PLAN_DAILY_QUOTA["max"]
    if sub is None:
        session.add(
            Subscription(
                user_id=user.id,
                plan=Plan.MAX,
                status=SubscriptionStatus.ACTIVE,
                expires_at=None,
                daily_quota=quota,
                lemonsqueezy_subscription_id=None,
                lemonsqueezy_customer_id=None,
            )
        )
    elif (
        sub.plan != Plan.MAX
        or sub.status != SubscriptionStatus.ACTIVE
        or sub.expires_at is not None
        or sub.daily_quota != quota
    ):
        sub.plan = Plan.MAX
        sub.status = SubscriptionStatus.ACTIVE
        sub.expires_at = None
        sub.daily_quota = quota
    await session.flush()


async def load_user(session: AsyncSession, user_id: int) -> User | None:
    return (
        await session.execute(
            select(User)
            .where(User.id == user_id)
            .options(
                selectinload(User.subscription),
                selectinload(User.email_draft),
                selectinload(User.specialties),
                selectinload(User.states),
            )
        )
    ).scalar_one_or_none()


async def set_full_name(session: AsyncSession, user_id: int, name: str) -> None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.full_name = name.strip()
    await session.flush()


async def set_gmail_address(
    session: AsyncSession, user_id: int, address: str
) -> None:
    """Persist the Gmail address alone so progress survives bailing mid-step."""
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.gmail_address = address.strip().lower()
    await session.flush()


async def set_gmail(
    session: AsyncSession,
    user_id: int,
    *,
    address: str,
    app_password_plaintext: str,
) -> None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.gmail_address = address.strip().lower()
    user.gmail_app_password_enc = encrypt_secret(app_password_plaintext.strip())
    await session.flush()


async def replace_specialties(
    session: AsyncSession, user_id: int, keywords: list[str]
) -> None:
    await session.execute(
        delete(UserSpecialty).where(UserSpecialty.user_id == user_id)
    )
    for kw in keywords:
        session.add(UserSpecialty(user_id=user_id, specialty_keyword=kw))
    await session.flush()


async def replace_states(
    session: AsyncSession, user_id: int, codes: list[str]
) -> None:
    await session.execute(delete(UserState).where(UserState.user_id == user_id))
    for code in codes:
        session.add(UserState(user_id=user_id, state_code=code))
    await session.flush()


async def upsert_draft(
    session: AsyncSession,
    user_id: int,
    *,
    subject_template: str | None = None,
    body_template: str | None = None,
    attachments_meta: list[dict[str, Any]] | None = None,
) -> EmailDraft:
    draft = (
        await session.execute(select(EmailDraft).where(EmailDraft.user_id == user_id))
    ).scalar_one_or_none()
    if draft is None:
        draft = EmailDraft(
            user_id=user_id,
            subject_template=subject_template or "",
            body_template=body_template or "",
            attachments_meta=attachments_meta or [],
        )
        session.add(draft)
        await session.flush()
        return draft
    if subject_template is not None:
        draft.subject_template = subject_template
    if body_template is not None:
        draft.body_template = body_template
    if attachments_meta is not None:
        draft.attachments_meta = attachments_meta
    await session.flush()
    return draft


async def append_attachment(
    session: AsyncSession,
    user_id: int,
    *,
    filename: str,
    file_id: str,
    mime: str,
    size: int,
) -> EmailDraft:
    draft = await upsert_draft(session, user_id)
    metas = list(draft.attachments_meta or [])
    if not any(m.get("telegram_file_id") == file_id for m in metas):
        metas.append(
            {
                "filename": filename,
                "telegram_file_id": file_id,
                "mime": mime,
                "size": size,
            }
        )
    draft.attachments_meta = metas
    await session.flush()
    return draft


async def remove_attachment(
    session: AsyncSession, user_id: int, file_id: str
) -> EmailDraft:
    draft = await upsert_draft(session, user_id)
    metas = [
        m for m in (draft.attachments_meta or []) if m.get("telegram_file_id") != file_id
    ]
    draft.attachments_meta = metas
    await session.flush()
    return draft


async def remove_attachment_at(
    session: AsyncSession, user_id: int, index: int
) -> EmailDraft:
    """Drop the attachment at ``index`` from the user's draft.

    Indexes are referenced from inline-keyboard buttons because callback_data
    has a 64-byte limit which real Telegram file_ids blow past.
    """
    draft = await upsert_draft(session, user_id)
    metas = list(draft.attachments_meta or [])
    if 0 <= index < len(metas):
        metas.pop(index)
        draft.attachments_meta = metas
        await session.flush()
    return draft


async def mark_onboarded(session: AsyncSession, user_id: int) -> None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.onboarding_complete = True
    user.is_active = True
    await session.flush()


async def set_active(session: AsyncSession, user_id: int, *, is_active: bool) -> None:
    user = (await session.execute(select(User).where(User.id == user_id))).scalar_one()
    user.is_active = is_active
    await session.flush()


async def grant_free_trial(session: AsyncSession, user_id: int) -> Subscription:
    """Activate a 3-day Free trial."""
    from datetime import timedelta

    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user_id)
        )
    ).scalar_one_or_none()
    now = datetime.now(tz=UTC)
    if sub is None:
        sub = Subscription(
            user_id=user_id,
            plan=Plan.FREE,
            status=SubscriptionStatus.ACTIVE,
            started_at=now,
            expires_at=now + timedelta(days=3),
            daily_quota=PLAN_DAILY_QUOTA["free"],
            emails_sent_today=0,
        )
        session.add(sub)
    else:
        sub.plan = Plan.FREE
        sub.status = SubscriptionStatus.ACTIVE
        sub.started_at = now
        sub.expires_at = now + timedelta(days=3)
        sub.daily_quota = PLAN_DAILY_QUOTA["free"]
    await session.flush()
    return sub


async def status_summary(
    session: AsyncSession, limiter: DailyQuotaLimiter, user_id: int
) -> StatusSummary:
    user = await load_user(session, user_id)
    if user is None:
        raise ValueError(f"unknown user_id={user_id}")
    sub = user.subscription
    plan_value = (
        sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)
    ) if (sub and sub.plan) else "free"
    quota = PLAN_DAILY_QUOTA.get(plan_value, PLAN_DAILY_QUOTA["free"])
    sent_today = await limiter.usage(user_id)
    remaining = await limiter.remaining(user_id, quota)
    total_sent = (
        await session.execute(
            select(Application.id).where(
                Application.user_id == user_id,
                Application.status == ApplicationStatus.SENT.value,
            )
        )
    ).all()
    return StatusSummary(
        plan=plan_value,
        daily_quota=quota,
        sent_today=sent_today,
        remaining_today=remaining,
        total_sent=len(total_sent),
        is_active=user.is_active,
    )


def plan_value(user: User) -> str:
    """Return the user's plan as a lowercase string ('free' if no sub)."""
    sub = user.subscription
    if sub is None or sub.plan is None:
        return "free"
    return sub.plan.value if hasattr(sub.plan, "value") else str(sub.plan)


def can_use_templates(user: User) -> bool:
    """Template-suggestion feature is gated to Pro and Max plans."""
    return plan_value(user) in {"pro", "max"}


def has_active_subscription(user: User) -> bool:
    sub = user.subscription
    if sub is None:
        return False
    if sub.status not in {SubscriptionStatus.ACTIVE, SubscriptionStatus.PAST_DUE}:
        return False
    if sub.expires_at is not None:
        expires = sub.expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=UTC)
        if expires < datetime.now(tz=UTC):
            return False
    return True


async def upsert_subscription(
    session: AsyncSession,
    *,
    telegram_id: int,
    plan: Plan,
    status: SubscriptionStatus,
    expires_at: datetime | None,
    lemonsqueezy_subscription_id: str | None,
    lemonsqueezy_customer_id: str | None,
    daily_quota: int,
) -> Subscription:
    """Create or update the subscription row for the given Telegram user."""
    user = await get_or_create_user(session, telegram_id)
    sub = (
        await session.execute(
            select(Subscription).where(Subscription.user_id == user.id)
        )
    ).scalar_one_or_none()
    now = datetime.now(tz=UTC)
    if sub is None:
        sub = Subscription(
            user_id=user.id,
            plan=plan,
            status=status,
            started_at=now,
            expires_at=expires_at,
            daily_quota=daily_quota,
            lemonsqueezy_subscription_id=lemonsqueezy_subscription_id,
            lemonsqueezy_customer_id=lemonsqueezy_customer_id,
        )
        session.add(sub)
    else:
        sub.plan = plan
        sub.status = status
        sub.expires_at = expires_at
        sub.daily_quota = daily_quota
        if lemonsqueezy_subscription_id is not None:
            sub.lemonsqueezy_subscription_id = lemonsqueezy_subscription_id
        if lemonsqueezy_customer_id is not None:
            sub.lemonsqueezy_customer_id = lemonsqueezy_customer_id
    await session.flush()
    return sub
