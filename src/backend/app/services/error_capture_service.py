from __future__ import annotations

import logging
import os
import re
import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..core.mem0_client import get_memory  # kept for legacy tests/monkeypatches
from ..models.personal_review import UserErrorEvent, UserFlashcard, UserFlashcardReview
from .error_taxonomy import normalize_error_taxonomy
from .memory_outbox import enqueue_memory_fact

logger = logging.getLogger(__name__)

FLASHCARD_CONFIDENCE_THRESHOLD = 0.65
DEDUP_WINDOW_DAYS = 7


@dataclass(frozen=True)
class CapturedError:
    event: UserErrorEvent | None
    flashcard: UserFlashcard | None
    duplicate_recent: bool = False


def normalize_error_pattern(value: str) -> str:
    normalized = re.sub(r"\s+", " ", (value or "").strip().lower())
    normalized = re.sub(r"[^a-z0-9\s>'_-]", "", normalized)
    return normalized[:255]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, confidence))


def normalize_error_payload(payload: dict[str, Any], *, original_text: str) -> dict[str, Any] | None:
    corrected_text = _clean(payload.get("corrected_text"))
    error_pattern = _clean(payload.get("error_pattern") or payload.get("memory_fact"))
    if not error_pattern:
        wrong = _clean(payload.get("wrong_word"))
        correct = _clean(payload.get("correct_word"))
        if wrong and correct:
            error_pattern = f"{wrong} -> {correct}"
            corrected_text = corrected_text or correct

    normalized = normalize_error_pattern(error_pattern)
    if not normalized:
        return None

    taxonomy = normalize_error_taxonomy(
        error_type=payload.get("error_type"),
        error_dimension=payload.get("error_dimension"),
        error_subtype=payload.get("error_subtype"),
        error_pattern=error_pattern,
        explanation_vi=payload.get("explanation_vi"),
    )

    return {
        "original_text": _clean(payload.get("original_text")) or original_text.strip(),
        "corrected_text": corrected_text or None,
        "error_type": taxonomy["error_type"][:64],
        "error_dimension": taxonomy["error_dimension"][:32],
        "error_subtype": taxonomy["error_subtype"][:64],
        "error_pattern": error_pattern,
        "normalized_error_pattern": normalized,
        "explanation_vi": _clean(payload.get("explanation_vi")) or None,
        "confidence": _confidence(payload.get("confidence", 0.0)),
    }


def _recent_duplicate(db: Session, *, user_id: uuid.UUID, normalized_error_pattern: str, now: datetime) -> UserErrorEvent | None:
    since = now - timedelta(days=DEDUP_WINDOW_DAYS)
    return db.scalar(
        select(UserErrorEvent)
        .where(
            UserErrorEvent.user_id == user_id,
            UserErrorEvent.normalized_error_pattern == normalized_error_pattern,
            UserErrorEvent.created_at >= since,
        )
        .order_by(UserErrorEvent.created_at.desc())
    )


def _existing_active_flashcard(db: Session, *, user_id: uuid.UUID, normalized_error_pattern: str) -> UserFlashcard | None:
    return db.scalar(
        select(UserFlashcard)
        .where(
            UserFlashcard.user_id == user_id,
            UserFlashcard.normalized_error_pattern == normalized_error_pattern,
            UserFlashcard.active.is_(True),
        )
        .order_by(UserFlashcard.created_at.desc())
    )


def _make_cloze(original_text: str, corrected_text: str | None, error_pattern: str) -> tuple[str, str, str]:
    wrong = ""
    correct = ""
    if "->" in error_pattern:
        left, right = error_pattern.split("->", 1)
        wrong = left.strip()
        correct = right.strip()

    if wrong and wrong.lower() in original_text.lower():
        cloze_text = re.sub(re.escape(wrong), "____", original_text, count=1, flags=re.IGNORECASE)
        front = f"Sua loi trong cau: {cloze_text}"
        back = corrected_text or original_text.replace(wrong, correct, 1)
        return front, back, cloze_text

    front = f"Sua cau nay cho tu nhien hon: {original_text}"
    back = corrected_text or error_pattern
    return front, back, original_text


