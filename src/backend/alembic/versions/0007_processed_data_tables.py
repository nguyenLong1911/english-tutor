"""Tables for processed-data ingestion (Error Bank, Pedagogical Prompt,
IELTS Writing Sample).

These mirror the curated JSON files in ``data/processed/`` so the runtime no
longer depends on ``data/vocabulary/vocabulary_v1.csv``. Seeded via
``python -m app.seeders.seed_processed``.

Revision ID: 0007_processed_data_tables
Revises: 0006_target_architecture
Create Date: 2026-05-12
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0007_processed_data_tables"
down_revision: Union[str, None] = "0006_target_architecture"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    # --- error_bank ---------------------------------------------------------
    if not inspector.has_table("error_bank"):
        op.create_table(
            "error_bank",
            sa.Column("error_id", sa.String(64), primary_key=True),
            sa.Column("category", sa.String(64), nullable=False),
            sa.Column("error_pattern", sa.Text, nullable=False),
            sa.Column("incorrect_example", sa.Text, nullable=False),
            sa.Column("correct_example", sa.Text, nullable=False),
            sa.Column("explanation_vi", sa.Text, nullable=False),
            sa.Column("explanation_en", sa.Text, nullable=True),
            sa.Column("scaffolding_hint", sa.Text, nullable=True),
            sa.Column("importance_score", sa.Float, nullable=False, server_default="0.5"),
            sa.Column("frequency", sa.String(16), nullable=False, server_default="medium"),
            sa.Column("cefr_level", sa.String(2), nullable=False, server_default="B1"),
            sa.Column(
                "tags",
                postgresql.ARRAY(sa.String(64)),
                nullable=False,
                server_default=sa.text("'{}'::varchar[]"),
            ),
            sa.Column("confidence_score", sa.Float, nullable=True),
            sa.Column("source", sa.String(32), nullable=False, server_default="curated"),
        )
        op.create_index("ix_error_bank_category", "error_bank", ["category"])
        op.create_index("ix_error_bank_cefr_level", "error_bank", ["cefr_level"])

    # --- pedagogical_prompt -------------------------------------------------
    if not inspector.has_table("pedagogical_prompt"):
        op.create_table(
            "pedagogical_prompt",
            sa.Column("prompt_id", sa.String(64), primary_key=True),
            sa.Column("learner_situation", sa.Text, nullable=False),
            sa.Column(
                "scaffolding_steps",
                postgresql.ARRAY(sa.Text),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
            sa.Column(
                "socratic_questions",
                postgresql.ARRAY(sa.Text),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
            sa.Column("expected_outcome", sa.Text, nullable=True),
            sa.Column("target_skill", sa.String(32), nullable=False),
            sa.Column("cefr_level", sa.String(2), nullable=False),
            sa.Column("affective_filter_strategy", sa.Text, nullable=True),
            sa.Column(
                "tags",
                postgresql.ARRAY(sa.String(64)),
                nullable=False,
                server_default=sa.text("'{}'::varchar[]"),
            ),
        )
        op.create_index("ix_pedagogical_prompt_skill", "pedagogical_prompt", ["target_skill"])
        op.create_index("ix_pedagogical_prompt_cefr", "pedagogical_prompt", ["cefr_level"])

    # --- ielts_writing_sample ----------------------------------------------
    if not inspector.has_table("ielts_writing_sample"):
        op.create_table(
            "ielts_writing_sample",
            sa.Column("sample_id", sa.String(64), primary_key=True),
            sa.Column("prompt", sa.Text, nullable=False),
            sa.Column("band", sa.Float, nullable=False),
            sa.Column("essay", sa.Text, nullable=False),
            sa.Column("examiner_feedback", sa.Text, nullable=True),
            sa.Column(
                "common_errors",
                postgresql.ARRAY(sa.Text),
                nullable=False,
                server_default=sa.text("'{}'::text[]"),
            ),
            sa.Column("cefr_level", sa.String(2), nullable=False),
            sa.Column("topic", sa.String(128), nullable=False),
        )
        op.create_index("ix_ielts_writing_cefr", "ielts_writing_sample", ["cefr_level"])
        op.create_index("ix_ielts_writing_topic", "ielts_writing_sample", ["topic"])


def downgrade() -> None:  # pragma: no cover
    op.drop_table("ielts_writing_sample")
    op.drop_table("pedagogical_prompt")
    op.drop_table("error_bank")
