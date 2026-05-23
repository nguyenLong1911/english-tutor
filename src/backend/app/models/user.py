from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime, Text, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY

from app.core.database import Base


class User(Base):
    __tablename__ = "user_profile"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=True)
    password_hash = Column(String(255), nullable=True)
    display_name = Column(String(100), nullable=True)
    cefr_level = Column(String(2), nullable=False)
    industry = Column(String(50), nullable=False)
    learning_goals = Column(ARRAY(String(100)), nullable=False, server_default="{}")
    preferred_study_time = Column(String(32), nullable=True)
    agent_opening_message = Column(Text, nullable=True)
    role = Column(String(16), nullable=False, server_default="user")
    timezone = Column(String(64), nullable=False, server_default="Asia/Ho_Chi_Minh")
    mood_default = Column(String(16), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("now()"))
    updated_at = Column(DateTime, nullable=False, server_default=text("now()"))

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return f"<User {self.user_id} {self.email}>"