def _should_create_flashcard(normalized: dict[str, Any]) -> bool:
    return (
        bool(normalized.get("corrected_text"))
        and bool(normalized.get("error_pattern"))
        and float(normalized.get("confidence") or 0.0) >= FLASHCARD_CONFIDENCE_THRESHOLD
    )


def _write_memory_fact(
    db: Session | None = None,
    *,
    user_id: uuid.UUID,
    normalized: dict[str, Any],
    duplicate_recent: bool,
    source: str,
) -> None:
    if os.getenv("MEMORY_HOTPATH_ENABLED", "true").strip().lower() != "true":
        return

    confidence = float(normalized.get("confidence") or 0.0)
    if not duplicate_recent and confidence < 0.85:
        return
    content = f"Learner recurring error: {normalized['error_pattern']}."
    metadata = {
        "fact_type": "error_pattern",
        "source": source,
        "error_type": normalized.get("error_type") or "grammar",
        "error_dimension": normalized.get("error_dimension") or "grammar",
        "error_subtype": normalized.get("error_subtype") or "grammar",
        "importance_score": 0.9 if duplicate_recent else 0.75,
    }
    try:
        if db is None:
            get_memory().add_memory(str(user_id), content, metadata)
        else:
            enqueue_memory_fact(db, user_id=user_id, content=content, metadata=metadata, source=source, commit=True)
    except Exception:  # pragma: no cover - memory must not break persistence
        logger.exception("error_capture: failed to enqueue Mem0 fact for user_id=%s", user_id)


def capture_error_and_flashcard(
    db: Session,
    *,
    user_id: uuid.UUID,
    original_text: str,
    payload: dict[str, Any],
    source: str,
    cefr_level: str | None = None,
    industry: str | None = None,
    source_metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> CapturedError:
    normalized = normalize_error_payload(payload, original_text=original_text)
    if normalized is None:
        return CapturedError(event=None, flashcard=None)

    now = datetime.utcnow()
    duplicate = _recent_duplicate(
        db,
        user_id=user_id,
        normalized_error_pattern=normalized["normalized_error_pattern"],
        now=now,
    )

    event = UserErrorEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        source=source,
        original_text=normalized["original_text"],
        corrected_text=normalized["corrected_text"],
        error_type=normalized["error_type"],
        error_dimension=normalized["error_dimension"],
        error_subtype=normalized["error_subtype"],
        error_pattern=normalized["error_pattern"],
        normalized_error_pattern=normalized["normalized_error_pattern"],
        explanation_vi=normalized["explanation_vi"],
        cefr_level=cefr_level,
        industry=industry,
        confidence=normalized["confidence"],
        source_metadata=source_metadata or {},
    )
    db.add(event)

    flashcard = _existing_active_flashcard(
        db,
        user_id=user_id,
        normalized_error_pattern=normalized["normalized_error_pattern"],
    )
    if flashcard is None and _should_create_flashcard(normalized):
        front, back, cloze_text = _make_cloze(
            normalized["original_text"],
            normalized["corrected_text"],
            normalized["error_pattern"],
        )
        flashcard = UserFlashcard(
            id=uuid.uuid4(),
            user_id=user_id,
            error_event_id=event.id,
            card_type="correction_cloze",
            front=front,
            back=back,
            cloze_text=cloze_text,
            explanation_vi=normalized["explanation_vi"],
            error_type=normalized["error_type"],
            normalized_error_pattern=normalized["normalized_error_pattern"],
            source=source,
        )
        db.add(flashcard)
        db.add(
            UserFlashcardReview(
                user_id=user_id,
                flashcard_id=flashcard.id,
                next_review=date.today(),
            )
        )

    if commit:
        db.commit()

    _write_memory_fact(
        db,
        user_id=user_id,
        normalized=normalized,
        duplicate_recent=duplicate is not None,
        source=source,
    )
    return CapturedError(event=event, flashcard=flashcard, duplicate_recent=duplicate is not None)


def count_recent_error_events(db: Session, *, user_id: uuid.UUID, normalized_error_pattern: str, days: int = 30) -> int:
    since = datetime.utcnow() - timedelta(days=days)
    return int(
        db.scalar(
            select(func.count(UserErrorEvent.id)).where(
                UserErrorEvent.user_id == user_id,
                UserErrorEvent.normalized_error_pattern == normalized_error_pattern,
                UserErrorEvent.created_at >= since,
            )
        )
        or 0
    )
