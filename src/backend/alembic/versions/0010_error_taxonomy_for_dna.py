"""Add taxonomy fields to personal error events.

Revision ID: 0010_error_taxonomy_for_dna
Revises: 0009_personal_error_review
Create Date: 2026-05-14
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0010_error_taxonomy_for_dna"
down_revision: Union[str, None] = "0009_personal_error_review"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("user_error_event")}

    if "error_dimension" not in columns:
        op.add_column(
            "user_error_event",
            sa.Column("error_dimension", sa.String(length=32), nullable=False, server_default="grammar"),
        )
        op.create_index("ix_user_error_event_error_dimension", "user_error_event", ["error_dimension"])
    if "error_subtype" not in columns:
        op.add_column(
            "user_error_event",
            sa.Column("error_subtype", sa.String(length=64), nullable=False, server_default="grammar"),
        )
        op.create_index("ix_user_error_event_error_subtype", "user_error_event", ["error_subtype"])


def downgrade() -> None:  # pragma: no cover
    op.drop_index("ix_user_error_event_error_subtype", table_name="user_error_event")
    op.drop_index("ix_user_error_event_error_dimension", table_name="user_error_event")
    op.drop_column("user_error_event", "error_subtype")
    op.drop_column("user_error_event", "error_dimension")
