"""add google oauth + admin + email columns to users

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-23 00:00:00

Adds the columns the web dashboard needs:
- google_oauth_sub: stable Google account identifier (the OIDC 'sub' claim)
- email: the Google email (separate from gmail_address used for sending)
- is_admin: gates the /app/admin section
- google_picture: avatar URL for the dashboard

Also relaxes the NOT NULL on telegram_id so users can sign up via the web
without ever linking Telegram (they can still link it later for notifications).
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("google_oauth_sub", sa.String(64), nullable=True))
        batch.add_column(sa.Column("email", sa.String(320), nullable=True))
        batch.add_column(sa.Column("google_picture", sa.String(500), nullable=True))
        batch.add_column(
            sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch.alter_column("telegram_id", existing_type=sa.BigInteger(), nullable=True)
        batch.create_index(
            "ix_users_google_oauth_sub", ["google_oauth_sub"], unique=True
        )
        batch.create_index("ix_users_email", ["email"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_email")
        batch.drop_index("ix_users_google_oauth_sub")
        batch.alter_column("telegram_id", existing_type=sa.BigInteger(), nullable=False)
        batch.drop_column("is_admin")
        batch.drop_column("google_picture")
        batch.drop_column("email")
        batch.drop_column("google_oauth_sub")
