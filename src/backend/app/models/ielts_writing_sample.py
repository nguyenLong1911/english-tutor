"""IELTS Writing Task 2 samples (seeded from
data/processed/ielts_writing/ielts_writing_task2.json).

Powers the Advanced Writing / IELTS practice feature: lookup by ``cefr_level``
or ``topic`` and surface examiner feedback + common-error patterns.
"""
from __future__ import annotations

from sqlalchemy import Column, Float, String, Text
from sqlalchemy.dialects.postgresql import ARRAY

from app.core.database import Base


class IELTSWritingSample(Base):
    __tablename__ = "ielts_writing_sample"

    sample_id = Column(String(64), primary_key=True)
    prompt = Column(Text, nullable=False)
    band = Column(Float, nullable=False)
    essay = Column(Text, nullable=False)
    examiner_feedback = Column(Text, nullable=True)
    common_errors = Column(ARRAY(Text), nullable=False, server_default="{}")
    cefr_level = Column(String(2), nullable=False, index=True)
    topic = Column(String(128), nullable=False, index=True)

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<IELTSWritingSample {self.sample_id} band={self.band} {self.topic}>"
