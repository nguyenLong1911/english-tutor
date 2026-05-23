"""Repair missing core tables on stamped or partially initialized databases.

Revision ID: 0005_repair_missing_core_schema
Revises: 0004_session_log
Create Date: 2026-05-10
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0005_repair_missing_core_schema"
down_revision: Union[str, None] = "0004_session_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table_name: str, column_name: str) -> bool:
    return any(column["name"] == column_name for column in inspector.get_columns(table_name))


def _has_index(inspector: sa.Inspector, table_name: str, index_name: str) -> bool:
    return any(index["name"] == index_name for index in inspector.get_indexes(table_name))


def _has_unique_constraint(inspector: sa.Inspector, table_name: str, constraint_name: str) -> bool:
    return any(
        constraint["name"] == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("user_profile"):
        op.create_table(
            "user_profile",
            sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("password_hash", sa.String(255), nullable=True),
            sa.Column("display_name", sa.String(100), nullable=True),
            sa.Column("cefr_level", sa.String(2), nullable=False),
            sa.Column("industry", sa.String(50), nullable=False),
            sa.Column("learning_goals", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("email", name="uq_user_email"),
        )
        inspector = sa.inspect(bind)
    else:
        if not _has_column(inspector, "user_profile", "password_hash"):
            op.add_column("user_profile", sa.Column("password_hash", sa.String(length=255), nullable=True))
            inspector = sa.inspect(bind)
        if not _has_unique_constraint(inspector, "user_profile", "uq_user_email"):
            with op.batch_alter_table("user_profile") as batch_op:
                batch_op.create_unique_constraint("uq_user_email", ["email"])
            inspector = sa.inspect(bind)

    if not inspector.has_table("vocabulary"):
        op.create_table(
            "vocabulary",
            sa.Column("word_id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("word", sa.String(100), nullable=False),
            sa.Column("pos", sa.String(20), nullable=False),
            sa.Column("cefr_level", sa.String(2), nullable=False),
            sa.Column("definition_vi", sa.Text(), nullable=False),
            sa.Column("example", sa.Text(), nullable=False),
            sa.Column("industry_tags", postgresql.ARRAY(sa.String(50)), nullable=False, server_default="{}"),
            sa.Column("confusion_with", postgresql.ARRAY(sa.String(100)), nullable=True),
            sa.Column("frequency_rank", sa.Integer(), nullable=True),
            sa.UniqueConstraint("word", "pos", name="uq_vocab_word_pos"),
        )
        op.create_index("ix_vocabulary_word", "vocabulary", ["word"])
        op.create_index("ix_vocabulary_cefr_level", "vocabulary", ["cefr_level"])
        inspector = sa.inspect(bind)
    else:
        if not _has_unique_constraint(inspector, "vocabulary", "uq_vocab_word_pos"):
            with op.batch_alter_table("vocabulary") as batch_op:
                batch_op.create_unique_constraint("uq_vocab_word_pos", ["word", "pos"])
            inspector = sa.inspect(bind)
        if not _has_index(inspector, "vocabulary", "ix_vocabulary_word"):
            op.create_index("ix_vocabulary_word", "vocabulary", ["word"])
            inspector = sa.inspect(bind)
        if not _has_index(inspector, "vocabulary", "ix_vocabulary_cefr_level"):
            op.create_index("ix_vocabulary_cefr_level", "vocabulary", ["cefr_level"])
            inspector = sa.inspect(bind)

    if not inspector.has_table("user_vocabulary"):
        op.create_table(
            "user_vocabulary",
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column(
                "word_id",
                sa.Integer(),
                sa.ForeignKey("vocabulary.word_id", ondelete="CASCADE"),
                primary_key=True,
            ),
            sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
            sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("next_review", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
            sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("total_reviews", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        )
        op.create_index("ix_user_vocabulary_next_review", "user_vocabulary", ["next_review"])
        inspector = sa.inspect(bind)
    elif not _has_index(inspector, "user_vocabulary", "ix_user_vocabulary_next_review"):
        op.create_index("ix_user_vocabulary_next_review", "user_vocabulary", ["next_review"])
        inspector = sa.inspect(bind)

    if not inspector.has_table("metrics_log"):
        op.create_table(
            "metrics_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("captured_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("total_users", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_reviews", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_reviews_per_user", sa.Float(), nullable=False, server_default="0"),
            sa.Column("mastered_words", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("vocabulary_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("avg_token_per_session", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_today", sa.Float(), nullable=False, server_default="0"),
            sa.Column("p95_latency_ms", sa.Float(), nullable=False, server_default="0"),
            sa.Column("snapshot_source", sa.String(length=32), nullable=False, server_default="hourly_job"),
        )
        op.create_index("ix_metrics_log_captured_at", "metrics_log", ["captured_at"])
        inspector = sa.inspect(bind)
    elif not _has_index(inspector, "metrics_log", "ix_metrics_log_captured_at"):
        op.create_index("ix_metrics_log_captured_at", "metrics_log", ["captured_at"])
        inspector = sa.inspect(bind)

    if not inspector.has_table("session_log"):
        op.create_table(
            "session_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column(
                "user_id",
                postgresql.UUID(as_uuid=True),
                sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
            sa.Column("intent", sa.String(length=16), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=False, server_default="mock"),
            sa.Column("model", sa.String(length=64), nullable=True),
            sa.Column("tokens_in", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("tokens_out", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0.0"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("was_correct", sa.Boolean(), nullable=True),
            sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
        )
        op.create_index("ix_session_log_user_created", "session_log", ["user_id", "created_at"])
        op.create_index("ix_session_log_created_at", "session_log", ["created_at"])
    else:
        if not _has_index(inspector, "session_log", "ix_session_log_user_created"):
            op.create_index("ix_session_log_user_created", "session_log", ["user_id", "created_at"])
            inspector = sa.inspect(bind)
        if not _has_index(inspector, "session_log", "ix_session_log_created_at"):
            op.create_index("ix_session_log_created_at", "session_log", ["created_at"])


def downgrade() -> None:
    # This migration repairs drift on existing databases. Downgrading it
    # should not drop live data that may have been reconstructed here.
    pass
