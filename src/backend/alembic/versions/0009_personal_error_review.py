"""Personal error review and flashcards.

Revision ID: 0009_personal_error_review
Revises: 0008_lesson_progress
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0009_personal_error_review"
down_revision: Union[str, None] = "0008_lesson_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("user_error_event"):
        op.create_table(
            "user_error_event",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("source", sa.String(16), nullable=False),
            sa.Column("original_text", sa.Text, nullable=False),
            sa.Column("corrected_text", sa.Text, nullable=True),
            sa.Column("error_type", sa.String(64), nullable=False, server_default="grammar"),
            sa.Column("error_pattern", sa.Text, nullable=False),
            sa.Column("normalized_error_pattern", sa.String(255), nullable=False),
            sa.Column("explanation_vi", sa.Text, nullable=True),
            sa.Column("cefr_level", sa.String(2), nullable=True),
            sa.Column("industry", sa.String(64), nullable=True),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0.0"),
            sa.Column("source_metadata", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_user_error_event_user_id", "user_error_event", ["user_id"])
        op.create_index("ix_user_error_event_source", "user_error_event", ["source"])
        op.create_index("ix_user_error_event_error_type", "user_error_event", ["error_type"])
        op.create_index("ix_user_error_event_normalized_error_pattern", "user_error_event", ["normalized_error_pattern"])
        op.create_index("ix_user_error_event_created_at", "user_error_event", ["created_at"])

    if not inspector.has_table("user_flashcard"):
        op.create_table(
            "user_flashcard",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("error_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_error_event.id", ondelete="SET NULL"), nullable=True),
            sa.Column("card_type", sa.String(32), nullable=False, server_default="correction_cloze"),
            sa.Column("front", sa.Text, nullable=False),
            sa.Column("back", sa.Text, nullable=False),
            sa.Column("cloze_text", sa.Text, nullable=False),
            sa.Column("explanation_vi", sa.Text, nullable=True),
            sa.Column("error_type", sa.String(64), nullable=False, server_default="grammar"),
            sa.Column("normalized_error_pattern", sa.String(255), nullable=False),
            sa.Column("source", sa.String(16), nullable=False, server_default="chat"),
            sa.Column("active", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_user_flashcard_user_id", "user_flashcard", ["user_id"])
        op.create_index("ix_user_flashcard_error_event_id", "user_flashcard", ["error_event_id"])
        op.create_index("ix_user_flashcard_error_type", "user_flashcard", ["error_type"])
        op.create_index("ix_user_flashcard_normalized_error_pattern", "user_flashcard", ["normalized_error_pattern"])
        op.create_index("ix_user_flashcard_created_at", "user_flashcard", ["created_at"])

    if not inspector.has_table("user_flashcard_review"):
        op.create_table(
            "user_flashcard_review",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), primary_key=True),
            sa.Column("flashcard_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_flashcard.id", ondelete="CASCADE"), primary_key=True),
            sa.Column("ease_factor", sa.Float, nullable=False, server_default="2.5"),
            sa.Column("interval_days", sa.Integer, nullable=False, server_default="1"),
            sa.Column("repetitions", sa.Integer, nullable=False, server_default="0"),
            sa.Column("next_review", sa.Date, nullable=False, server_default=sa.text("CURRENT_DATE")),
            sa.Column("first_seen_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
            sa.Column("last_reviewed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("total_reviews", sa.Integer, nullable=False, server_default="0"),
            sa.Column("mastered", sa.Boolean, nullable=False, server_default="false"),
        )
        op.create_index("ix_user_flashcard_review_next_review", "user_flashcard_review", ["next_review"])


def downgrade() -> None:  # pragma: no cover
    op.drop_table("user_flashcard_review")
    op.drop_table("user_flashcard")
    op.drop_table("user_error_event")
