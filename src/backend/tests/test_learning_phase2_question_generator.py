from __future__ import annotations

import asyncio
import json
from collections import Counter

import pytest
from pydantic import ValidationError

from app.models.processed_dataset_schemas import (
    LearnerProfile,
    LessonContent,
    LessonPracticeSet,
    LessonQuestion,
    LessonQuestionChoice,
    LessonVocabularyItem,
)
from app.services import lesson_question_generator as generator_module
from app.services.lesson_question_generator import (
    DEFAULT_QUESTION_PLAN,
    QuestionPlan,
    create_lesson_questions,
)


def _lesson() -> LessonContent:
    return LessonContent(
        lesson_id="A2_present_simple_be",
        title="Present Simple with to be",
        cefr_level="A2",
        lesson_path="data/curriculum_skeleton/A2/01_A2_present_simple_be.md",
        metadata_path="data/curriculum_skeleton/A2/01_A2_present_simple_be.yaml",
        order_index=1,
        skill_type="grammar",
        metadata={
            "topic_id": "A2_present_simple_be",
            "title": "Present Simple with to be",
            "cefr_level": "A2",
            "skill_type": "grammar",
            "recommended_vocab": ["meeting"],
            "common_errors": [
                {
                    "wrong": "She are a teacher",
                    "correct": "She is a teacher",
                    "hint": "Chu ngu so it di voi is.",
                }
            ],
        },
        markdown=(
            "# Present Simple with to be\n\n"
            "Example: `I am a project assistant.`\n"
            "Example: `They are ready for the client meeting.`\n"
        ),
    )


def _learner() -> LearnerProfile:
    return LearnerProfile(
        user_id="mock-user",
        cefr_level="A2",
        industry="business",
        learning_goals=["daily work communication"],
        weak_points=["articles", "verb forms"],
        preferred_language="vi",
    )


def _vocabulary() -> list[LessonVocabularyItem]:
    return [
        LessonVocabularyItem(
            word_id="mock-a2-present-simple-be-001",
            word="am",
            pos="verb",
            definition_vi="la, thi, o dang ngoi thu nhat so it",
            example="I am a project assistant.",
            source="mock",
        ),
        LessonVocabularyItem(
            word_id="mock-a2-present-simple-be-002",
            word="assistant",
            pos="noun",
            definition_vi="tro ly, nguoi ho tro cong viec",
            example="I am an assistant in the sales team.",
            source="mock",
        ),
    ]


def _llm_question_payload() -> str:
    questions = []
    for index in range(5):
        questions.append(
            {
                "type": "multiple_choice_abcd",
                "prompt": f"Choose the best sentence for the learner's sales meeting scenario #{index + 1}.",
                "choices": [
                    {"key": "A", "text": f"The team is ready for the client meeting {index + 1}."},
                    {"key": "B", "text": f"The team are ready for the client meeting {index + 1}."},
                    {"key": "C", "text": f"The team am ready for the client meeting {index + 1}."},
                    {"key": "D", "text": f"The team be ready for the client meeting {index + 1}."},
                ],
                "correct_answer": "A",
                "target_vocab": ["meeting"],
                "rubric": {"acceptable_answers": ["A"], "explanation_vi": "Dung cau dung cho boi canh hop voi khach hang."},
            }
        )
    for index in range(3):
        questions.append(
            {
                "type": "write_sentence",
                "prompt": f"Write one sentence for a client update using 'assistant' #{index + 1}.",
                "choices": [],
                "correct_answer": "assistant",
                "target_vocab": ["assistant"],
                "rubric": {
                    "must_include": ["assistant"],
                    "target_structure": "grammar: Present Simple with to be",
                    "min_words": 5,
                    "explanation_vi": "Dung tu assistant trong cau lien quan cong viec.",
                },
            }
        )
    for index in range(2):
        questions.append(
            {
                "type": "vocab_answer",
                "prompt": f"Complete the sentence: I am an ___ in the sales team {index + 1}.",
                "choices": [],
                "correct_answer": "assistant",
                "target_vocab": ["assistant"],
                "rubric": {
                    "acceptable_answers": ["assistant"],
                    "explanation_vi": "Can dien dung tu assistant.",
                },
            }
        )
    for index in range(2):
        questions.append(
            {
                "type": "quick_definition",
                "prompt": f"What does 'meeting' mean in this work context #{index + 1}?",
                "choices": [],
                "correct_answer": "cuoc hop",
                "target_vocab": ["meeting"],
                "rubric": {
                    "acceptable_answers": ["cuoc hop", "buoi hop"],
                    "explanation_vi": "Meeting o day co nghia la cuoc hop.",
                },
            }
        )
    return json.dumps({"questions": questions})


