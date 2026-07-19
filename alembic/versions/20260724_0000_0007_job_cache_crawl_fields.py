"""add crawl fields to job_cache

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-24 00:00:00

When a Bundesagentur posting carries no contactable email, the dispatcher now
falls back to crawling the employer's own website. These columns persist the
outcome on the existing 24h cache row:
- contact_person: 'Frau/Herr <Name>' recovered from the site (optional).
- website_url: the employer URL that was crawled.
- crawl_attempted_at: set once a crawl ran, so we don't re-crawl the same
  employer on every tick within the cache TTL.
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("job_cache") as batch:
        batch.add_column(sa.Column("contact_person", sa.String(length=200), nullable=True))
        batch.add_column(sa.Column("website_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column("crawl_attempted_at", sa.DateTime(timezone=True), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("job_cache") as batch:
        batch.drop_column("crawl_attempted_at")
        batch.drop_column("website_url")
        batch.drop_column("contact_person")
