"""rename lemonsqueezy columns to paddle

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-20 00:00:00

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.alter_column(
            "lemonsqueezy_subscription_id",
            new_column_name="paddle_subscription_id",
        )
        batch.alter_column(
            "lemonsqueezy_customer_id",
            new_column_name="paddle_customer_id",
        )
        batch.drop_index("ix_subscriptions_lemonsqueezy_subscription_id")
        batch.create_index(
            "ix_subscriptions_paddle_subscription_id",
            ["paddle_subscription_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_index("ix_subscriptions_paddle_subscription_id")
        batch.alter_column(
            "paddle_subscription_id",
            new_column_name="lemonsqueezy_subscription_id",
        )
        batch.alter_column(
            "paddle_customer_id",
            new_column_name="lemonsqueezy_customer_id",
        )
        batch.create_index(
            "ix_subscriptions_lemonsqueezy_subscription_id",
            ["lemonsqueezy_subscription_id"],
        )
