import json
import logging
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.schemas import ReviewItem, ReviewSubmit, ReviewSubmitResult
from ...models.personal_review import UserFlashcard, UserFlashcardReview
from ...models.vocabulary import Vocabulary, UserVocabulary
from ...services.error_capture_service import capture_error_and_flashcard
from ...services.sm2_scheduler import SM2State, update_sm2


router = APIRouter(tags=["review"])
logger = logging.getLogger(__name__)


@router.get("/review/due", response_model=list[ReviewItem])
def review_due(
    user_id: UUID = Query(...),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    today = date.today()
    vocab_stmt = (
        select(UserVocabulary, Vocabulary)
        .join(Vocabulary, Vocabulary.word_id == UserVocabulary.word_id)
        .where(UserVocabulary.user_id == user_id)
        .where(UserVocabulary.next_review <= today)
        .order_by(UserVocabulary.next_review.asc())
        .limit(limit)
    )
    vocab_rows = db.execute(vocab_stmt).all()

    payload = [
        ReviewItem(
            card_kind="vocab",
            word_id=v.word_id,
            word=v.word,
            pos=v.pos,
            definition_vi=v.definition_vi,
            example=v.example,
            next_review=uv.next_review,
            repetitions=uv.repetitions,
            ease_factor=uv.ease_factor,
            interval_days=uv.interval_days,
        )
        for uv, v in vocab_rows
    ]

    remaining = max(0, limit - len(payload))
    if remaining:
        error_stmt = (
            select(UserFlashcardReview, UserFlashcard)
            .join(UserFlashcard, UserFlashcard.id == UserFlashcardReview.flashcard_id)
            .where(UserFlashcardReview.user_id == user_id)
            .where(UserFlashcardReview.next_review <= today)
            .where(UserFlashcard.active.is_(True))
            .order_by(UserFlashcardReview.next_review.asc())
            .limit(remaining)
        )
        error_rows = db.execute(error_stmt).all()
        payload.extend(
            ReviewItem(
                card_kind="error",
                flashcard_id=card.id,
                word="Personal correction",
                pos=card.error_type,
                definition_vi=card.explanation_vi or card.back,
                example=card.cloze_text,
                next_review=review.next_review,
                repetitions=review.repetitions,
                ease_factor=review.ease_factor,
                interval_days=review.interval_days,
                front=card.front,
                back=card.back,
                cloze_text=card.cloze_text,
                explanation_vi=card.explanation_vi,
                error_type=card.error_type,
                source=card.source,
            )
            for review, card in error_rows
        )

    payload.sort(key=lambda item: item.next_review)
    payload = payload[:limit]
    logger.info(
        "frontend_payload.vocabulary.review_due %s",
        json.dumps(_review_due_log_summary(payload), ensure_ascii=False, default=str),
    )
    return payload


@router.post("/review/submit", response_model=ReviewSubmitResult)
def submit_review(payload: ReviewSubmit, db: Session = Depends(get_db)):
    if payload.card_kind == "error":
        return _submit_error_review(payload, db)
    uv = db.get(UserVocabulary, (payload.user_id, payload.word_id))
    if uv is None:
        raise HTTPException(status_code=404, detail="user/word pair not found")

    state = SM2State(
        ease_factor=uv.ease_factor,
        interval_days=uv.interval_days,
        repetitions=uv.repetitions,
        next_review=uv.next_review,
        mastered=uv.mastered,
        total_reviews=uv.total_reviews,
    )
    state = update_sm2(state, payload.quality)

    uv.ease_factor = state.ease_factor
    uv.interval_days = state.interval_days
    uv.repetitions = state.repetitions
    uv.next_review = state.next_review
    uv.mastered = state.mastered
    uv.total_reviews = state.total_reviews
    uv.last_reviewed_at = datetime.utcnow()

    db.commit()

    return ReviewSubmitResult(
        card_kind="vocab",
        word_id=uv.word_id,
        next_review=uv.next_review,
        interval_days=uv.interval_days,
        ease_factor=uv.ease_factor,
        repetitions=uv.repetitions,
        mastered=uv.mastered,
    )


def _submit_error_review(payload: ReviewSubmit, db: Session) -> ReviewSubmitResult:
    review = db.get(UserFlashcardReview, (payload.user_id, payload.flashcard_id))
    if review is None:
        raise HTTPException(status_code=404, detail="user/flashcard pair not found")
    card = db.get(UserFlashcard, payload.flashcard_id)
    if card is None:
        raise HTTPException(status_code=404, detail="flashcard not found")

    state = SM2State(
        ease_factor=review.ease_factor,
        interval_days=review.interval_days,
        repetitions=review.repetitions,
        next_review=review.next_review,
        mastered=review.mastered,
        total_reviews=review.total_reviews,
    )
    state = update_sm2(state, payload.quality)

    review.ease_factor = state.ease_factor
    review.interval_days = state.interval_days
    review.repetitions = state.repetitions
    review.next_review = state.next_review
    review.mastered = state.mastered
    review.total_reviews = state.total_reviews
    review.last_reviewed_at = datetime.utcnow()

    if payload.quality < 3:
        capture_error_and_flashcard(
            db,
            user_id=payload.user_id,
            original_text=card.cloze_text or card.front,
            payload={
                "corrected_text": card.back,
                "error_pattern": card.normalized_error_pattern,
                "error_type": card.error_type,
                "explanation_vi": card.explanation_vi,
                "confidence": 0.8,
            },
            source="review",
            source_metadata={"flashcard_id": str(card.id), "quality": payload.quality},
            commit=False,
        )

    db.commit()
    return ReviewSubmitResult(
        card_kind="error",
        flashcard_id=review.flashcard_id,
        next_review=review.next_review,
        interval_days=review.interval_days,
        ease_factor=review.ease_factor,
        repetitions=review.repetitions,
        mastered=review.mastered,
    )


def _review_due_log_summary(items: list[ReviewItem]) -> dict:
    return {
        "count": len(items),
        "items": [
            {
                "card_kind": item.card_kind,
                "word_id": item.word_id,
                "word": item.word,
                "pos": item.pos,
                "flashcard_id": item.flashcard_id,
                "error_type": item.error_type,
                "next_review": item.next_review,
                "repetitions": item.repetitions,
                "interval_days": item.interval_days,
                "ease_factor": item.ease_factor,
            }
            for item in items
        ],
    }
