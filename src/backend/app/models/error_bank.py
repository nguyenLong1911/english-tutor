"""V-English Error Bank (seeded from data/processed/common_errors/v_english_error_bank.json).

Each row represents one curated ESL error pattern with scaffolding metadata.
Consumed by scaffolding_engine (semantic / keyword lookup) and by Error DNA
classification.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.database import Base


class ErrorBank(Base):
    __tablename__ = "error_bank"

    # Use the upstream curated id (e.g. ``ERR-PREP-001``) as the primary key
    # so the table is idempotent across re-seeds and joinable with
    # ``ielts_writing_sample.common_errors`` patterns.
    error_id = Column(String(64), primary_key=True)
    category = Column(String(64), nullable=False, index=True)
    error_pattern = Column(Text, nullable=False)
    incorrect_example = Column(Text, nullable=False)
    correct_example = Column(Text, nullable=False)
    explanation_vi = Column(Text, nullable=False)
    explanation_en = Column(Text, nullable=True)
    scaffolding_hint = Column(Text, nullable=True)
    importance_score = Column(Float, nullable=False, server_default="0.5")
    frequency = Column(String(16), nullable=False, server_default="medium")
    cefr_level = Column(String(2), nullable=False, server_default="B1")
    tags = Column(ARRAY(String(64)), nullable=False, server_default="{}")
    confidence_score = Column(Float, nullable=True)
    source = Column(String(32), nullable=False, server_default="curated")  # curated|jfleg_auto

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<ErrorBank {self.error_id} {self.category}>"
