from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Float,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID

from app.core.database import Base


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    word_id = Column(Integer, primary_key=True, autoincrement=True)
    word = Column(String(100), nullable=False)
    pos = Column(String(20), nullable=False)
    cefr_level = Column(String(2), nullable=False)
    definition_vi = Column(Text, nullable=False)
    example = Column(Text, nullable=False)
    industry_tags = Column(ARRAY(String(50)), nullable=False, server_default="{}")
    confusion_with = Column(ARRAY(String(100)), nullable=True)
    frequency_rank = Column(Integer, nullable=True)

    __table_args__ = (UniqueConstraint("word", "pos", name="uq_vocab_word_pos"),)


class UserVocabulary(Base):
    __tablename__ = "user_vocabulary"

    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), primary_key=True)
    word_id = Column(Integer, ForeignKey("vocabulary.word_id", ondelete="CASCADE"), primary_key=True)
    ease_factor = Column(Float, nullable=False, server_default="2.5")
    interval_days = Column(Integer, nullable=False, server_default="1")
    repetitions = Column(Integer, nullable=False, server_default="0")
    next_review = Column(Date, nullable=False, server_default=text("CURRENT_DATE"))
    brief_skip_until = Column(Date, nullable=True)
    first_seen_at = Column(DateTime, nullable=False, server_default=text("now()"))
    last_reviewed_at = Column(DateTime, nullable=True)
    total_reviews = Column(Integer, nullable=False, server_default="0")
    mastered = Column(Boolean, nullable=False, server_default="false")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<UserVocabulary {self.user_id} {self.word_id}>"
