"""Database enums shared by models and the rest of the app."""

from __future__ import annotations

import enum


class Language(str, enum.Enum):
    AR = "ar"
    DE = "de"


class Plan(str, enum.Enum):
    FREE = "free"
    PLUS = "plus"
    PRO = "pro"
    MAX = "max"


class SubscriptionStatus(str, enum.Enum):
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    PAST_DUE = "past_due"


class ApplicationStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    FAILED = "failed"
    BOUNCED = "bounced"
