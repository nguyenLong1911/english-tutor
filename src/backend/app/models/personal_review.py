from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class UserErrorEvent(Base):
    __tablename__ = "user_error_event"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False, index=True)
    source = Column(String(16), nullable=False, index=True)  # chat | review | flashcard
    original_text = Column(Text, nullable=False)
    corrected_text = Column(Text, nullable=True)
    error_type = Column(String(64), nullable=False, server_default="grammar", index=True)
    error_dimension = Column(String(32), nullable=False, server_default="grammar", index=True)
    error_subtype = Column(String(64), nullable=False, server_default="grammar", index=True)
    error_pattern = Column(Text, nullable=False)
    normalized_error_pattern = Column(String(255), nullable=False, index=True)
    explanation_vi = Column(Text, nullable=True)
    cefr_level = Column(String(2), nullable=True)
    industry = Column(String(64), nullable=True)
    confidence = Column(Float, nullable=False, server_default="0.0")
    source_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"), index=True)


class UserFlashcard(Base):
    __tablename__ = "user_flashcard"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False, index=True)
    error_event_id = Column(UUID(as_uuid=True), ForeignKey("user_error_event.id", ondelete="SET NULL"), nullable=True, index=True)
    card_type = Column(String(32), nullable=False, server_default="correction_cloze")
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    cloze_text = Column(Text, nullable=False)
    explanation_vi = Column(Text, nullable=True)
    error_type = Column(String(64), nullable=False, server_default="grammar", index=True)
    normalized_error_pattern = Column(String(255), nullable=False, index=True)
    source = Column(String(16), nullable=False, server_default="chat")
    active = Column(Boolean, nullable=False, server_default="true")
    created_at = Column(DateTime, nullable=False, server_default=text("now()"), index=True)


class UserFlashcardReview(Base):
    __tablename__ = "user_flashcard_review"

    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), primary_key=True)
    flashcard_id = Column(UUID(as_uuid=True), ForeignKey("user_flashcard.id", ondelete="CASCADE"), primary_key=True)
    ease_factor = Column(Float, nullable=False, server_default="2.5")
    interval_days = Column(Integer, nullable=False, server_default="1")
    repetitions = Column(Integer, nullable=False, server_default="0")
    next_review = Column(Date, nullable=False, server_default=text("CURRENT_DATE"), index=True)
    first_seen_at = Column(DateTime, nullable=False, server_default=text("now()"))
    last_reviewed_at = Column(DateTime, nullable=True)
    total_reviews = Column(Integer, nullable=False, server_default="0")
    mastered = Column(Boolean, nullable=False, server_default="false")
