"""replace notifications_enabled bool with notification_mode string

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-21 00:00:00

Values: NULL (not yet asked), 'per_send', 'daily', 'off'.

True  -> 'per_send'
False -> 'off'
NULL  -> NULL
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("notification_mode", sa.String(16), nullable=True))

    op.execute(
        "UPDATE users SET notification_mode = "
        "CASE "
        "WHEN notifications_enabled IS TRUE THEN 'per_send' "
        "WHEN notifications_enabled IS FALSE THEN 'off' "
        "ELSE NULL END"
    )

    with op.batch_alter_table("users") as batch:
        batch.drop_column("notifications_enabled")


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("notifications_enabled", sa.Boolean(), nullable=True))

    op.execute(
        "UPDATE users SET notifications_enabled = "
        "CASE "
        "WHEN notification_mode = 'per_send' THEN TRUE "
        "WHEN notification_mode = 'daily' THEN TRUE "
        "WHEN notification_mode = 'off' THEN FALSE "
        "ELSE NULL END"
    )

    with op.batch_alter_table("users") as batch:
        batch.drop_column("notification_mode")
