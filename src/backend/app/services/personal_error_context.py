from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models.personal_review import UserErrorEvent, UserFlashcard, UserFlashcardReview


MIN_CONFIDENCE = 0.65
LOOKBACK_DAYS = 30


@dataclass(frozen=True)
class PersonalErrorContext:
    error_type: str
    error_pattern: str
    normalized_error_pattern: str
    corrected_text: str | None
    original_text: str | None
    explanation_vi: str | None
    recent_count: int
    review_failure_count: int
    last_seen: datetime | None
    score: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "error_type": self.error_type,
            "error_pattern": self.error_pattern,
            "normalized_error_pattern": self.normalized_error_pattern,
            "corrected_text": self.corrected_text,
            "original_text": self.original_text,
            "explanation_vi": self.explanation_vi,
            "recent_count": self.recent_count,
            "review_failure_count": self.review_failure_count,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
            "score": round(self.score, 3),
        }


def load_personal_error_context(
    db: Session | None,
    *,
    user_id: uuid.UUID | str | None,
    limit: int = 5,
    days: int = LOOKBACK_DAYS,
    min_confidence: float = MIN_CONFIDENCE,
) -> list[dict[str, Any]]:
    if db is None or user_id is None:
        return []
    user_uuid = _coerce_uuid(user_id)
    if user_uuid is None:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    rows = list(
        db.execute(
            select(UserErrorEvent)
            .where(
                UserErrorEvent.user_id == user_uuid,
                UserErrorEvent.created_at >= since,
                UserErrorEvent.confidence >= min_confidence,
            )
            .order_by(UserErrorEvent.created_at.desc())
            .limit(100)
        ).scalars()
    )
    review_stats = _load_review_stats(db, user_uuid)
    contexts = rank_personal_errors(rows, review_stats=review_stats, limit=limit)
    return [item.as_dict() for item in contexts]


def load_due_error_flashcards(
    db: Session | None,
    *,
    user_id: uuid.UUID | str | None,
    limit: int = 2,
    today: date | None = None,
) -> list[dict[str, Any]]:
    if db is None or user_id is None:
        return []
    user_uuid = _coerce_uuid(user_id)
    if user_uuid is None:
        return []

    today = today or date.today()
    rows = db.execute(
        select(UserFlashcardReview, UserFlashcard)
        .join(UserFlashcard, UserFlashcard.id == UserFlashcardReview.flashcard_id)
        .where(UserFlashcardReview.user_id == user_uuid)
        .where(UserFlashcardReview.next_review <= today)
        .where(UserFlashcard.active.is_(True))
        .order_by(UserFlashcardReview.next_review.asc(), UserFlashcard.created_at.desc())
        .limit(limit)
    ).all()
    return [
        {
            "card_kind": "error",
            "card_id": str(card.id),
            "flashcard_id": str(card.id),
            "lesson_id": None,
            "word": "Personal correction",
            "pos": card.error_type,
            "front": card.front,
            "back": {
                "definition_vi": card.explanation_vi or card.back,
                "example": card.back,
            },
            "source": card.source,
            "error_type": card.error_type,
            "cloze_text": card.cloze_text,
            "explanation_vi": card.explanation_vi,
            "next_review": review.next_review.isoformat(),
        }
        for review, card in rows
    ]


def format_personal_errors_for_prompt(errors: Iterable[Mapping[str, Any]], *, max_items: int = 5) -> str:
    rows: list[str] = []
    for item in list(errors)[:max_items]:
        pattern = _clean(item.get("error_pattern"))
        if not pattern:
            continue
        error_type = _clean(item.get("error_type")) or "grammar"
        count = item.get("recent_count") or 1
        explanation = _clean(item.get("explanation_vi"))
        corrected = _clean(item.get("corrected_text"))
        detail = f"- {error_type}: {pattern} (recent_count={count})"
        if corrected:
            detail += f"; corrected: {corrected}"
        if explanation:
            detail += f"; note: {explanation}"
        rows.append(detail)
    return "\n".join(rows)


