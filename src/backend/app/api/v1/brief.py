"""Morning Brief (§9.4): 3 retrieval Qs each morning, SM-2 driven."""
from __future__ import annotations

import json
import logging
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user
from ...core.database import get_db
from ...core.redis_client import get_redis
from ...models.personal_review import UserFlashcard
from ...models.user import User
from ...models.vocabulary import UserVocabulary, Vocabulary
from ...services.error_capture_service import capture_error_and_flashcard
from ...services.sm2_scheduler import SM2State, update_sm2
from ...utils.llm import get_llm_client

router = APIRouter(tags=["brief"])
logger = logging.getLogger(__name__)

BRIEF_KEY = "brief:{user_id}:{date}"


class BriefAnswer(BaseModel):
    word_id: int
    quality: int
    user_answer: str | None = None


class BriefSubmit(BaseModel):
    answers: list[BriefAnswer]


def _pick_due_words(db: Session, user_id, limit: int = 3) -> list[Vocabulary]:
    today = date.today()
    rows = db.execute(
        select(Vocabulary, UserVocabulary)
        .join(UserVocabulary, UserVocabulary.word_id == Vocabulary.word_id)
        .where(
            UserVocabulary.user_id == user_id,
            UserVocabulary.next_review <= today,
            or_(UserVocabulary.brief_skip_until.is_(None), UserVocabulary.brief_skip_until < today),
        )
        .order_by(UserVocabulary.next_review.asc())
        .limit(limit)
    ).all()
    return [r[0] for r in rows]


def _normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFD", str(value or "").strip().lower())
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _candidate_definitions(definition_vi: str) -> list[str]:
    full = _normalize_text(definition_vi)
    candidates = {full} if full else set()
    for part in re.split(r"[;/,\n]|(?:\shoac\s)|(?:\shay\s)", full):
        candidate = part.strip()
        if len(candidate) >= 3:
            candidates.add(candidate)
    return sorted(candidates, key=len, reverse=True)


def _is_answer_correct(user_answer: str, definition_vi: str) -> bool:
    answer = _normalize_text(user_answer)
    if not answer:
        return False

    answer_tokens = set(answer.split())
    for candidate in _candidate_definitions(definition_vi):
        if not candidate:
            continue
        if answer == candidate or answer in candidate or candidate in answer:
            return True
        candidate_tokens = set(candidate.split())
        if candidate_tokens and candidate_tokens.issubset(answer_tokens):
            return True
        overlap = len(candidate_tokens & answer_tokens)
        if overlap and overlap / max(len(candidate_tokens), 1) >= 0.8:
            return True
    return False


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^`{1,3}(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*`{1,3}$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None

    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _judge_answer_correctness_with_llm(
    *,
    word: str,
    prompt_vi: str,
    definition_vi: str,
    user_answer: str,
) -> bool | None:
    cleaned_answer = str(user_answer or "").strip()
    if not cleaned_answer:
        return False

    llm = get_llm_client()
    messages = [
        {
            "role": "system",
            "content": (
                "You evaluate whether a Vietnamese learner's answer matches the correct Vietnamese meaning of one English word. "
                "Be strict about semantic meaning, but allow close Vietnamese paraphrases, synonym phrases, and minor spelling/diacritic differences. "
                "Do not reward answers that are merely related, too broad, opposite, or only partially correct. "
                "Return only one valid JSON object with keys: is_correct, rationale."
            ),
        },
        {
            "role": "user",
            "content": (
                f'English word: "{word}"\n'
                f'Question shown to learner: "{prompt_vi}"\n'
                f'Correct Vietnamese meaning: "{definition_vi}"\n'
                f'Learner answer: "{cleaned_answer}"\n\n'
                "Decide whether the learner answer should count as correct for Morning Brief."
            ),
        },
    ]

    try:
        raw = await llm.generate_chat_completion(messages, temperature=0.0, max_tokens=120)
    except Exception:
        logger.exception("brief: llm judge failed for word=%s", word)
        return None

    provider = getattr(llm, "last_provider", "mock")
    if provider in {"mock", "guardrail"}:
        return None

    parsed = _extract_json_object(raw)
    if parsed is None:
        logger.warning("brief: llm judge returned non-json for word=%s: %r", word, raw[:200])
        return None

    value = parsed.get("is_correct")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "correct", "yes"}:
            return True
        if lowered in {"false", "incorrect", "no"}:
            return False
    return None


