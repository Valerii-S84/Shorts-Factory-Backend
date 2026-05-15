"""create stage1 tables

Revision ID: 001_create_stage1_tables
Revises:
Create Date: 2026-05-15 00:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "001_create_stage1_tables"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "video_jobs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("quiz_id", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("locale", sa.String(length=16), nullable=False),
        sa.Column("level", sa.String(length=64), nullable=True),
        sa.Column("topic", sa.String(length=128), nullable=True),
        sa.Column("target_platforms", sa.JSON(), nullable=False),
        sa.Column("script_json", sa.JSON(), nullable=True),
        sa.Column("render_plan_json", sa.JSON(), nullable=True),
        sa.Column("video_path", sa.Text(), nullable=True),
        sa.Column("duration_sec", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_video_jobs_quiz_id", "video_jobs", ["quiz_id"])
    op.create_index("ix_video_jobs_status", "video_jobs", ["status"])

    op.create_table(
        "templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("duration_sec", sa.Float(), nullable=False),
        sa.Column("frame_count", sa.Integer(), nullable=False),
        sa.Column("style_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "publish_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["video_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_publish_logs_job_id", "publish_logs", ["job_id"])
    op.create_index("ix_publish_logs_platform", "publish_logs", ["platform"])

    op.create_table(
        "render_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("step", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["video_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_render_logs_job_id", "render_logs", ["job_id"])
    op.create_index("ix_render_logs_step", "render_logs", ["step"])

    op.create_table(
        "video_assets",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("checksum", sa.String(length=128), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["video_jobs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_video_assets_job_id", "video_assets", ["job_id"])
    op.create_index("ix_video_assets_type", "video_assets", ["type"])


def downgrade() -> None:
    op.drop_index("ix_video_assets_type", table_name="video_assets")
    op.drop_index("ix_video_assets_job_id", table_name="video_assets")
    op.drop_table("video_assets")
    op.drop_index("ix_render_logs_step", table_name="render_logs")
    op.drop_index("ix_render_logs_job_id", table_name="render_logs")
    op.drop_table("render_logs")
    op.drop_index("ix_publish_logs_platform", table_name="publish_logs")
    op.drop_index("ix_publish_logs_job_id", table_name="publish_logs")
    op.drop_table("publish_logs")
    op.drop_table("templates")
    op.drop_index("ix_video_jobs_status", table_name="video_jobs")
    op.drop_index("ix_video_jobs_quiz_id", table_name="video_jobs")
    op.drop_table("video_jobs")