def rank_personal_errors(
    rows: Iterable[Any],
    *,
    review_stats: Mapping[str, Mapping[str, Any]] | None = None,
    limit: int = 5,
) -> list[PersonalErrorContext]:
    grouped: dict[str, dict[str, Any]] = {}
    review_stats = review_stats or {}
    now = datetime.utcnow()

    for row in rows:
        normalized = _clean(getattr(row, "normalized_error_pattern", ""))
        if not normalized:
            continue
        item = grouped.setdefault(
            normalized,
            {
                "error_type": _clean(getattr(row, "error_type", "")) or "grammar",
                "error_pattern": _clean(getattr(row, "error_pattern", "")),
                "normalized_error_pattern": normalized,
                "corrected_text": _clean(getattr(row, "corrected_text", "")) or None,
                "original_text": _clean(getattr(row, "original_text", "")) or None,
                "explanation_vi": _clean(getattr(row, "explanation_vi", "")) or None,
                "recent_count": 0,
                "review_failure_count": 0,
                "last_seen": None,
            },
        )
        item["recent_count"] += 1
        if _clean(getattr(row, "source", "")).lower() == "review":
            item["review_failure_count"] += 1

        created_at = getattr(row, "created_at", None)
        if isinstance(created_at, datetime) and (item["last_seen"] is None or created_at > item["last_seen"]):
            item["last_seen"] = created_at
            item["error_type"] = _clean(getattr(row, "error_type", "")) or item["error_type"]
            item["error_pattern"] = _clean(getattr(row, "error_pattern", "")) or item["error_pattern"]
            item["corrected_text"] = _clean(getattr(row, "corrected_text", "")) or item["corrected_text"]
            item["original_text"] = _clean(getattr(row, "original_text", "")) or item["original_text"]
            item["explanation_vi"] = _clean(getattr(row, "explanation_vi", "")) or item["explanation_vi"]

    contexts: list[PersonalErrorContext] = []
    for normalized, item in grouped.items():
        stats = review_stats.get(normalized, {})
        review_failures = int(item["review_failure_count"]) + int(stats.get("failed_reviews", 0) or 0)
        last_seen = item["last_seen"]
        recency_bonus = 0.0
        if isinstance(last_seen, datetime):
            age_days = max(0, (now - last_seen).days)
            recency_bonus = max(0.0, 1.5 - (age_days / 14))
        score = (
            float(item["recent_count"]) * 2.0
            + float(review_failures) * 3.0
            + float(stats.get("due_bonus", 0) or 0)
            + recency_bonus
        )
        contexts.append(
            PersonalErrorContext(
                error_type=item["error_type"],
                error_pattern=item["error_pattern"],
                normalized_error_pattern=normalized,
                corrected_text=item["corrected_text"],
                original_text=item["original_text"],
                explanation_vi=item["explanation_vi"],
                recent_count=int(item["recent_count"]),
                review_failure_count=review_failures,
                last_seen=last_seen,
                score=score,
            )
        )

    contexts.sort(key=lambda item: (item.score, item.last_seen or datetime.min), reverse=True)
    return contexts[:limit]


def _load_review_stats(db: Session, user_id: uuid.UUID) -> dict[str, dict[str, Any]]:
    rows = db.execute(
        select(UserFlashcardReview, UserFlashcard)
        .join(UserFlashcard, UserFlashcard.id == UserFlashcardReview.flashcard_id)
        .where(UserFlashcardReview.user_id == user_id)
        .where(UserFlashcard.active.is_(True))
    ).all()

    stats: dict[str, dict[str, Any]] = {}
    today = date.today()
    for review, card in rows:
        normalized = _clean(card.normalized_error_pattern)
        if not normalized:
            continue
        item = stats.setdefault(normalized, {"failed_reviews": 0, "due_bonus": 0})
        if int(review.total_reviews or 0) > 0 and int(review.repetitions or 0) == 0:
            item["failed_reviews"] += 1
        if review.next_review and review.next_review <= today:
            item["due_bonus"] += 1
    return stats


def _coerce_uuid(value: uuid.UUID | str) -> uuid.UUID | None:
    if isinstance(value, uuid.UUID):
        return value
    try:
        return uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _clean(value: Any) -> str:
    return str(value or "").strip()