def _maybe_capture_brief_error(
    db: Session,
    *,
    user: User,
    vocab: Vocabulary,
    user_answer: str,
    quality: int,
) -> UserFlashcard | None:
    cleaned_answer = str(user_answer or "").strip()
    if not cleaned_answer:
        return None

    captured = capture_error_and_flashcard(
        db,
        user_id=user.user_id,
        original_text=cleaned_answer,
        payload={
            "corrected_text": vocab.definition_vi,
            "error_pattern": f"{cleaned_answer} -> {vocab.definition_vi}",
            "error_type": "vocab",
            "explanation_vi": f'Nghĩa đúng của "{vocab.word}" là: {vocab.definition_vi}',
            "confidence": 0.95,
        },
        source="brief",
        cefr_level=vocab.cefr_level,
        industry=user.industry,
        source_metadata={
            "word_id": vocab.word_id,
            "word": vocab.word,
            "quality": quality,
            "brief_date": date.today().isoformat(),
        },
        commit=False,
    )
    return captured.flashcard


@router.get("/brief/today")
async def brief_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict[str, Any]:
    redis = get_redis()
    key = BRIEF_KEY.format(user_id=user.user_id, date=date.today().isoformat())
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)

    words = _pick_due_words(db, user.user_id, 3)
    questions = [
        {
            "word_id": w.word_id,
            "prompt_vi": f'Nghĩa tiếng Việt của "{w.word}" là gì?',
            "answer": w.definition_vi,
            "example": w.example,
        }
        for w in words
    ]
    payload = {"date": date.today().isoformat(), "questions": questions}
    await redis.setex(key, 60 * 60 * 18, json.dumps(payload, default=str))
    return payload


@router.post("/brief/submit")
async def brief_submit(
    payload: BriefSubmit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    results = []
    touched_word_ids: set[int] = set()
    for ans in payload.answers:
        try:
            wid = int(ans.word_id)
            quality = int(ans.quality)
        except (TypeError, ValueError):
            continue
        if quality < 0 or quality > 5:
            continue
        if wid in touched_word_ids:
            continue

        uv = db.get(UserVocabulary, (user.user_id, wid))
        vocab = db.get(Vocabulary, wid)
        if not uv or not vocab:
            continue

        touched_word_ids.add(wid)
        user_answer = str(ans.user_answer or "").strip()
        answer_correct = None
        used_llm_judge = False
        if user_answer:
            answer_correct = await _judge_answer_correctness_with_llm(
                word=vocab.word,
                prompt_vi=f'Nghĩa tiếng Việt của "{vocab.word}" là gì?',
                definition_vi=vocab.definition_vi,
                user_answer=user_answer,
            )
            used_llm_judge = answer_correct is not None
            if answer_correct is None:
                answer_correct = _is_answer_correct(user_answer, vocab.definition_vi)
        else:
            answer_correct = False

        s = SM2State(
            ease_factor=uv.ease_factor,
            interval_days=uv.interval_days,
            repetitions=uv.repetitions,
            next_review=uv.next_review,
            mastered=uv.mastered,
            total_reviews=uv.total_reviews,
        )
        s = update_sm2(s, quality)
        uv.ease_factor = s.ease_factor
        uv.interval_days = s.interval_days
        uv.repetitions = s.repetitions
        uv.next_review = s.next_review
        uv.mastered = s.mastered
        uv.total_reviews = s.total_reviews
        uv.last_reviewed_at = datetime.utcnow()

        flashcard = None
        if answer_correct is True:
            # Skip exactly the next Morning Brief cycle, while preserving the
            # normal SM-2 schedule used by the main review queue.
            uv.brief_skip_until = date.today() + timedelta(days=1)
        else:
            uv.brief_skip_until = None
            if answer_correct is False:
                flashcard = _maybe_capture_brief_error(
                    db,
                    user=user,
                    vocab=vocab,
                    user_answer=user_answer,
                    quality=quality,
                )

        results.append(
            {
                "word_id": wid,
                "next_review": s.next_review.isoformat(),
                "mastered": s.mastered,
                "user_answer": user_answer,
                "answer_correct": answer_correct,
                "answer_judge": "llm" if used_llm_judge else "heuristic",
                "brief_skip_until": uv.brief_skip_until.isoformat() if uv.brief_skip_until else None,
                "error_flashcard_id": str(flashcard.id) if flashcard else None,
            }
        )

    db.commit()

    redis = get_redis()
    key = BRIEF_KEY.format(user_id=user.user_id, date=date.today().isoformat())
    await redis.delete(key)

    return {"updated": results}
