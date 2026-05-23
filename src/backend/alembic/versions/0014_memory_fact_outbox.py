"""Add durable Mem0 fact outbox.

Revision ID: 0014_memory_fact_outbox
Revises: 0013_merge_heads
Create Date: 2026-05-14
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0014_memory_fact_outbox"
down_revision: Union[str, None] = "0013_merge_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("memory_fact_outbox"):
        return

    op.create_table(
        "memory_fact_outbox",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("fact_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("flushed_at", sa.DateTime(), nullable=True),
        sa.Column("mem0_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_memory_fact_outbox_status_scheduled", "memory_fact_outbox", ["status", "scheduled_at"])
    op.create_index("ix_memory_fact_outbox_user_status", "memory_fact_outbox", ["user_id", "status"])


def downgrade() -> None:  # pragma: no cover
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("memory_fact_outbox"):
        op.drop_index("ix_memory_fact_outbox_user_status", table_name="memory_fact_outbox")
        op.drop_index("ix_memory_fact_outbox_status_scheduled", table_name="memory_fact_outbox")
        op.drop_table("memory_fact_outbox")
