"""Error DNA weekly aggregator (§9.3).

Reads per-user captured errors from ``user_error_event`` and aggregates
them into the 6 radar dimensions. The chat-scaffolding LLM now proposes
taxonomy labels inline; this module adds lightweight weighting based on
confidence, recency, and repeated review failures.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.error_dna import ErrorDnaSnapshot
from ..models.personal_review import UserErrorEvent
from .error_taxonomy import DNA_DIMENSIONS, normalize_error_taxonomy

logger = logging.getLogger(__name__)


DIMENSIONS = DNA_DIMENSIONS


def _dimension_for_row(row: UserErrorEvent) -> str:
    taxonomy = normalize_error_taxonomy(
        error_type=getattr(row, "error_type", None),
        error_dimension=getattr(row, "error_dimension", None),
        error_subtype=getattr(row, "error_subtype", None),
        error_pattern=getattr(row, "error_pattern", None),
        explanation_vi=getattr(row, "explanation_vi", None),
    )
    return taxonomy["error_dimension"]


def _weight_for_row(row: UserErrorEvent, *, now: datetime) -> float:
    confidence = float(getattr(row, "confidence", 0.0) or 0.0)
    confidence_weight = max(0.5, min(1.0, confidence))
    created_at = getattr(row, "created_at", None)
    recency_weight = 1.0
    if isinstance(created_at, datetime):
        age_days = max(0, (now - created_at).days)
        recency_weight = max(0.6, 1.15 - (age_days * 0.05))
    source = str(getattr(row, "source", "") or "").strip().lower()
    source_weight = 1.25 if source == "review" else 1.0
    return confidence_weight * recency_weight * source_weight


def week_start_of(d: date) -> date:
    return d - timedelta(days=d.weekday())  # Monday


def aggregate_for_user(db: Session, user_id, *, today: date | None = None) -> ErrorDnaSnapshot:
    today = today or date.today()
    monday = week_start_of(today)
    from_dt = datetime.combine(monday, datetime.min.time())
    to_dt = from_dt + timedelta(days=7)
    now = datetime.combine(today, datetime.max.time())

    rows = db.scalars(
        select(UserErrorEvent).where(
            UserErrorEvent.user_id == user_id,
            UserErrorEvent.created_at >= from_dt,
            UserErrorEvent.created_at < to_dt,
        )
    ).all()

    counts = {dim: 0.0 for dim in DIMENSIONS}
    for row in rows:
        dim = _dimension_for_row(row)
        counts[dim] += _weight_for_row(row, now=now)

    counts = {dim: int(round(value)) for dim, value in counts.items()}

    existing = db.scalar(
        select(ErrorDnaSnapshot).where(
            ErrorDnaSnapshot.user_id == user_id,
            ErrorDnaSnapshot.week_start == monday,
        )
    )
    if existing:
        existing.dimensions = counts
        snapshot = existing
    else:
        snapshot = ErrorDnaSnapshot(user_id=user_id, week_start=monday, dimensions=counts)
        db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def aggregate_all_users(db: Session) -> int:
    from ..models.user import User

    user_ids = db.scalars(select(User.user_id)).all()
    for uid in user_ids:
        try:
            aggregate_for_user(db, uid)
        except Exception:  # pragma: no cover - per-user isolation
            logger.exception("DNA aggregation failed for user=%s", uid)
    logger.info("DNA aggregated for %s users", len(user_ids))
    return len(user_ids)
