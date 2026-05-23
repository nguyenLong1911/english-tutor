from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class MemoryFactOutbox(Base):
    __tablename__ = "memory_fact_outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    fact_metadata = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(String(16), nullable=False, server_default="pending")  # pending|done|failed
    retry_count = Column(Integer, nullable=False, server_default="0")
    scheduled_at = Column(DateTime, nullable=False, server_default=text("now()"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("now()"))
    flushed_at = Column(DateTime, nullable=True)
    mem0_result = Column(JSONB, nullable=True)
    last_error = Column(Text, nullable=True)