class _FakePersonalizationContext:
    def prompt_summary(self, *, max_items: int = 12) -> str:
        _ = max_items
        return "- Work context: learner joins client-facing sales meetings.\n- Preference: likes short practical tasks."


class _ValidQuestionLLM:
    enabled = True
    last_provider = "test"

    def __init__(self) -> None:
        self.messages = []

    async def generate_chat_completion(self, messages, **kwargs):
        _ = kwargs
        self.messages.append(messages)
        return _llm_question_payload()


class _InvalidQuestionLLM:
    enabled = True
    last_provider = "test"

    def __init__(self) -> None:
        self.calls = 0

    async def generate_chat_completion(self, messages, **kwargs):
        _ = messages, kwargs
        self.calls += 1
        return "not valid json"


def test_lesson_question_generator_returns_fixed_twelve_question_plan():
    practice_set = asyncio.run(create_lesson_questions(_learner(), _lesson(), _vocabulary()))

    assert practice_set.total_questions == 12
    assert practice_set.question_counts == {
        "multiple_choice_abcd": 5,
        "write_sentence": 3,
        "vocab_answer": 2,
        "quick_definition": 2,
    }
    assert Counter(question.type for question in practice_set.questions) == practice_set.question_counts


def test_lesson_question_generator_uses_deterministic_ids_and_valid_abcd_choices():
    practice_set = asyncio.run(create_lesson_questions(_learner(), _lesson(), _vocabulary()))

    assert practice_set.practice_set_id == "A2_present_simple_be-practice-v1"
    assert [question.question_id for question in practice_set.questions] == [
        f"A2_present_simple_be-q{index:03d}" for index in range(1, 13)
    ]

    multiple_choice_questions = [
        question for question in practice_set.questions if question.type == "multiple_choice_abcd"
    ]
    assert len(multiple_choice_questions) == DEFAULT_QUESTION_PLAN.multiple_choice_abcd
    for question in multiple_choice_questions:
        assert [choice.key for choice in question.choices] == ["A", "B", "C", "D"]
        assert question.correct_answer in {"A", "B", "C", "D"}


def test_lesson_question_generator_accepts_injected_practice_set_id_factory():
    plan = QuestionPlan(practice_set_id_factory=lambda lesson: f"{lesson.lesson_id}-test-run")

    practice_set = asyncio.run(create_lesson_questions(_learner(), _lesson(), _vocabulary(), plan))

    assert practice_set.practice_set_id == "A2_present_simple_be-test-run"


def test_lesson_question_schema_rejects_multiple_choice_without_abcd_keys():
    with pytest.raises(ValidationError):
        LessonQuestion(
            question_id="A2_present_simple_be-q001",
            lesson_id="A2_present_simple_be",
            type="multiple_choice_abcd",
            prompt="Choose the correct sentence.",
            choices=[
                LessonQuestionChoice(key="A", text="I am ready."),
                LessonQuestionChoice(key="B", text="I is ready."),
                LessonQuestionChoice(key="C", text="I are ready."),
                LessonQuestionChoice(key="E", text="I be ready."),
            ],
            correct_answer="A",
            difficulty="A2",
        )


