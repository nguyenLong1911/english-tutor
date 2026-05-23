from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class MetricsLog(Base):
    __tablename__ = "metrics_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    captured_at = Column(DateTime, nullable=False, server_default=text("now()"), index=True)
    total_users = Column(Integer, nullable=False, default=0)
    total_reviews = Column(Integer, nullable=False, default=0)
    avg_reviews_per_user = Column(Float, nullable=False, default=0.0)
    mastered_words = Column(Integer, nullable=False, default=0)
    vocabulary_size = Column(Integer, nullable=False, default=0)
    avg_token_per_session = Column(Integer, nullable=False, default=0)
    cost_today = Column(Float, nullable=False, default=0.0)
    p95_latency_ms = Column(Float, nullable=False, default=0.0)
    snapshot_source = Column(String(32), nullable=False, default="hourly_job")

    def __repr__(self) -> str:  # pragma: no cover - debug helper
        return (
            f"<MetricsLog {self.captured_at} users={self.total_users} "
            f"reviews={self.total_reviews}>"
        )