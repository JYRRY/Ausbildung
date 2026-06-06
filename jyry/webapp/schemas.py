"""Pydantic response schemas for the dashboard API.

Kept separate from db.models so the public JSON shape is decoupled from the
DB layout (no leaking of internal columns like fernet-encrypted blobs).
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SubscriptionOut(_ORM):
    plan: str
    status: str
    started_at: datetime | None
    expires_at: datetime | None
    emails_sent_today: int
    daily_quota: int
    auto_renew: bool


class MeOut(_ORM):
    id: int
    email: str | None
    google_picture: str | None
    full_name: str | None
    gmail_address: str | None
    has_app_password: bool
    telegram_id: int | None
    telegram_linked: bool
    is_admin: bool
    is_active: bool
    onboarding_complete: bool
    notification_mode: str | None
    accepted_terms_at: datetime | None
    accepted_paid_terms_at: datetime | None
    trial_started_at: datetime | None
    subscription: SubscriptionOut | None


class ApplicationOut(_ORM):
    id: int
    job_title: str | None
    sent_at: datetime | None
    status: str
    error_message: str | None
    created_at: datetime


class ApplicationsPage(BaseModel):
    items: list[ApplicationOut]
    total: int
    page: int
    page_size: int


class NotificationPatch(BaseModel):
    mode: str  # one of "per_send" | "daily" | "off"


class ProfilePatch(BaseModel):
    full_name: str | None = None
    gmail_address: str | None = None


class AppPasswordPatch(BaseModel):
    app_password: str


class ActivePatch(BaseModel):
    is_active: bool


# --- Onboarding / setup ----------------------------------------------------

class SpecialtyRef(BaseModel):
    keyword: str
    label_de: str
    label_ar: str


class StateRef(BaseModel):
    code: str
    label_de: str
    label_ar: str


class AttachmentOut(BaseModel):
    index: int
    filename: str
    size: int
    mime: str | None
    source: str  # "local" (web upload) | "telegram" (bot upload)


class OnboardingOut(BaseModel):
    # Current selections
    specialties: list[str]
    states: list[str]
    subject_template: str
    body_template: str
    attachments: list[AttachmentOut]
    # Reference data + plan limits (None = unlimited)
    all_specialties: list[SpecialtyRef]
    all_states: list[StateRef]
    max_specialties: int | None
    max_states: int | None
    # Readiness
    has_app_password: bool
    ready: bool
    onboarding_complete: bool
    plan: str


class SelectionPut(BaseModel):
    specialties: list[str]
    states: list[str]


class TemplatePut(BaseModel):
    subject_template: str
    body_template: str


# --- Admin -----------------------------------------------------------------

class AdminUserRow(_ORM):
    id: int
    email: str | None
    full_name: str | None
    telegram_id: int | None
    plan: str
    is_active: bool
    is_admin: bool
    onboarding_complete: bool
    notification_mode: str | None
    created_at: datetime
    last_seen_at: datetime | None
    emails_sent_today: int
    emails_sent_total: int


class AdminUsersPage(BaseModel):
    items: list[AdminUserRow]
    total: int
    page: int
    page_size: int


class AdminStats(BaseModel):
    users_total: int
    users_active: int
    users_by_plan: dict[str, int]
    emails_sent_today: int
    emails_sent_total: int
