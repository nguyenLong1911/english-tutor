from __future__ import annotations

import re
import unicodedata
from typing import Any


_EXAM_MARKERS = (
    "sap thi",
    "sắp thi",
    "ki thi",
    "kỳ thi",
    "thi vao",
    "thi vào",
    "on thi",
    "ôn thi",
    "exam",
    "test",
    "ielts",
    "toeic",
    "toefl",
    "sat",
)

_PREFERENCE_MARKERS = (
    "toi thich",
    "tôi thích",
    "minh thich",
    "mình thích",
    "toi muon hoc qua",
    "tôi muốn học qua",
    "toi hoc tot hon voi",
    "tôi học tốt hơn với",
    "i like",
    "i prefer",
    "prefer to study",
    "learn best with",
    "work best with",
)

_GOAL_MARKERS = (
    "muc tieu",
    "mục tiêu",
    "toi muon",
    "tôi muốn",
    "minh muon",
    "mình muốn",
    "toi can",
    "tôi cần",
    "i want to",
    "i need to",
    "my goal is",
    "prepare for",
    "achieve",
    "dat ",
    "đạt ",
)

_STUDY_HABIT_MARKERS = (
    "moi ngay",
    "mỗi ngày",
    "hang ngay",
    "hằng ngày",
    "thuong hoc",
    "thường học",
    "buoi sang",
    "buổi sáng",
    "buoi toi",
    "buổi tối",
    "cuoi tuan",
    "cuối tuần",
    "after work",
    "before work",
    "every day",
    "every morning",
    "every evening",
    "every weekend",
    "hours a day",
)

_SCHEDULE_MARKERS = (
    "vao ngay",
    "vào ngày",
    "truoc ngay",
    "trước ngày",
    "truoc thang",
    "trước tháng",
    "deadline",
    "by ",
    "before ",
)

_DATE_PATTERN = re.compile(
    r"(\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{4}-\d{2}-\d{2}\b|\bngay\s+\d{1,2}(?:[/-]\d{1,2}(?:[/-]\d{2,4})?)?\b|\bthang\s+\d{1,2}\b|\bmonth\s+\d{1,2}\b)",
    re.IGNORECASE,
)
_TARGET_SCORE_PATTERN = re.compile(r"\b(?:ielts|toeic|toefl|sat)\s*\d[\d.]*(?:\+)?\b", re.IGNORECASE)
_DURATION_PATTERN = re.compile(
    r"(\b\d+\s*(?:gio|giờ|tieng|tiếng|phut|phút|hours?|minutes?)\b|\b\d+\s*(?:h|m)\/?(?:day|ngay|ngày)\b)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    lowered = str(text or "").strip().lower().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", lowered)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _split_sentences(message: str) -> list[str]:
    parts = re.split(r"[\n\r]+|(?<=[.!?;])\s+", str(message or "").strip())
    return [part.strip(" \t\r\n-") for part in parts if part and part.strip()]


def _make_fact(content: str, *, fact_type: str, source_label: str, importance: float, snippet: str) -> dict[str, Any]:
    return {
        "content": content,
        "metadata": {
            "fact_type": fact_type,
            "source": "chat_profile_extractor",
            "source_label": source_label,
            "importance_score": importance,
            "snippet": snippet[:240],
        },
    }


def _extract_exam_fact(sentence: str, normalized: str) -> dict[str, Any] | None:
    has_exam_marker = any(marker in normalized for marker in _EXAM_MARKERS)
    has_schedule = bool(_DATE_PATTERN.search(sentence)) or any(marker in normalized for marker in _SCHEDULE_MARKERS)
    target_score = _TARGET_SCORE_PATTERN.search(sentence)
    if not has_exam_marker and not target_score:
        return None
    if target_score:
        return _make_fact(
            f'Learner has an exam target: "{sentence}".',
            fact_type="exam_target",
            source_label="exam_target",
            importance=0.92,
            snippet=sentence,
        )
    if has_schedule:
        return _make_fact(
            f'Learner has an upcoming exam or test deadline: "{sentence}".',
            fact_type="exam_target",
            source_label="exam_deadline",
            importance=0.9,
            snippet=sentence,
        )
    return None


def _extract_preference_fact(sentence: str, normalized: str) -> dict[str, Any] | None:
    if not any(marker in normalized for marker in _PREFERENCE_MARKERS):
        return None
    return _make_fact(
        f'Learner study preference: "{sentence}".',
        fact_type="study_preference",
        source_label="study_preference",
        importance=0.84,
        snippet=sentence,
    )


def _extract_goal_fact(sentence: str, normalized: str) -> dict[str, Any] | None:
    if not any(marker in normalized for marker in _GOAL_MARKERS):
        return None
    if any(marker in normalized for marker in ("mo bai", "mở bài", "flashcard", "on tap", "ôn tập", "review tab")):
        return None
    return _make_fact(
        f'Learner goal or desired outcome: "{sentence}".',
        fact_type="goal",
        source_label="goal",
        importance=0.86,
        snippet=sentence,
    )


def _extract_study_habit_fact(sentence: str, normalized: str) -> dict[str, Any] | None:
    if not any(marker in normalized for marker in _STUDY_HABIT_MARKERS):
        return None
    if not _DURATION_PATTERN.search(sentence) and not any(
        marker in normalized for marker in ("buoi", "buổi", "every", "after work", "before work", "cuoi tuan", "cuối tuần")
    ):
        return None
    return _make_fact(
        f'Learner study habit or schedule: "{sentence}".',
        fact_type="study_habit",
        source_label="study_habit",
        importance=0.78,
        snippet=sentence,
    )


def _dedupe_facts(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    deduped: list[dict[str, Any]] = []
    for fact in facts:
        content = str(fact.get("content", "")).strip()
        metadata = fact.get("metadata") or {}
        fact_type = str(metadata.get("fact_type", "")).strip().lower()
        key = (fact_type, content.lower())
        if not content or key in seen:
            continue
        seen.add(key)
        deduped.append(fact)
    return deduped


def extract_profile_facts(
    message: str,
    *,
    intent: str | None = None,
    learning_intent: str | None = None,
    command: str | None = None,
    message_type: str | None = None,
) -> list[dict[str, Any]]:
    if not str(message or "").strip():
        return []
    if str(message_type or "").strip().upper() == "SYSTEM_COMMAND":
        return []
    if str(learning_intent or "NONE").strip().upper() != "NONE":
        return []

    facts: list[dict[str, Any]] = []
    for sentence in _split_sentences(message):
        normalized = _normalize(sentence)
        for extractor in (
            _extract_exam_fact,
            _extract_preference_fact,
            _extract_goal_fact,
            _extract_study_habit_fact,
        ):
            fact = extractor(sentence, normalized)
            if fact is not None:
                facts.append(fact)

    return _dedupe_facts(facts)
