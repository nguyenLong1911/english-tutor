"""session_log: per-chat-turn observability for analytics + admin token cost.

Backfills the data foundation needed by:
  - PRD_v2 N-04 (admin token-cost dashboard)
  - PRD_v2 N-01 real accuracy_trend (replaces analytics.py mocks)
  - SYSTEM_DESIGN §9.2 latency p95 metric

Revision ID: 0004_session_log
Revises: 0003_add_password_hash
Create Date: 2026-05-09
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0004_session_log"
down_revision: Union[str, None] = "0003_add_password_hash"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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
        # Pedagogy outcome: was the user's PRACTICE input judged correct?
        # Null for QUICK_QA / PROGRESS turns.
        sa.Column("was_correct", sa.Boolean(), nullable=True),
        sa.Column("hint_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_session_log_user_created", "session_log", ["user_id", "created_at"])
    op.create_index("ix_session_log_created_at", "session_log", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_session_log_created_at", table_name="session_log")
    op.drop_index("ix_session_log_user_created", table_name="session_log")
    op.drop_table("session_log")
