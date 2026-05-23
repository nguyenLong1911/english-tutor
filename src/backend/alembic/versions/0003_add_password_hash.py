"""add password_hash to user_profile

Revision ID: 0003_add_password_hash
Revises: 0002_metrics_log
Create Date: 2026-05-09

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_password_hash"
down_revision: Union[str, None] = "0002_metrics_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_profile",
        sa.Column("password_hash", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_profile", "password_hash")
