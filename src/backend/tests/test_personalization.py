from __future__ import annotations

from app.models.processed_dataset_schemas import LearnerProfile
from app.services import personalization


class _FakeMemory:
    def __init__(self) -> None:
        self.added: list[tuple[str, str, dict]] = []

    def search_memory(self, user_id: str, query: str, limit: int = 10):
        assert user_id == "user-1"
        assert query
        assert limit == 20
        return [
            {
                "content": "Learner frequently omits articles before singular countable nouns.",
                "metadata": {"fact_type": "error_pattern"},
            },
            {
                "content": "Learner wants to write professional emails.",
                "metadata": {"fact_type": "goal"},
            },
            {
                "content": "Learner responds best to workplace examples.",
                "metadata": {"type": "preference"},
            },
            {
                "content": "Ignore unrelated row",
                "metadata": {"fact_type": "billing"},
            },
        ]

    def add_memory(self, user_id: str, content: str, metadata: dict):
        self.added.append((user_id, content, metadata))


def test_build_personalization_context_groups_mem0_fact_types():
    context = personalization.build_personalization_context(
        [
            {"content": "Learner confuses present perfect with past simple.", "metadata": {"fact_type": "error_pattern"}},
            {"content": "Learner benefits from review-first sessions.", "metadata": {"fact_type": "mood_pattern"}},
            {"content": "Learner prefers marketing scenarios.", "metadata": {"type": "topic_preference"}},
            {"content": 'Learner has an upcoming exam or test deadline: "Tôi sắp thi IELTS vào ngày 20/06".', "metadata": {"fact_type": "exam_target"}},
            {"content": 'Learner study habit or schedule: "Mỗi ngày tôi học 2 tiếng vào buổi tối".', "metadata": {"fact_type": "study_habit"}},
        ]
    )

    assert context.error_patterns == ["Learner confuses present perfect with past simple."]
    assert context.weak_points == ["present perfect"]
    assert context.mood_patterns == ["Learner benefits from review-first sessions."]
    assert context.preferences == ["Learner prefers marketing scenarios."]
    assert context.goals == ['Learner has an upcoming exam or test deadline: "Tôi sắp thi IELTS vào ngày 20/06".']
    assert context.progress == ['Learner study habit or schedule: "Mỗi ngày tôi học 2 tiếng vào buổi tối".']
    assert "Recurring errors" in context.prompt_summary()


def test_enrich_profile_dict_adds_prompt_summary_and_weak_points(monkeypatch):
    fake = _FakeMemory()
    monkeypatch.setenv("MEMORY_HOTPATH_ENABLED", "true")
    monkeypatch.setattr(personalization, "get_memory", lambda: fake)

    profile = personalization.enrich_profile_dict(
        "user-1",
        {"cefr_level": "B1", "industry": "marketing", "learning_goals": ["emails"]},
    )

    assert profile["weak_points"] == ["article"]
    assert "Learner wants to write professional emails." in profile["personalization_summary"]
    assert profile["personalization"]["preferences"] == ["Learner responds best to workplace examples."]


def test_personalize_learner_profile_preserves_existing_weak_points(monkeypatch):
    fake = _FakeMemory()
    monkeypatch.setenv("MEMORY_HOTPATH_ENABLED", "true")
    monkeypatch.setattr(personalization, "get_memory", lambda: fake)
    base = LearnerProfile(
        user_id="user-1",
        cefr_level="B1",
        industry="marketing",
        learning_goals=["emails"],
        weak_points=["verb forms"],
    )

    enriched = personalization.personalize_learner_profile(base)

    assert enriched.weak_points == ["verb forms", "article"]


def test_enrich_profile_dict_skips_mem0_when_hotpath_disabled(monkeypatch):
    class _ExplodingMemory:
        def search_memory(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("Mem0 should not be called when hotpath is disabled")

    monkeypatch.setenv("MEMORY_HOTPATH_ENABLED", "false")
    monkeypatch.setattr(personalization, "get_memory", lambda: _ExplodingMemory())

    profile = personalization.enrich_profile_dict(
        "user-1",
        {"cefr_level": "B1", "industry": "marketing", "learning_goals": ["emails"]},
    )

    assert profile["personalization"]["error_patterns"] == []
    assert "personalization_summary" not in profile


def test_seed_onboarding_memory_writes_prd_core_fact_types(monkeypatch):
    fake = _FakeMemory()
    monkeypatch.setattr(personalization, "get_memory", lambda: fake)

    written = personalization.seed_onboarding_memory(
        "user-1",
        cefr_level="B1",
        industry="marketing",
        learning_goals=["write emails", "present reports"],
    )

    assert written == 4
    assert [row[2]["fact_type"] for row in fake.added] == [
        "skill_level",
        "industry_vocab",
        "goal",
        "goal",
    ]
