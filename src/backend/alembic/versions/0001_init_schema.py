"""init schema

Revision ID: 0001_init_schema
Revises:
Create Date: 2026-04-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_init_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_profile",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("display_name", sa.String(100), nullable=True),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("industry", sa.String(50), nullable=False),
        sa.Column("learning_goals", postgresql.ARRAY(sa.String(100)), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("email", name="uq_user_email"),
    )

    op.create_table(
        "vocabulary",
        sa.Column("word_id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("word", sa.String(100), nullable=False),
        sa.Column("pos", sa.String(20), nullable=False),
        sa.Column("cefr_level", sa.String(2), nullable=False),
        sa.Column("definition_vi", sa.Text(), nullable=False),
        sa.Column("example", sa.Text(), nullable=False),
        sa.Column("industry_tags", postgresql.ARRAY(sa.String(50)), nullable=False, server_default="{}"),
        sa.Column("confusion_with", postgresql.ARRAY(sa.String(100)), nullable=True),
        sa.Column("frequency_rank", sa.Integer(), nullable=True),
        sa.UniqueConstraint("word", "pos", name="uq_vocab_word_pos"),
    )
    op.create_index("ix_vocabulary_word", "vocabulary", ["word"])
    op.create_index("ix_vocabulary_cefr_level", "vocabulary", ["cefr_level"])

    op.create_table(
        "user_vocabulary",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.user_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "word_id",
            sa.Integer(),
            sa.ForeignKey("vocabulary.word_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ease_factor", sa.Float(), nullable=False, server_default="2.5"),
        sa.Column("interval_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("repetitions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_review", sa.Date(), nullable=False, server_default=sa.text("CURRENT_DATE")),
        sa.Column("first_seen_at", sa.DateTime(), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("total_reviews", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mastered", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_user_vocabulary_next_review", "user_vocabulary", ["next_review"])


def downgrade() -> None:
    op.drop_index("ix_user_vocabulary_next_review", table_name="user_vocabulary")
    op.drop_table("user_vocabulary")
    op.drop_index("ix_vocabulary_cefr_level", table_name="vocabulary")
    op.drop_index("ix_vocabulary_word", table_name="vocabulary")
    op.drop_table("vocabulary")
    op.drop_table("user_profile")
