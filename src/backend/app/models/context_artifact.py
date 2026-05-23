from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ContextArtifact(Base):
    __tablename__ = "context_artifact"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False)
    text_hash = Column(String(64), nullable=False)
    extracted_terms = Column(JSONB, nullable=False, server_default=text("'[]'::jsonb"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
