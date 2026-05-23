from __future__ import annotations

import logging
from collections.abc import Iterable

from sqlalchemy import func, or_, select

from app.core.database import SessionLocal
from app.models.schemas import LearnerProfile, LessonVocabularyItem
from app.models.vocabulary import Vocabulary
from app.services.lesson_catalog import get_lesson


logger = logging.getLogger(__name__)

MOCK_VOCABULARY_SIZE = 5

_BASE_MOCK_VOCAB: tuple[tuple[str, str, str, str], ...] = (
    ("am", "verb", "la, thi, o dang ngoi thu nhat so it", "I am a project assistant."),
    ("is", "verb", "la, thi, o voi chu ngu so it", "She is ready for the client meeting."),
    ("are", "verb", "la, thi, o voi you, we, they hoac danh tu so nhieu", "They are in the meeting room."),
    ("not", "adverb", "tu phu dinh dung sau am, is, are", "The report is not ready yet."),
    ("assistant", "noun", "tro ly, nguoi ho tro cong viec", "I am an assistant in the sales team."),
)


def get_lesson_vocabulary(lesson_id: str, learner: LearnerProfile) -> list[LessonVocabularyItem]:
    lesson = _load_lesson(lesson_id)
    candidate_words = _candidate_words(lesson.metadata if lesson is not None else None)
    items: list[LessonVocabularyItem] = []
    seen_words: set[str] = set()

    for item in _load_db_exact_matches(candidate_words):
        _append_unique(items, seen_words, item)

    if len(items) < MOCK_VOCABULARY_SIZE:
        for item in _load_db_supplemental(learner, exclude_words=seen_words):
            _append_unique(items, seen_words, item)
            if len(items) >= MOCK_VOCABULARY_SIZE:
                return items[:MOCK_VOCABULARY_SIZE]

    for item in _metadata_fallback_items(lesson_id, candidate_words):
        _append_unique(items, seen_words, item)
        if len(items) >= MOCK_VOCABULARY_SIZE:
            return items[:MOCK_VOCABULARY_SIZE]

    for item in _mock_fallback_items(lesson_id):
        _append_unique(items, seen_words, item)
        if len(items) >= MOCK_VOCABULARY_SIZE:
            break

    return items[:MOCK_VOCABULARY_SIZE]


def _load_lesson(lesson_id: str):
    try:
        return get_lesson(lesson_id)
    except KeyError:
        return None


def _candidate_words(metadata: dict | None) -> list[str]:
    if not metadata:
        return []

    raw_words = metadata.get("recommended_vocab") or []
    if not isinstance(raw_words, list):
        return []

    words: list[str] = []
    for item in raw_words:
        word = ""
        if isinstance(item, str):
            word = item.strip()
        elif isinstance(item, dict):
            value = item.get("word") or item.get("term") or item.get("text")
            word = value.strip() if isinstance(value, str) else ""
        if word:
            words.append(word)
    return _dedupe_words(words)


def _load_db_exact_matches(candidate_words: list[str]) -> list[LessonVocabularyItem]:
    if not candidate_words:
        return []

    lowered_words = [word.lower() for word in candidate_words]
    try:
        with SessionLocal() as db:
            rows = list(
                db.execute(
                    select(Vocabulary)
                    .where(func.lower(Vocabulary.word).in_(lowered_words))
                    .order_by(Vocabulary.frequency_rank.asc().nulls_last(), Vocabulary.word.asc())
                ).scalars()
            )
    except Exception:
        logger.exception("lesson_vocabulary_provider: exact-match vocabulary lookup failed")
        return []

    by_word: dict[str, Vocabulary] = {}
    for row in rows:
        key = (row.word or "").strip().lower()
        by_word.setdefault(key, row)

    items: list[LessonVocabularyItem] = []
    for word in candidate_words:
        row = by_word.get(word.lower())
        if row is not None:
            items.append(_db_row_to_item(row))
    return items


def _load_db_supplemental(learner: LearnerProfile, *, exclude_words: set[str]) -> list[LessonVocabularyItem]:
    normalized_industry = (learner.industry or "").strip().lower()
    try:
        with SessionLocal() as db:
            rows = list(
                db.execute(
                    select(Vocabulary)
                    .where(Vocabulary.cefr_level == learner.cefr_level)
                    .where(
                        or_(
                            Vocabulary.industry_tags.any(normalized_industry),
                            Vocabulary.industry_tags.any("general"),
                        )
                    )
                    .order_by(Vocabulary.frequency_rank.asc().nulls_last(), Vocabulary.word.asc())
                    .limit(MOCK_VOCABULARY_SIZE * 2)
                ).scalars()
            )

            if rows:
                return [
                    _db_row_to_item(row)
                    for row in rows
                    if (row.word or "").strip().lower() not in exclude_words
                ]

            fallback_rows = list(
                db.execute(
                    select(Vocabulary)
                    .where(Vocabulary.cefr_level == learner.cefr_level)
                    .order_by(Vocabulary.frequency_rank.asc().nulls_last(), Vocabulary.word.asc())
                    .limit(MOCK_VOCABULARY_SIZE * 2)
                ).scalars()
            )
    except Exception:
        logger.exception("lesson_vocabulary_provider: supplemental vocabulary lookup failed")
        return []

    return [
        _db_row_to_item(row)
        for row in fallback_rows
        if (row.word or "").strip().lower() not in exclude_words
    ]


def _metadata_fallback_items(lesson_id: str, candidate_words: Iterable[str]) -> list[LessonVocabularyItem]:
    slug = _mock_slug(lesson_id)
    return [
        LessonVocabularyItem(
            word_id=f"lesson-meta-{slug}-{index:03d}",
            word=word,
            pos="unknown",
            definition_vi=f"tu/cum tu '{word}' trong bai hoc",
            example=f"The lesson uses {word} in a workplace context.",
            source="lesson_metadata",
        )
        for index, word in enumerate(candidate_words, start=1)
    ]


def _mock_fallback_items(lesson_id: str) -> list[LessonVocabularyItem]:
    slug = _mock_slug(lesson_id)
    return [
        LessonVocabularyItem(
            word_id=f"mock-{slug}-{index:03d}",
            word=word,
            pos=pos,
            definition_vi=definition_vi,
            example=example,
            source="mock",
        )
        for index, (word, pos, definition_vi, example) in enumerate(_BASE_MOCK_VOCAB, start=1)
    ]


def _db_row_to_item(row: Vocabulary) -> LessonVocabularyItem:
    return LessonVocabularyItem(
        word_id=str(row.word_id),
        word=row.word,
        pos=row.pos,
        definition_vi=row.definition_vi,
        example=row.example,
        source="db",
    )


def _append_unique(items: list[LessonVocabularyItem], seen_words: set[str], item: LessonVocabularyItem) -> None:
    normalized = item.word.strip().lower()
    if not normalized or normalized in seen_words:
        return
    seen_words.add(normalized)
    items.append(item)


def _dedupe_words(words: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for word in words:
        normalized = word.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(word.strip())
    return deduped


def _mock_slug(lesson_id: str) -> str:
    return lesson_id.replace("_", "-").lower()
