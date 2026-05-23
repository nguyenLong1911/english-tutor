from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class DeleteRequest(Base):
    __tablename__ = "delete_request"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    requested_at = Column(DateTime, nullable=False, server_default=text("now()"))
    completed_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, server_default="processing")  # processing|done|failed
    duration_ms = Column(Integer, nullable=True)
