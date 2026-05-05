"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-05-05 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(length=200), nullable=True),
        sa.Column("gmail_address", sa.String(length=320), nullable=True),
        sa.Column("gmail_app_password_enc", sa.LargeBinary(), nullable=True),
        sa.Column("language", sa.String(length=2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("onboarding_complete", sa.Boolean(), nullable=False),
        sa.Column("accepted_terms_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trial_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("telegram_id", name=op.f("uq_users_telegram_id")),
    )
    op.create_index(op.f("ix_users_telegram_id"), "users", ["telegram_id"])
    op.create_index(op.f("ix_users_gmail_address"), "users", ["gmail_address"])

    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("plan", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("daily_quota", sa.Integer(), nullable=False),
        sa.Column("emails_sent_today", sa.Integer(), nullable=False),
        sa.Column("last_reset_on", sa.Date(), nullable=True),
        sa.Column("lemonsqueezy_subscription_id", sa.String(length=64), nullable=True),
        sa.Column("lemonsqueezy_customer_id", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_subscriptions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_subscriptions")),
        sa.UniqueConstraint("user_id", name=op.f("uq_subscriptions_user_id")),
    )
    op.create_index(
        op.f("ix_subscriptions_expires_at"), "subscriptions", ["expires_at"]
    )
    op.create_index(
        op.f("ix_subscriptions_lemonsqueezy_subscription_id"),
        "subscriptions",
        ["lemonsqueezy_subscription_id"],
    )

    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kundennummer", sa.String(length=64), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("email_to", sa.String(length=320), nullable=True),
        sa.Column("email_subject", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "queued_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_applications_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        sa.UniqueConstraint(
            "user_id",
            "kundennummer",
            name=op.f("uq_applications_user_id_kundennummer"),
        ),
    )
    op.create_index(op.f("ix_applications_user_id"), "applications", ["user_id"])
    op.create_index(
        op.f("ix_applications_kundennummer"), "applications", ["kundennummer"]
    )
    op.create_index(op.f("ix_applications_status"), "applications", ["status"])
    op.create_index(op.f("ix_applications_sent_at"), "applications", ["sent_at"])

    op.create_table(
        "job_cache",
        sa.Column("kundennummer", sa.String(length=64), nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=True),
        sa.Column("job_title", sa.String(length=255), nullable=True),
        sa.Column("location", sa.String(length=255), nullable=True),
        sa.Column("state_code", sa.String(length=8), nullable=True),
        sa.Column("specialty_keyword", sa.String(length=128), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column(
            "raw_data",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "fetched_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("kundennummer", name=op.f("pk_job_cache")),
    )
    op.create_index(op.f("ix_job_cache_state_code"), "job_cache", ["state_code"])
    op.create_index(
        op.f("ix_job_cache_specialty_keyword"), "job_cache", ["specialty_keyword"]
    )
    op.create_index(op.f("ix_job_cache_fetched_at"), "job_cache", ["fetched_at"])

    op.create_table(
        "email_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("subject_template", sa.String(length=500), nullable=False),
        sa.Column("body_template", sa.Text(), nullable=False),
        sa.Column("attachments_meta", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_email_drafts_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_email_drafts")),
        sa.UniqueConstraint("user_id", name=op.f("uq_email_drafts_user_id")),
    )

    op.create_table(
        "user_specialties",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("specialty_keyword", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_specialties_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_specialties")),
        sa.UniqueConstraint(
            "user_id",
            "specialty_keyword",
            name=op.f("uq_user_specialties_user_id_specialty_keyword"),
        ),
    )
    op.create_index(
        op.f("ix_user_specialties_user_id"), "user_specialties", ["user_id"]
    )
    op.create_index(
        op.f("ix_user_specialties_specialty_keyword"),
        "user_specialties",
        ["specialty_keyword"],
    )

    op.create_table(
        "user_states",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("state_code", sa.String(length=8), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_states_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_states")),
        sa.UniqueConstraint(
            "user_id",
            "state_code",
            name=op.f("uq_user_states_user_id_state_code"),
        ),
    )
    op.create_index(op.f("ix_user_states_user_id"), "user_states", ["user_id"])
    op.create_index(op.f("ix_user_states_state_code"), "user_states", ["state_code"])


def downgrade() -> None:
    op.drop_table("user_states")
    op.drop_table("user_specialties")
    op.drop_table("email_drafts")
    op.drop_table("job_cache")
    op.drop_table("applications")
    op.drop_table("subscriptions")
    op.drop_table("users")
