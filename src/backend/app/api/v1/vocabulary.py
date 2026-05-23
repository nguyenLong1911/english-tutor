import json
import logging
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, or_, not_, exists, select
from sqlalchemy.orm import Session

from ...core.database import get_db
from ...models.schemas import VocabularyOut
from ...models.user import User
from ...models.vocabulary import Vocabulary, UserVocabulary


router = APIRouter(tags=["vocabulary"])
logger = logging.getLogger(__name__)


@router.get("/vocabulary/new", response_model=list[VocabularyOut])
def get_new_vocabulary(
    user_id: UUID = Query(..., description="User to source CEFR/industry from"),
    limit: int = Query(3, ge=1, le=20),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")

    # words the user has already started learning
    seen_subq = (
        select(UserVocabulary.word_id)
        .where(UserVocabulary.user_id == user_id)
        .scalar_subquery()
    )

    industry_filter = or_(
        Vocabulary.industry_tags.any(user.industry),
        Vocabulary.industry_tags.any("general"),
    )

    stmt = (
        select(Vocabulary)
        .where(
            and_(
                Vocabulary.cefr_level == user.cefr_level,
                industry_filter,
                Vocabulary.word_id.notin_(seen_subq),
            )
        )
        .order_by(Vocabulary.frequency_rank.asc().nulls_last())
        .limit(limit)
    )

    rows = db.execute(stmt).scalars().all()

    # Track that we surfaced these words so they enter the SM-2 schedule
    today = date.today()
    for vocab in rows:
        existing = db.get(UserVocabulary, (user_id, vocab.word_id))
        if existing is None:
            db.add(
                UserVocabulary(
                    user_id=user_id,
                    word_id=vocab.word_id,
                    next_review=today,
                )
            )
    db.commit()

    payload = [VocabularyOut.model_validate(row).model_dump(mode="json") for row in rows]
    logger.info("frontend_payload.vocabulary.new %s", json.dumps(payload, ensure_ascii=False, default=str))
    return rows
