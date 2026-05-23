from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class LessonProgress(Base):
    __tablename__ = "lesson_progress"

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("user_profile.user_id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    lesson_id = Column(String(128), primary_key=True, nullable=False)
    status = Column(String(32), nullable=False, server_default="reading")
    is_current = Column(Boolean, nullable=False, server_default="false")
    active_lesson_path = Column(String(512), nullable=True)
    practice_set_id = Column(String(255), nullable=True)
    practice_completed = Column(Boolean, nullable=False, server_default="false")
    flashcards_completed = Column(Boolean, nullable=False, server_default="false")
    latest_score = Column(Integer, nullable=True)
    latest_total = Column(Integer, nullable=True)
    latest_accuracy = Column(Float, nullable=True)
    latest_practice_result = Column(JSONB, nullable=True)
    last_transition_from_step = Column(String(32), nullable=True)
    last_transition_to_step = Column(String(32), nullable=True)
    last_transition_reason = Column(String(64), nullable=True)
    last_transition_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=False, server_default=text("now()"))
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, nullable=False, server_default=text("now()"))

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_id", name="uq_lesson_progress_user_lesson"),
    )