def test_practice_set_schema_rejects_inconsistent_question_counts():
    question = LessonQuestion(
        question_id="A2_present_simple_be-q001",
        lesson_id="A2_present_simple_be",
        type="quick_definition",
        prompt="What does 'assistant' mean?",
        correct_answer="tro ly",
        target_vocab=["assistant"],
        difficulty="A2",
    )

    with pytest.raises(ValidationError):
        LessonPracticeSet(
            practice_set_id="A2_present_simple_be-practice-v1",
            lesson_id="A2_present_simple_be",
            total_questions=12,
            question_counts={"quick_definition": 12},
            questions=[question],
        )


def test_lesson_question_generator_falls_back_when_vocabulary_and_metadata_are_sparse():
    sparse_lesson = LessonContent(
        lesson_id="A2_sparse_lesson",
        title="Sparse Lesson",
        cefr_level="A2",
        lesson_path="data/curriculum_skeleton/A2/99_A2_sparse_lesson.md",
        metadata_path=None,
        order_index=99,
        metadata={},
        markdown="# Sparse Lesson\n\nShort lesson text.",
    )

    practice_set = asyncio.run(create_lesson_questions(_learner(), sparse_lesson, []))

    assert practice_set.total_questions == 12
    assert practice_set.lesson_id == "A2_sparse_lesson"
    assert all(question.prompt for question in practice_set.questions)
    assert all(question.target_vocab for question in practice_set.questions if question.type != "multiple_choice_abcd")


def test_lesson_question_generator_prioritizes_personal_errors_in_multiple_choice():
    practice_set = asyncio.run(
        create_lesson_questions(
            _learner(),
            _lesson(),
            _vocabulary(),
            personal_errors=[
                {
                    "error_type": "grammar",
                    "error_pattern": "then -> than",
                    "corrected_text": "This option is better than the previous one.",
                    "original_text": "This option is better then the previous one.",
                    "explanation_vi": "Dung than khi so sanh.",
                }
            ],
        )
    )

    first = practice_set.questions[0]
    assert first.type == "multiple_choice_abcd"
    assert first.choices[0].text == "This option is better than the previous one."
    assert any(choice.text == "This option is better then the previous one." for choice in first.choices)
    assert first.rubric.explanation_vi == "Dung than khi so sanh."


def test_lesson_question_generator_uses_llm_with_personalized_context(monkeypatch):
    fake_llm = _ValidQuestionLLM()
    monkeypatch.setattr(generator_module, "get_llm_client", lambda: fake_llm)
    monkeypatch.setattr(generator_module, "load_personalization_context", lambda user_id: _FakePersonalizationContext())

    practice_set = asyncio.run(
        create_lesson_questions(
            _learner(),
            _lesson(),
            _vocabulary(),
            personal_errors=[
                {
                    "error_pattern": "then -> than",
                    "original_text": "better then",
                    "corrected_text": "better than",
                    "explanation_vi": "Dung than khi so sanh.",
                }
            ],
        )
    )

    assert practice_set.total_questions == 12
    assert practice_set.questions[0].prompt == "Choose the best sentence for the learner's sales meeting scenario #1."
    assert fake_llm.messages
    user_prompt = fake_llm.messages[0][-1]["content"]
    assert "learning_goals: ['daily work communication']" in user_prompt
    assert "then -> than" in user_prompt
    assert "client-facing sales meetings" in user_prompt


def test_lesson_question_generator_falls_back_when_llm_returns_invalid_json(monkeypatch):
    fake_llm = _InvalidQuestionLLM()
    monkeypatch.setattr(generator_module, "get_llm_client", lambda: fake_llm)
    monkeypatch.setattr(generator_module, "load_personalization_context", lambda user_id: _FakePersonalizationContext())

    practice_set = asyncio.run(create_lesson_questions(_learner(), _lesson(), _vocabulary()))

    assert fake_llm.calls == 2
    assert practice_set.practice_set_id == "A2_present_simple_be-practice-v1"
    assert practice_set.questions[0].prompt == "Choose the correct sentence for this lesson: Present Simple with to be."
