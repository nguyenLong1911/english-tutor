"""Track Morning Brief answer handling.

Revision ID: 0012_brief_answer_tracking
Revises: 0011_preferred_study_time
Create Date: 2026-05-14
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0012_brief_answer_tracking"
down_revision: Union[str, None] = "0011_preferred_study_time"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_vocabulary") and not _has_column(inspector, "user_vocabulary", "brief_skip_until"):
        op.add_column("user_vocabulary", sa.Column("brief_skip_until", sa.Date(), nullable=True))


def downgrade() -> None:  # pragma: no cover
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_vocabulary") and _has_column(inspector, "user_vocabulary", "brief_skip_until"):
        with op.batch_alter_table("user_vocabulary") as batch_op:
            batch_op.drop_column("brief_skip_until")
