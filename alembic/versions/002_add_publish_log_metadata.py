"""add publish log metadata

Revision ID: 002_add_publish_log_metadata
Revises: 001_create_stage1_tables
Create Date: 2026-05-15 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "002_add_publish_log_metadata"
down_revision: str | None = "001_create_stage1_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("publish_logs", sa.Column("metadata_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("publish_logs", "metadata_json")
