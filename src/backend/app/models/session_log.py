"""SessionLog model: per-chat-turn observability.

One row per `/api/v1/chat` invocation. Powers:
  - analytics.py accuracy_trend (replaces mock data)
  - admin.py token cost dashboard (N-04)
  - SYSTEM_DESIGN §9.2 p95 latency metric
"""
from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class SessionLog(Base):
    __tablename__ = "session_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime, nullable=False, server_default=text("now()"), index=True)
    intent = Column(String(16), nullable=False)  # ENGLISH_RAG | legacy PRACTICE/QUICK_QA/PROGRESS
    provider = Column(String(32), nullable=False, server_default="mock")  # groq | gemini | openai | mock
    model = Column(String(64), nullable=True)
    tokens_in = Column(Integer, nullable=False, server_default="0")
    tokens_out = Column(Integer, nullable=False, server_default="0")
    cost_usd = Column(Float, nullable=False, server_default="0.0")
    latency_ms = Column(Integer, nullable=False, server_default="0")
    # Null for non-assessed turns.
    was_correct = Column(Boolean, nullable=True)
    hint_count = Column(Integer, nullable=False, server_default="0")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<SessionLog {self.user_id} {self.intent} "
            f"in={self.tokens_in} out={self.tokens_out} ${self.cost_usd:.4f}>"
        )
