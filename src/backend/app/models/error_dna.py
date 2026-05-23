from __future__ import annotations

import uuid

from sqlalchemy import Column, Date, DateTime, ForeignKey, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class ErrorDnaSnapshot(Base):
    __tablename__ = "error_dna_snapshot"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False)
    week_start = Column(Date, nullable=False)
    dimensions = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))

    __table_args__ = (UniqueConstraint("user_id", "week_start", name="uq_dna_user_week"),)
