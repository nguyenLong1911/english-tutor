"""Persist lesson progress in PostgreSQL.

Revision ID: 0008_lesson_progress
Revises: 0007_processed_data_tables
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0008_lesson_progress"
down_revision: Union[str, None] = "0007_processed_data_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("lesson_progress"):
        return

    op.create_table(
        "lesson_progress",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("lesson_id", sa.String(length=128), primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="reading"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active_lesson_path", sa.String(length=512), nullable=True),
        sa.Column("practice_set_id", sa.String(length=255), nullable=True),
        sa.Column("practice_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("flashcards_completed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("latest_score", sa.Integer(), nullable=True),
        sa.Column("latest_total", sa.Integer(), nullable=True),
        sa.Column("latest_accuracy", sa.Float(), nullable=True),
        sa.Column("latest_practice_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_transition_from_step", sa.String(length=32), nullable=True),
        sa.Column("last_transition_to_step", sa.String(length=32), nullable=True),
        sa.Column("last_transition_reason", sa.String(length=64), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
    )
    op.create_index("ix_lesson_progress_user_updated", "lesson_progress", ["user_id", "updated_at"])
    op.create_index("ix_lesson_progress_user_current", "lesson_progress", ["user_id", "is_current"])


def downgrade() -> None:  # pragma: no cover
    op.drop_index("ix_lesson_progress_user_current", table_name="lesson_progress")
    op.drop_index("ix_lesson_progress_user_updated", table_name="lesson_progress")
    op.drop_table("lesson_progress")
