"""add applicant postal fields to users

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-25 00:00:00

The dispatcher now auto-generates a German Anschreiben (cover letter) per
employer and attaches it to the application. Its letterhead needs the
applicant's postal address and phone, which the web/bot onboarding collects:
- postal_street:   e.g. "Musterstraße 12"
- postal_plz_city: "PLZ City" as a single line, e.g. "80331 München"
- phone:           free-form contact number

All nullable — a missing line is simply omitted from the letter.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("postal_street", sa.String(length=200), nullable=True))
        batch.add_column(
            sa.Column("postal_plz_city", sa.String(length=200), nullable=True)
        )
        batch.add_column(sa.Column("phone", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_column("phone")
        batch.drop_column("postal_plz_city")
        batch.drop_column("postal_street")
