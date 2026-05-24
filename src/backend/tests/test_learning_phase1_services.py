from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from app.models.processed_dataset_schemas import LessonQuestion, LearningState, UIDirective
from app.services import lesson_catalog
from app.services import lesson_vocabulary_provider as lesson_vocab_module
from app.services.learner_profile_provider import get_learner_profile
from app.services.lesson_vocabulary_provider import get_lesson_vocabulary


def _write_lesson(root: Path, cefr: str, filename: str, *, topic_id: str, title: str) -> None:
    lesson_dir = root / "data" / "curriculum_skeleton" / cefr
    lesson_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(filename).stem
    (lesson_dir / filename).write_text(
        f"---\ntopic_id: frontmatter_{topic_id}\ntitle: Frontmatter Title\n---\n\n# {title}\n\nLearner content.",
        encoding="utf-8",
    )
    (lesson_dir / f"{stem}.yaml").write_text(
        f"topic_id: {topic_id}\ntitle: {title}\ncefr_level: {cefr}\nskill_type: grammar\n",
        encoding="utf-8",
    )


@pytest.fixture()
def temp_curriculum(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    curriculum_root = tmp_path / "data" / "curriculum_skeleton"
    monkeypatch.setattr(lesson_catalog, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(lesson_catalog, "CURRICULUM_ROOT", curriculum_root)
    return curriculum_root


def test_lesson_catalog_sorts_by_cefr_folder_and_numeric_prefix(temp_curriculum: Path):
    root = temp_curriculum.parents[1]
    _write_lesson(root, "B1", "02_B1_second.md", topic_id="B1_second", title="B1 Second")
    _write_lesson(root, "A2", "10_A2_tenth.md", topic_id="A2_tenth", title="A2 Tenth")
    _write_lesson(root, "A2", "01_A2_first.md", topic_id="A2_first", title="A2 First")
    _write_lesson(root, "B1", "01_B1_first.md", topic_id="B1_first", title="B1 First")

    lessons = lesson_catalog.list_lessons()

    assert [lesson.lesson_id for lesson in lessons] == [
        "A2_first",
        "A2_tenth",
        "B1_first",
        "B1_second",
    ]


def test_get_lesson_prefers_yaml_metadata_and_returns_learner_markdown(temp_curriculum: Path):
    root = temp_curriculum.parents[1]
    _write_lesson(
        root,
        "A2",
        "01_A2_present_simple_be.md",
        topic_id="A2_present_simple_be",
        title="Present Simple with be",
    )

    lesson = lesson_catalog.get_lesson("A2_present_simple_be")

    assert lesson.title == "Present Simple with be"
    assert lesson.metadata["topic_id"] == "A2_present_simple_be"
    assert lesson.lesson_path == "data/curriculum_skeleton/A2/01_A2_present_simple_be.md"
    assert lesson.markdown.startswith("# Present Simple with be")
    assert "frontmatter_A2_present_simple_be" not in lesson.markdown


def test_get_next_lesson_returns_first_sorted_lesson_for_level(temp_curriculum: Path):
    root = temp_curriculum.parents[1]
    _write_lesson(root, "A2", "02_A2_second.md", topic_id="A2_second", title="A2 Second")
    _write_lesson(root, "A2", "01_A2_first.md", topic_id="A2_first", title="A2 First")

    next_lesson = lesson_catalog.get_next_lesson("mock-user", "A2")

    assert next_lesson.lesson_id == "A2_first"


def test_lesson_vocabulary_provider_uses_hybrid_fallbacks(monkeypatch: pytest.MonkeyPatch):
    learner = get_learner_profile()
    monkeypatch.setattr(lesson_vocab_module, "_load_db_exact_matches", lambda candidate_words: [])
    monkeypatch.setattr(lesson_vocab_module, "_load_db_supplemental", lambda learner, exclude_words: [])

    vocabulary = get_lesson_vocabulary("A2_present_simple_be", learner)

    assert len(vocabulary) == 5
    assert vocabulary[0].source == "lesson_metadata"
    assert vocabulary[0].word == "meeting"
    assert vocabulary[0].word_id == "lesson-meta-a2-present-simple-be-001"
    assert any(item.source == "mock" for item in vocabulary[1:])


def test_mock_learner_profile_matches_phase_one_contract():
    profile = get_learner_profile()

    assert profile.user_id == "mock-user"
    assert profile.cefr_level == "A2"
    assert profile.industry == "business"
    assert profile.learning_goals == ["daily work communication"]
    assert profile.weak_points == ["articles", "verb forms"]
    assert profile.preferred_language == "vi"


def test_learning_foundation_schemas_validate_ui_and_state_contracts():
    state = LearningState(active_lesson_id="A2_present_simple_be", current_step="LESSON_READING")
    directive = UIDirective(
        screen="LESSON_READER",
        action="OPEN",
        lesson_id="A2_present_simple_be",
        reason="start_learning",
    )

    assert state.practice_completed is False
    assert directive.screen == "LESSON_READER"


def test_multiple_choice_question_requires_four_choices():
    with pytest.raises(ValidationError):
        LessonQuestion(
            question_id="A2_present_simple_be-q001",
            lesson_id="A2_present_simple_be",
            type="multiple_choice_abcd",
            prompt="Choose the correct sentence.",
            choices=[],
            correct_answer="A",
            difficulty="A2",
        )
