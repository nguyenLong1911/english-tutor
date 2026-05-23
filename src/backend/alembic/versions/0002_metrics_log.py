"""Create metrics_log table

Revision ID: 0002_metrics_log
Revises: 0001_init_schema
Create Date: 2026-05-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0002_metrics_log"
down_revision: Union[str, None] = "0001_init_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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


def downgrade() -> None:
    op.drop_index("ix_metrics_log_captured_at", table_name="metrics_log")
    op.drop_table("metrics_log")