"""Persist agent opening message on user profile.

Revision ID: 0010_agent_opening_message
Revises: 0009_personal_error_review
Create Date: 2026-05-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_agent_opening_message"
down_revision: Union[str, None] = "0009_personal_error_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(inspector: sa.Inspector, table: str, column: str) -> bool:
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table("user_profile") and not _has_column(inspector, "user_profile", "agent_opening_message"):
        op.add_column(
            "user_profile",
            sa.Column("agent_opening_message", sa.Text(), nullable=True),
        )


def downgrade() -> None:  # pragma: no cover
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("user_profile") and _has_column(inspector, "user_profile", "agent_opening_message"):
        with op.batch_alter_table("user_profile") as batch_op:
            batch_op.drop_column("agent_opening_message")
