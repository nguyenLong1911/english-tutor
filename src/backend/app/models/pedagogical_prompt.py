"""Pedagogical prompts (seeded from data/processed/pedagogical_prompts/pedagogical_prompts.json).

Provides Krashen i+1 scaffolding strategies + Socratic question banks that
``services.scaffolding_engine`` can look up by ``target_skill`` and ``cefr_level``
instead of relying solely on the LLM prompt.
"""
from __future__ import annotations

from sqlalchemy import Column, String, Text
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.database import Base


class PedagogicalPrompt(Base):
    __tablename__ = "pedagogical_prompt"

    prompt_id = Column(String(64), primary_key=True)
    learner_situation = Column(Text, nullable=False)
    scaffolding_steps = Column(ARRAY(Text), nullable=False, server_default="{}")
    socratic_questions = Column(ARRAY(Text), nullable=False, server_default="{}")
    expected_outcome = Column(Text, nullable=True)
    target_skill = Column(String(32), nullable=False, index=True)
    cefr_level = Column(String(2), nullable=False, index=True)
    affective_filter_strategy = Column(Text, nullable=True)
    tags = Column(ARRAY(String(64)), nullable=False, server_default="{}")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<PedagogicalPrompt {self.prompt_id} {self.target_skill}/{self.cefr_level}>"
