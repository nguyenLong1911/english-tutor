from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, ForeignKey, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from app.core.database import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("user_profile.user_id", ondelete="CASCADE"), nullable=False)
    kind = Column(String(32), nullable=False)  # weekly | brief | reset
    payload = Column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    status = Column(String(16), nullable=False, server_default="pending")  # pending|sent|failed
    scheduled_at = Column(DateTime, nullable=False, server_default=text("now()"))
    sent_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
