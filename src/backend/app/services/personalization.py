from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Iterable

from ..core.mem0_client import get_memory
from ..models.processed_dataset_schemas import LearnerProfile
from .memory_outbox import enqueue_memory_facts

logger = logging.getLogger(__name__)

PERSONALIZATION_FACT_TYPES = {
    "error_pattern",
    "vocabulary",
    "mood_pattern",
    "industry_vocab",
    "skill_level",
    "topic_preference",
    "preference",
    "study_preference",
    "progress",
    "context",
    "goal",
    "exam_target",
    "study_habit",
    "practice_feedback",
}


@dataclass
class PersonalizationContext:
    facts: list[dict[str, Any]] = field(default_factory=list)
    error_patterns: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    preferences: list[str] = field(default_factory=list)
    workplace_context: list[str] = field(default_factory=list)
    mood_patterns: list[str] = field(default_factory=list)
    progress: list[str] = field(default_factory=list)

    def as_profile_patch(self) -> dict[str, Any]:
        return {
            "personalization": {
                "error_patterns": self.error_patterns,
                "weak_points": self.weak_points,
                "goals": self.goals,
                "preferences": self.preferences,
                "workplace_context": self.workplace_context,
                "mood_patterns": self.mood_patterns,
                "progress": self.progress,
            }
        }

    def prompt_summary(self, *, max_items: int = 12) -> str:
        rows: list[str] = []
        for label, values in (
            ("Recurring errors", self.error_patterns),
            ("Weak points", self.weak_points),
            ("Goals", self.goals),
            ("Preferences", self.preferences),
            ("Work context", self.workplace_context),
            ("Mood patterns", self.mood_patterns),
            ("Progress", self.progress),
        ):
            for value in values[:3]:
                rows.append(f"- {label}: {value}")
                if len(rows) >= max_items:
                    return "\n".join(rows)
        return "\n".join(rows)


def _content(item: dict[str, Any]) -> str:
    value = item.get("content") or item.get("memory") or item.get("text") or ""
    return str(value).strip()


def _metadata(item: dict[str, Any]) -> dict[str, Any]:
    raw = item.get("metadata") or item.get("payload") or {}
    return raw if isinstance(raw, dict) else {}


def _fact_type(item: dict[str, Any]) -> str:
    metadata = _metadata(item)
    raw = metadata.get("fact_type") or metadata.get("type") or item.get("fact_type") or item.get("type") or ""
    return str(raw).strip().lower()


def _dedupe(values: Iterable[str], *, limit: int = 8) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(str(value).split())
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _weak_point_from_text(text: str) -> str:
    lowered = text.lower()
    keywords = (
        "article",
        "preposition",
        "present perfect",
        "past simple",
        "collocation",
        "subject-verb",
        "tense",
        "grammar",
        "vocabulary",
        "pronunciation",
        "writing",
    )
    for keyword in keywords:
        if keyword in lowered:
            return keyword
    return text[:80]


def build_personalization_context(items: Iterable[dict[str, Any]]) -> PersonalizationContext:
    context = PersonalizationContext()
    typed_rows: dict[str, list[str]] = {}
    normalized_facts: list[dict[str, Any]] = []

    for item in items:
        content = _content(item)
        if not content:
            continue
        fact_type = _fact_type(item)
        if fact_type and fact_type not in PERSONALIZATION_FACT_TYPES:
            continue
        normalized_facts.append({"content": content, "metadata": _metadata(item)})
        typed_rows.setdefault(fact_type or "context", []).append(content)

    context.facts = normalized_facts
    context.error_patterns = _dedupe(typed_rows.get("error_pattern", []) + typed_rows.get("practice_feedback", []))
    context.weak_points = _dedupe((_weak_point_from_text(row) for row in context.error_patterns), limit=6)
    context.goals = _dedupe(typed_rows.get("goal", []) + typed_rows.get("exam_target", []), limit=5)
    context.preferences = _dedupe(
        typed_rows.get("preference", []) + typed_rows.get("topic_preference", []) + typed_rows.get("study_preference", []),
        limit=5,
    )
    context.workplace_context = _dedupe(
        typed_rows.get("context", []) + typed_rows.get("industry_vocab", []),
        limit=5,
    )
    context.mood_patterns = _dedupe(typed_rows.get("mood_pattern", []), limit=5)
    context.progress = _dedupe(
        typed_rows.get("progress", []) + typed_rows.get("skill_level", []) + typed_rows.get("study_habit", []),
        limit=5,
    )
    return context


def load_personalization_context(user_id: str, query: str = "learner profile errors goals preferences mood work context") -> PersonalizationContext:
    if os.getenv("MEMORY_HOTPATH_ENABLED", "true").strip().lower() != "true":
        return PersonalizationContext()

    try:
        rows = get_memory().search_memory(user_id=user_id, query=query, limit=20)
    except Exception:  # pragma: no cover - memory must not break tutoring
        logger.exception("personalization: Mem0 profile retrieval failed for user_id=%s", user_id)
        rows = []
    return build_personalization_context(rows)


def enrich_profile_dict(user_id: str, profile: dict[str, Any], *, query: str | None = None) -> dict[str, Any]:
    context = load_personalization_context(user_id, query=query or "learner profile")
    enriched = dict(profile)
    enriched.update(context.as_profile_patch())
    if context.weak_points:
        existing = [str(item) for item in enriched.get("weak_points") or []]
        enriched["weak_points"] = _dedupe([*existing, *context.weak_points], limit=8)
    summary = context.prompt_summary()
    if summary:
        enriched["personalization_summary"] = summary
    return enriched


def personalize_learner_profile(profile: LearnerProfile) -> LearnerProfile:
    context = load_personalization_context(profile.user_id)
    weak_points = _dedupe([*profile.weak_points, *context.weak_points], limit=8)
    return profile.model_copy(update={"weak_points": weak_points})


def _onboarding_facts(*, cefr_level: str, industry: str, learning_goals: list[str]) -> list[dict[str, Any]]:
    facts = [
        {
            "content": f"Learner CEFR level is {cefr_level}.",
            "metadata": {"fact_type": "skill_level", "source": "onboarding", "importance_score": 0.9, "cefr_level": cefr_level},
        },
        {
            "content": f"Learner works in or studies the {industry} domain; prioritize industry-specific examples when useful.",
            "metadata": {"fact_type": "industry_vocab", "source": "onboarding", "importance_score": 0.85, "industry": industry},
        },
    ]
    for goal in learning_goals[:5]:
        facts.append(
            {
                "content": f"Learner goal: {goal}.",
                "metadata": {"fact_type": "goal", "source": "onboarding", "importance_score": 0.85},
            }
        )
    return facts


def seed_onboarding_memory(user_id: str, *, cefr_level: str, industry: str, learning_goals: list[str], db=None) -> int:
    facts = _onboarding_facts(cefr_level=cefr_level, industry=industry, learning_goals=learning_goals)

    if db is not None and os.getenv("MEMORY_WRITE_MODE", "queued").strip().lower() == "queued":
        return enqueue_memory_facts(db, user_id=user_id, facts=facts, source="onboarding", commit=True)

    written = 0
    memory = get_memory()
    for fact in facts:
        try:
            memory.add_memory(user_id=user_id, content=fact["content"], metadata=fact.get("metadata", {}))
            written += 1
        except Exception:  # pragma: no cover - onboarding must not fail on Mem0 outage
            logger.exception("personalization: failed to seed onboarding fact for user_id=%s", user_id)
    return written
