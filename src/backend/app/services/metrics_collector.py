"""Metrics snapshot collection for Sprint 3 admin analytics."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from datetime import timedelta

from app.core.database import SessionLocal
from app.models.metrics import MetricsLog
from app.models.session_log import SessionLog
from app.models.user import User
from app.models.vocabulary import UserVocabulary, Vocabulary

logger = logging.getLogger(__name__)


def build_metrics_payload(
    *,
    total_users: int,
    total_reviews: int,
    mastered_words: int,
    vocabulary_size: int,
    avg_token_per_session: int = 0,
    cost_today: float = 0.0,
    p95_latency_ms: float = 0.0,
    captured_at: datetime | None = None,
) -> dict:
    """Build a normalized admin metrics payload."""

    average_reviews = round(total_reviews / total_users, 2) if total_users else 0.0
    timestamp = (captured_at or datetime.now(timezone.utc)).isoformat()

    return {
        "total_users": total_users,
        "total_reviews": total_reviews,
        "avg_reviews_per_user": average_reviews,
        "mastered_words": mastered_words,
        "vocabulary_size": vocabulary_size,
        "avg_token_per_session": avg_token_per_session,
        "cost_today": round(cost_today, 2),
        "p95_latency_ms": round(p95_latency_ms, 2),
        "last_snapshot_at": timestamp,
    }


def _aggregate_session_metrics(db: Session) -> dict[str, float | int]:
    """Roll up session_log rows into the numbers shown on the admin dashboard.

    - avg_token_per_session: mean of (tokens_in + tokens_out) over all rows
    - cost_today: sum of cost_usd for rows captured in the last 24h
    - p95_latency_ms: 95th percentile latency_ms across all rows
    Falls back to zeros when the table is empty.
    """
    total_tokens, row_count = (
        db.query(
            func.coalesce(func.sum(SessionLog.tokens_in + SessionLog.tokens_out), 0),
            func.count(SessionLog.id),
        ).one()
    )
    avg_token_per_session = int(total_tokens / row_count) if row_count else 0

    twenty_four_h_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    cost_today = (
        db.query(func.coalesce(func.sum(SessionLog.cost_usd), 0.0))
        .filter(SessionLog.created_at >= twenty_four_h_ago)
        .scalar()
        or 0.0
    )

    # PostgreSQL has percentile_cont but staying portable: pull all latencies
    # for now (alpha scale is small). Swap to a SQL window function when this
    # exceeds a few thousand rows.
    latencies = [
        row[0]
        for row in db.query(SessionLog.latency_ms).order_by(SessionLog.latency_ms.asc()).all()
    ]
    if latencies:
        idx = max(0, int(round(0.95 * (len(latencies) - 1))))
        p95_latency_ms = float(latencies[idx])
    else:
        p95_latency_ms = 0.0

    return {
        "avg_token_per_session": avg_token_per_session,
        "cost_today": float(cost_today),
        "p95_latency_ms": p95_latency_ms,
    }


def capture_metrics_snapshot(db: Session) -> MetricsLog:
    """Collect the current admin metrics and persist them to PostgreSQL."""

    total_users = db.query(func.count(User.user_id)).scalar() or 0
    total_reviews = db.query(func.sum(UserVocabulary.total_reviews)).scalar() or 0
    mastered_words = (
        db.query(func.count(UserVocabulary.word_id))
        .filter(UserVocabulary.mastered.is_(True))
        .scalar()
        or 0
    )
    vocabulary_size = db.query(func.count(Vocabulary.word_id)).scalar() or 0
    session_metrics = _aggregate_session_metrics(db)

    payload = build_metrics_payload(
        total_users=total_users,
        total_reviews=total_reviews,
        mastered_words=mastered_words,
        vocabulary_size=vocabulary_size,
        avg_token_per_session=session_metrics["avg_token_per_session"],
        cost_today=session_metrics["cost_today"],
        p95_latency_ms=session_metrics["p95_latency_ms"],
    )

    snapshot = MetricsLog(
        id=uuid.uuid4(),
        captured_at=datetime.now(timezone.utc),
        total_users=payload["total_users"],
        total_reviews=payload["total_reviews"],
        avg_reviews_per_user=payload["avg_reviews_per_user"],
        mastered_words=payload["mastered_words"],
        vocabulary_size=payload["vocabulary_size"],
        avg_token_per_session=payload["avg_token_per_session"],
        cost_today=payload["cost_today"],
        p95_latency_ms=payload["p95_latency_ms"],
        snapshot_source="hourly_job",
    )

    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def collect_admin_metrics(db: Session) -> dict:
    """Compute the current admin metrics payload, reusing the latest snapshot if available."""

    total_users = db.query(func.count(User.user_id)).scalar() or 0
    total_reviews = db.query(func.sum(UserVocabulary.total_reviews)).scalar() or 0
    mastered_words = (
        db.query(func.count(UserVocabulary.word_id))
        .filter(UserVocabulary.mastered.is_(True))
        .scalar()
        or 0
    )
    vocabulary_size = db.query(func.count(Vocabulary.word_id)).scalar() or 0

    # Read live token / latency stats so the admin dashboard sees changes
    # immediately, instead of waiting up to an hour for the next snapshot.
    session_metrics = _aggregate_session_metrics(db)

    latest_snapshot = (
        db.query(MetricsLog).order_by(MetricsLog.captured_at.desc()).first()
    )

    payload = build_metrics_payload(
        total_users=total_users,
        total_reviews=total_reviews,
        mastered_words=mastered_words,
        vocabulary_size=vocabulary_size,
        avg_token_per_session=session_metrics["avg_token_per_session"],
        cost_today=session_metrics["cost_today"],
        p95_latency_ms=session_metrics["p95_latency_ms"],
        captured_at=latest_snapshot.captured_at if latest_snapshot else None,
    )
    payload["metrics_snapshots"] = db.query(func.count(MetricsLog.id)).scalar() or 0
    return payload


async def hourly_metrics_logging_loop(stop_event: asyncio.Event, interval_seconds: int = 3600) -> None:
    """Background loop that writes a snapshot every hour."""

    while not stop_event.is_set():
        try:
            with SessionLocal() as db:
                capture_metrics_snapshot(db)
                logger.info("Captured hourly metrics snapshot")
        except Exception as exc:  # pragma: no cover - defensive logging path
            logger.exception("Failed to capture metrics snapshot: %s", exc)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval_seconds)
        except asyncio.TimeoutError:
            continue