"""Target architecture tables & columns (mood, context, DNA, email outbox,
delete_request, RBAC role + timezone).

Revision ID: 0006_target_architecture
Revises: 0005_repair_missing_core_schema
Create Date: 2026-05-11
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0006_target_architecture"
down_revision: Union[str, None] = "0005_repair_missing_core_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- user_profile: role / timezone / mood_default -----------------------
    if inspector.has_table("user_profile"):
        if not _has_column(inspector, "user_profile", "role"):
            op.add_column(
                "user_profile",
                sa.Column("role", sa.String(16), nullable=False, server_default="user"),
            )
        if not _has_column(inspector, "user_profile", "timezone"):
            op.add_column(
                "user_profile",
                sa.Column(
                    "timezone",
                    sa.String(64),
                    nullable=False,
                    server_default="Asia/Ho_Chi_Minh",
                ),
            )
        if not _has_column(inspector, "user_profile", "mood_default"):
            op.add_column(
                "user_profile",
                sa.Column("mood_default", sa.String(16), nullable=True),
            )

    # --- mood_log -----------------------------------------------------------
    if not inspector.has_table("mood_log"):
        op.create_table(
            "mood_log",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("mood", sa.String(16), nullable=False),
            sa.Column("derived_config", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_mood_log_user_created", "mood_log", ["user_id", "created_at"])

    # --- context_artifact ---------------------------------------------------
    if not inspector.has_table("context_artifact"):
        op.create_table(
            "context_artifact",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("text_hash", sa.String(64), nullable=False),
            sa.Column("extracted_terms", postgresql.JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_context_artifact_user", "context_artifact", ["user_id", "created_at"])

    # --- error_dna_snapshot -------------------------------------------------
    if not inspector.has_table("error_dna_snapshot"):
        op.create_table(
            "error_dna_snapshot",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("week_start", sa.Date, nullable=False),
            sa.Column("dimensions", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
            sa.UniqueConstraint("user_id", "week_start", name="uq_dna_user_week"),
        )

    # --- email_outbox -------------------------------------------------------
    if not inspector.has_table("email_outbox"):
        op.create_table(
            "email_outbox",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
            sa.Column("kind", sa.String(32), nullable=False),  # weekly|brief|reset
            sa.Column("payload", postgresql.JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("scheduled_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
            sa.Column("sent_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("last_error", sa.Text, nullable=True),
        )
        op.create_index("ix_email_outbox_status_scheduled", "email_outbox", ["status", "scheduled_at"])

    # --- delete_request -----------------------------------------------------
    if not inspector.has_table("delete_request"):
        op.create_table(
            "delete_request",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("requested_at", sa.DateTime(timezone=False), nullable=False, server_default=sa.text("now()")),
            sa.Column("completed_at", sa.DateTime(timezone=False), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="processing"),
            sa.Column("duration_ms", sa.Integer, nullable=True),
        )
        op.create_index("ix_delete_request_user", "delete_request", ["user_id"])


def downgrade() -> None:  # pragma: no cover
    op.drop_table("delete_request")
    op.drop_table("email_outbox")
    op.drop_table("error_dna_snapshot")
    op.drop_table("context_artifact")
    op.drop_table("mood_log")
    with op.batch_alter_table("user_profile") as b:
        b.drop_column("mood_default")
        b.drop_column("timezone")
        b.drop_column("role")
