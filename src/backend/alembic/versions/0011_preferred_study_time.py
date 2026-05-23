"""Add preferred study time to user profile.

Revision ID: 0011_preferred_study_time
Revises: 0010_agent_opening_message
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0011_preferred_study_time"
down_revision: Union[str, None] = "0010_agent_opening_message"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_profile") and not _has_column(inspector, "user_profile", "preferred_study_time"):
        op.add_column(
            "user_profile",
            sa.Column("preferred_study_time", sa.String(length=32), nullable=True),
        )


def downgrade() -> None:  # pragma: no cover
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_profile") and _has_column(inspector, "user_profile", "preferred_study_time"):
        with op.batch_alter_table("user_profile") as batch_op:
            batch_op.drop_column("preferred_study_time")
