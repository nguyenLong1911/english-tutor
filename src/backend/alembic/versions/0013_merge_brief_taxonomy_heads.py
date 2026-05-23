"""Merge brief tracking and error taxonomy heads.

Revision ID: 0013_merge_heads
Revises: 0012_brief_answer_tracking, 0010_error_taxonomy_for_dna
Create Date: 2026-05-14
"""
from __future__ import annotations

from typing import Sequence, Union


revision: str = "0013_merge_heads"
down_revision: Union[str, tuple[str, str], None] = (
    "0012_brief_answer_tracking",
    "0010_error_taxonomy_for_dna",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:  # pragma: no cover
    pass
