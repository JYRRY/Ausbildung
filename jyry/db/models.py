"""ORM models for JYRY AI.

All timestamps are timezone-aware. Sensitive material (the user's Gmail App
Password) is stored as Fernet ciphertext bytes; encryption/decryption is
handled by jyry.services.crypto, not by the model layer.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import (
    JSON,
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from jyry.db.base import Base, TimestampMixin
from jyry.db.enums import (
    ApplicationStatus,
    Language,
    Plan,
    SubscriptionStatus,
)

if TYPE_CHECKING:
    pass

# JSONB on PostgreSQL (production) and JSON on SQLite (tests).
JSONType = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int | None] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )
    # Web-side identifiers — populated when the user signs in via Google.
    google_oauth_sub: Mapped[str | None] = mapped_column(
        String(64), unique=True, nullable=True, index=True
    )
    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    google_picture: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_admin: Mapped[bool] = mapped_column(default=False, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(200))
    # Applicant postal details — fed into the Anschreiben (cover-letter) header
    # by the dispatcher. Optional: a missing line is simply omitted from the
    # letter. ``postal_plz_city`` holds "PLZ City" as one field (e.g. "80331
    # München"); ``phone`` is free-form.
    postal_street: Mapped[str | None] = mapped_column(String(200))
    postal_plz_city: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(64))
    gmail_address: Mapped[str | None] = mapped_column(String(320), index=True)
    # Fernet ciphertext of the user's Gmail App Password.
    gmail_app_password_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    language: Mapped[Language] = mapped_column(
        String(2), nullable=False, default=Language.AR
    )
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
    onboarding_complete: Mapped[bool] = mapped_column(default=False, nullable=False)
    accepted_terms_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    accepted_paid_terms_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    trial_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # None = user has not yet been prompted.
    # 'per_send' = ping after each email.
    # 'daily'    = single end-of-day summary.
    # 'off'      = no notifications.
    notification_mode: Mapped[str | None] = mapped_column(String(16), default=None)

    subscription: Mapped[Subscription | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    applications: Mapped[list[Application]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    email_draft: Mapped[EmailDraft | None] = relationship(
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    specialties: Mapped[list[UserSpecialty]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    states: Mapped[list[UserState]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    plan: Mapped[Plan] = mapped_column(String(16), nullable=False, default=Plan.FREE)
    status: Mapped[SubscriptionStatus] = mapped_column(
        String(16), nullable=False, default=SubscriptionStatus.ACTIVE
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    daily_quota: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    emails_sent_today: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reset_on: Mapped[date | None] = mapped_column(Date)

    # Paddle linkage
    paddle_subscription_id: Mapped[str | None] = mapped_column(String(64), index=True)
    paddle_customer_id: Mapped[str | None] = mapped_column(String(64))

    user: Mapped[User] = relationship(back_populates="subscription")


class Application(Base):
    """One row per (user, employer) — UNIQUE prevents re-contacting an employer."""

    __tablename__ = "applications"
    __table_args__ = (UniqueConstraint("user_id", "kundennummer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    kundennummer: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    job_title: Mapped[str | None] = mapped_column(String(255))
    email_to: Mapped[str | None] = mapped_column(String(320))
    email_subject: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[ApplicationStatus] = mapped_column(
        String(16), nullable=False, default=ApplicationStatus.QUEUED, index=True
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    queued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)

    user: Mapped[User] = relationship(back_populates="applications")


class JobCache(Base):
    """24-hour cache of Bundesagentur job postings keyed by kundennummer."""

    __tablename__ = "job_cache"

    kundennummer: Mapped[str] = mapped_column(String(64), primary_key=True)
    company_name: Mapped[str | None] = mapped_column(String(255))
    job_title: Mapped[str | None] = mapped_column(String(255))
    location: Mapped[str | None] = mapped_column(String(255))
    state_code: Mapped[str | None] = mapped_column(String(8), index=True)
    specialty_keyword: Mapped[str | None] = mapped_column(String(128), index=True)
    email: Mapped[str | None] = mapped_column(String(320))
    # Populated when the posting had no email and we crawled the employer site.
    contact_person: Mapped[str | None] = mapped_column(String(200))
    website_url: Mapped[str | None] = mapped_column(String(500))
    crawl_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSONType, nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


class EmailDraft(Base, TimestampMixin):
    """One reusable subject + body + attachments per user."""

    __tablename__ = "email_drafts"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    subject_template: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    body_template: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # List of {filename, telegram_file_id, size, mime}
    attachments_meta: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )

    user: Mapped[User] = relationship(back_populates="email_draft")


class UserSpecialty(Base):
    """User <-> specialty many-to-many (one of the 13 supported keywords)."""

    __tablename__ = "user_specialties"
    __table_args__ = (UniqueConstraint("user_id", "specialty_keyword"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    specialty_keyword: Mapped[str] = mapped_column(String(128), nullable=False, index=True)

    user: Mapped[User] = relationship(back_populates="specialties")


class UserState(Base):
    """User <-> Bundesland (one of the 16 supported state codes)."""

    __tablename__ = "user_states"
    __table_args__ = (UniqueConstraint("user_id", "state_code"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    state_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)

    user: Mapped[User] = relationship(back_populates="states")
