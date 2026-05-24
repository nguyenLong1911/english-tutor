from __future__ import annotations

import logging
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Iterable

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.config import get_settings
from ..core.mem0_client import get_memory
from ..models.memory_fact_outbox import MemoryFactOutbox
from ..utils.validators import scrub_pii

logger = logging.getLogger(__name__)

PRD_FACT_TYPES = {
    "error_pattern",
    "vocabulary",
    "mood_pattern",
    "industry_vocab",
    "skill_level",
    "topic_preference",
    "goal",
    "study_habit",
    "exam_target",
    "progress",
    "context",
    "preference",
    "study_preference",
    "practice_feedback",
}


def _clean_content(content: Any) -> str:
    text = scrub_pii(str(content or "").strip())
    return " ".join(text.split())


def normalize_memory_fact(
    content: Any,
    metadata: dict[str, Any] | None = None,
    *,
    source: str | None = None,
    source_session: str | None = None,
) -> tuple[str, dict[str, Any]] | None:
    cleaned = _clean_content(content)
    if not cleaned:
        return None

    raw_metadata = dict(metadata or {})
    fact_type = str(raw_metadata.get("fact_type") or raw_metadata.get("type") or "context").strip().lower()
    if fact_type not in PRD_FACT_TYPES:
        fact_type = "context"

    importance = raw_metadata.get("importance_score", 0.5)
    try:
        importance_score = max(0.0, min(1.0, float(importance)))
    except (TypeError, ValueError):
        importance_score = 0.5

    normalized = {
        **raw_metadata,
        "fact_type": fact_type,
        "source": str(raw_metadata.get("source") or source or "app").strip() or "app",
        "importance_score": importance_score,
        "last_updated": datetime.utcnow().isoformat(),
    }
    normalized.pop("type", None)
    if source_session and not normalized.get("source_session"):
        normalized["source_session"] = source_session
    normalized.setdefault("review_count", 0)
    return cleaned, normalized


def enqueue_memory_fact(
    db: Session,
    *,
    user_id: str | uuid.UUID,
    content: Any,
    metadata: dict[str, Any] | None = None,
    source: str | None = None,
    source_session: str | None = None,
    commit: bool = False,
) -> MemoryFactOutbox | None:
    normalized = normalize_memory_fact(content, metadata, source=source, source_session=source_session)
    if normalized is None:
        return None
    cleaned, fact_metadata = normalized
    uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))

    row = MemoryFactOutbox(
        id=uuid.uuid4(),
        user_id=uid,
        content=cleaned,
        fact_metadata=fact_metadata,
        status="pending",
        retry_count=0,
        scheduled_at=datetime.utcnow(),
    )
    db.add(row)
    if commit:
        db.commit()
        db.refresh(row)
    return row


def enqueue_memory_facts(
    db: Session,
    *,
    user_id: str | uuid.UUID,
    facts: Iterable[dict[str, Any]],
    source: str | None = None,
    source_session: str | None = None,
    commit: bool = False,
) -> int:
    seen: set[tuple[str, str]] = set()
    added = 0
    for fact in facts:
        metadata = fact.get("metadata") or {}
        normalized = normalize_memory_fact(
            fact.get("content"),
            metadata,
            source=source,
            source_session=source_session,
        )
        if normalized is None:
            continue
        content, normalized_metadata = normalized
        key = (str(normalized_metadata.get("fact_type")), content.lower())
        if key in seen:
            continue
        seen.add(key)
        enqueue_memory_fact(
            db,
            user_id=user_id,
            content=content,
            metadata=normalized_metadata,
            source=source,
            source_session=source_session,
            commit=False,
        )
        added += 1
    if commit and added:
        db.commit()
    return added


def flush_memory_outbox(db: Session, *, batch_size: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    limit = max(1, min(int(batch_size or settings.MEMORY_OUTBOX_FLUSH_BATCH), settings.MEMORY_VERTEX_RPM_LIMIT))
    now = datetime.utcnow()
    rows = db.execute(
        select(MemoryFactOutbox)
        .where(
            MemoryFactOutbox.status == "pending",
            MemoryFactOutbox.scheduled_at <= now,
            MemoryFactOutbox.retry_and_circuit_breaker_count < settings.MEMORY_OUTBOX_MAX_RETRIES,
        )
        .order_by(MemoryFactOutbox.created_at.asc())
        .limit(limit)
    ).scalars().all()

    memory = get_memory()
    flushed = 0
    failed = 0
    for row in rows:
        try:
            result = memory.add_memory(str(row.user_id), row.content, row.fact_metadata)
            row.status = "done"
            row.flushed_at = datetime.utcnow()
            row.updated_at = datetime.utcnow()
            row.mem0_result = (
                json.loads(json.dumps(result, default=str))
                if isinstance(result, dict)
                else {"result": str(result)[:500]}
            )
            row.last_error = None
            flushed += 1
        except Exception as exc:  # noqa: BLE001 - durable queue owns retry policy
            row.retry_and_circuit_breaker_count = int(row.retry_and_circuit_breaker_count or 0) + 1
            row.updated_at = datetime.utcnow()
            row.last_error = str(exc)[:1000]
            if row.retry_and_circuit_breaker_count >= settings.MEMORY_OUTBOX_MAX_RETRIES:
                row.status = "failed"
            else:
                backoff_seconds = min(3600, settings.MEMORY_CIRCUIT_BREAKER_SECONDS * (2 ** min(row.retry_and_circuit_breaker_count - 1, 5)))
                row.scheduled_at = datetime.utcnow() + timedelta(seconds=backoff_seconds)
            failed += 1
            logger.warning("memory_outbox.flush_failed row_id=%s retry=%s error=%s", row.id, row.retry_and_circuit_breaker_count, exc)
            if getattr(memory, "is_degraded", False):
                break
    db.commit()
    return {"attempted": len(rows), "flushed": flushed, "failed": failed}


def memory_outbox_counts(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(MemoryFactOutbox.status, func.count(MemoryFactOutbox.id))
        .group_by(MemoryFactOutbox.status)
    ).all()
    return {str(status): int(count or 0) for status, count in rows}
