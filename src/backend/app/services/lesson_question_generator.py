from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping, Sequence

from app.models.processed_dataset_schemas import (
    LearnerProfile,
    LessonContent,
    LessonPracticeSet,
    LessonQuestion,
    LessonQuestionChoice,
    LessonQuestionRubric,
    LessonVocabularyItem,
)
from app.services.personalization import load_personalization_context
from app.services.system_prompt import prepend_persona
from app.core.config import get_settings
from app.utils.llm import get_llm_client


logger = logging.getLogger(__name__)


QUESTION_TYPES = ("multiple_choice_abcd", "write_sentence", "vocab_answer", "quick_definition")


@dataclass(frozen=True)
class QuestionPlan:
    multiple_choice_abcd: int = 5
    write_sentence: int = 3
    vocab_answer: int = 2
    quick_definition: int = 2
    practice_set_id_factory: Callable[[LessonContent], str] | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "multiple_choice_abcd": self.multiple_choice_abcd,
            "write_sentence": self.write_sentence,
            "vocab_answer": self.vocab_answer,
            "quick_definition": self.quick_definition,
        }

    @property
    def total_questions(self) -> int:
        return sum(self.counts.values())


DEFAULT_QUESTION_PLAN = QuestionPlan()


@dataclass(frozen=True)
class _VocabularySeed:
    word: str
    pos: str
    definition_vi: str
    example: str


async def create_lesson_questions(
    learner: LearnerProfile,
    lesson: LessonContent,
    vocabulary: list[LessonVocabularyItem],
    question_plan: QuestionPlan = DEFAULT_QUESTION_PLAN,
    personal_errors: Sequence[Mapping[str, object]] | None = None,
) -> LessonPracticeSet:
    """Create a deterministic, schema-validated practice set for one lesson.

    This Phase 2 implementation is intentionally replaceable: a future LLM path
    can build the same raw question payloads, then rely on the same Pydantic
    validation before returning a LessonPracticeSet.
    """

    _validate_question_plan(question_plan)
    llm_practice_set = await _create_lesson_questions_with_llm(
        learner,
        lesson,
        vocabulary,
        question_plan,
        personal_errors=personal_errors,
    )
    if llm_practice_set is not None:
        return llm_practice_set

    builder = _FallbackQuestionBuilder(learner, lesson, vocabulary, question_plan, personal_errors)
    questions = builder.build()
    question_counts = dict(Counter(question.type for question in questions))

    practice_set = LessonPracticeSet(
        practice_set_id=_practice_set_id(lesson, question_plan),
        lesson_id=lesson.lesson_id,
        total_questions=len(questions),
        question_counts={question_type: question_counts[question_type] for question_type in QUESTION_TYPES},
        questions=questions,
    )
    return LessonPracticeSet.model_validate(practice_set.model_dump())


async def _create_lesson_questions_with_llm(
    learner: LearnerProfile,
    lesson: LessonContent,
    vocabulary: Sequence[LessonVocabularyItem],
    question_plan: QuestionPlan,
    *,
    personal_errors: Sequence[Mapping[str, object]] | None = None,
) -> LessonPracticeSet | None:
    settings = get_settings()
    if not settings.PRACTICE_QUESTION_LLM_ENABLED:
        return None

    llm = get_llm_client()
    if not getattr(llm, "enabled", False):
        return None

    prompt_messages = _build_lesson_question_prompt(
        learner,
        lesson,
        vocabulary,
        question_plan,
        personal_errors=personal_errors,
    )
    max_tokens = 2600

    try:
        raw = await llm.generate_chat_completion(prompt_messages, temperature=0.2, max_tokens=max_tokens)
    except Exception:
        logger.exception("lesson_question_generator: llm question generation failed for lesson_id=%s", lesson.lesson_id)
        return None

    parsed = _extract_json_object(raw)
    if parsed is None:
        retry_messages = _build_lesson_question_retry_prompt(prompt_messages, raw)
        try:
            retry_raw = await llm.generate_chat_completion(retry_messages, temperature=0.0, max_tokens=max_tokens)
        except Exception:
            logger.exception("lesson_question_generator: llm retry failed for lesson_id=%s", lesson.lesson_id)
            return None
        parsed = _extract_json_object(retry_raw)
        if parsed is None:
            logger.warning(
                "lesson_question_generator: llm returned non-json lesson_id=%s provider=%s",
                lesson.lesson_id,
                getattr(llm, "last_provider", "unknown"),
            )
            return None

    try:
        return _practice_set_from_llm_payload(parsed, learner, lesson, question_plan)
    except Exception:
        logger.exception("lesson_question_generator: invalid llm practice payload for lesson_id=%s", lesson.lesson_id)
        return None


def _build_lesson_question_prompt(
    learner: LearnerProfile,
    lesson: LessonContent,
    vocabulary: Sequence[LessonVocabularyItem],
    question_plan: QuestionPlan,
    *,
    personal_errors: Sequence[Mapping[str, object]] | None = None,
) -> list[dict[str, str]]:
    personalization = load_personalization_context(learner.user_id)
    vocab_rows = "\n".join(
        f"- {item.word} | {item.pos} | {item.definition_vi} | example: {item.example} | source: {item.source}"
        for item in vocabulary[:8]
    )
    lesson_examples = "\n".join(f"- {example}" for example in _lesson_examples(lesson.markdown)[:6])
    common_errors = "\n".join(
        f"- wrong: {_as_text(item.get('wrong'))} | correct: {_as_text(item.get('correct'))} | hint_vi: {_as_text(item.get('hint'))}"
        for item in _common_errors(lesson.metadata)[:6]
    )
    recent_errors = "\n".join(
        (
            f"- pattern: {_as_text(item.get('error_pattern'))} | original: {_as_text(item.get('original_text'))} "
            f"| corrected: {_as_text(item.get('corrected_text'))} | note_vi: {_as_text(item.get('explanation_vi'))}"
        )
        for item in _personal_errors(personal_errors or [])
    )
    recommended_vocab = ", ".join(_metadata_vocab_words(lesson.metadata)[:8]) or "- none"
    markdown_preview = lesson.markdown.strip()[:5000]

    system_prompt = (
        "Create a personalized English lesson practice set for a Vietnamese learner. "
        "Return ONLY one valid JSON object. Do not use markdown fences or extra commentary.\n"
        "The JSON shape must be: {\"questions\": [ ... ]}.\n"
        "Return exactly 12 questions in this exact order and type distribution:\n"
        "- 5 multiple_choice_abcd\n"
        "- 3 write_sentence\n"
        "- 2 vocab_answer\n"
        "- 2 quick_definition\n"
        "Each question object must contain keys: type, prompt, choices, correct_answer, target_vocab, rubric.\n"
        "For multiple_choice_abcd: choices must be exactly four objects with keys A, B, C, D, and correct_answer must be one of A/B/C/D.\n"
        "For write_sentence: choices must be [], correct_answer should be the main target word or phrase, "
        "and rubric should include must_include, target_structure, min_words, explanation_vi.\n"
        "For vocab_answer and quick_definition: choices must be [], target_vocab should list the target word, "
        "and rubric should include acceptable_answers and explanation_vi.\n"
        "Personalize the questions using learner profile, onboarding details, workplace context, goals, and recent recurring errors. "
        "Use recent recurring errors only when relevant; do not force them into every question.\n"
        "All questions must stay inside the lesson scope. Keep difficulty aligned to the lesson CEFR level. "
        "Prefer realistic workplace English examples when the learner profile suggests that context."
    )
    user_prompt = (
        f"Learner profile:\n"
        f"- user_id: {learner.user_id}\n"
        f"- cefr_level: {learner.cefr_level}\n"
        f"- industry: {learner.industry}\n"
        f"- learning_goals: {learner.learning_goals}\n"
        f"- weak_points: {learner.weak_points}\n"
        f"- preferred_language: {learner.preferred_language}\n\n"
        f"Personalization summary from memory:\n{personalization.prompt_summary() or '- none'}\n\n"
        f"Recent recurring errors:\n{recent_errors or '- none'}\n\n"
        f"Lesson info:\n"
        f"- lesson_id: {lesson.lesson_id}\n"
        f"- title: {lesson.title}\n"
        f"- cefr_level: {lesson.cefr_level}\n"
        f"- skill_type: {_as_text(lesson.metadata.get('skill_type')) or lesson.skill_type or 'unknown'}\n"
        f"- recommended_vocab: {recommended_vocab}\n\n"
        f"Lesson common errors:\n{common_errors or '- none'}\n\n"
        f"Lesson examples:\n{lesson_examples or '- none'}\n\n"
        f"Vocabulary candidates:\n{vocab_rows or '- none'}\n\n"
        f"Question plan counts: {question_plan.counts}\n\n"
        f"Lesson markdown excerpt:\n{markdown_preview}\n"
    )
    return prepend_persona(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
    )


def _build_lesson_question_retry_prompt(
    messages: list[dict[str, str]],
    invalid_response: str,
) -> list[dict[str, str]]:
    return [
        *messages,
        {
            "role": "user",
            "content": (
                "Your previous response could not be parsed as a complete JSON object. "
                "Re-emit ONLY one valid JSON object with shape {\"questions\": [...]} and no extra text.\n\n"
                f"Previous invalid response:\n{invalid_response[:1600]}"
            ),
        },
    ]


def _practice_set_from_llm_payload(
    payload: Mapping[str, Any],
    learner: LearnerProfile,
    lesson: LessonContent,
    question_plan: QuestionPlan,
) -> LessonPracticeSet:
    raw_questions = payload.get("questions")
    if not isinstance(raw_questions, list):
        raise ValueError("LLM payload must include a questions list")

    questions = [
        _question_from_llm_draft(index, raw_question, learner, lesson)
        for index, raw_question in enumerate(raw_questions, start=1)
    ]
    question_counts = dict(Counter(question.type for question in questions))
    if len(questions) != question_plan.total_questions:
        raise ValueError("LLM question count does not match configured plan")
    if {question_type: question_counts.get(question_type, 0) for question_type in QUESTION_TYPES} != question_plan.counts:
        raise ValueError("LLM question type counts do not match configured plan")
    practice_set = LessonPracticeSet(
        practice_set_id=_practice_set_id(lesson, question_plan),
        lesson_id=lesson.lesson_id,
        total_questions=len(questions),
        question_counts={question_type: question_counts.get(question_type, 0) for question_type in QUESTION_TYPES},
        questions=questions,
    )
    _validate_question_plan(question_plan)
    return LessonPracticeSet.model_validate(practice_set.model_dump())


def _question_from_llm_draft(
    index: int,
    raw_question: Any,
    learner: LearnerProfile,
    lesson: LessonContent,
) -> LessonQuestion:
    if not isinstance(raw_question, Mapping):
        raise ValueError("Each LLM question must be an object")

    question_type = _as_text(raw_question.get("type"))
    prompt = _as_text(raw_question.get("prompt"))
    correct_answer = _as_text(raw_question.get("correct_answer"))
    target_vocab = _normalize_string_list(raw_question.get("target_vocab"))
    rubric = _rubric_from_llm(raw_question.get("rubric"), question_type, correct_answer, target_vocab, learner, lesson)
    choices = _choices_from_llm(raw_question.get("choices"), question_type)

    return LessonQuestion(
        question_id=f"{lesson.lesson_id}-q{index:03d}",
        lesson_id=lesson.lesson_id,
        type=question_type,  # type: ignore[arg-type]
        prompt=prompt,
        choices=choices,
        correct_answer=correct_answer,
        target_vocab=target_vocab,
        rubric=rubric,
        difficulty=lesson.cefr_level,
    )


def _rubric_from_llm(
    raw_rubric: Any,
    question_type: str,
    correct_answer: str,
    target_vocab: Sequence[str],
    learner: LearnerProfile,
    lesson: LessonContent,
) -> LessonQuestionRubric:
    data = raw_rubric if isinstance(raw_rubric, Mapping) else {}
    explanation_vi = _as_text(data.get("explanation_vi"))
    acceptable_answers = _normalize_string_list(data.get("acceptable_answers"))
    must_include = _normalize_string_list(data.get("must_include"))
    target_structure = _as_text(data.get("target_structure")) or _target_structure(lesson)
    min_words = _as_int(data.get("min_words"))

    if question_type == "multiple_choice_abcd":
        acceptable_answers = [correct_answer] if correct_answer else []
    elif question_type == "write_sentence":
        if not must_include and target_vocab:
            must_include = [target_vocab[0]]
        if min_words is None:
            min_words = 4
        if not explanation_vi:
            explanation_vi = (
                "Cau can dung dung tu/cau truc trong bai va phu hop voi muc tieu hoc tap "
                f"trong boi canh {learner.industry}."
            )
    else:
        if correct_answer and correct_answer not in acceptable_answers:
            acceptable_answers = [*acceptable_answers, correct_answer]
        if not explanation_vi and target_vocab:
            explanation_vi = f"Dap an can phu hop voi tu/cum tu '{target_vocab[0]}' trong bai hoc."

    return LessonQuestionRubric(
        must_include=must_include,
        acceptable_answers=acceptable_answers,
        target_structure=target_structure if question_type == "write_sentence" else None,
        min_words=min_words if question_type == "write_sentence" else None,
        explanation_vi=explanation_vi or None,
    )


def _choices_from_llm(raw_choices: Any, question_type: str) -> list[LessonQuestionChoice]:
    if question_type != "multiple_choice_abcd":
        return []

    if not isinstance(raw_choices, list) or len(raw_choices) != 4:
        raise ValueError("multiple_choice_abcd requires exactly four choices")

    normalized: list[LessonQuestionChoice] = []
    for fallback_key, item in zip(("A", "B", "C", "D"), raw_choices):
        if isinstance(item, Mapping):
            key = _as_text(item.get("key")) or fallback_key
            text = _as_text(item.get("text"))
        else:
            key = fallback_key
            text = _as_text(item)
        normalized.append(LessonQuestionChoice(key=key, text=text))
    return normalized


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, Sequence):
        return []
    result: list[str] = []
    for item in value:
        text = _as_text(item)
        if text:
            result.append(text)
    return _dedupe_keep_order(result)


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = text.strip()
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


class _FallbackQuestionBuilder:
    def __init__(
        self,
        learner: LearnerProfile,
        lesson: LessonContent,
        vocabulary: Sequence[LessonVocabularyItem],
        question_plan: QuestionPlan,
        personal_errors: Sequence[Mapping[str, object]] | None = None,
    ) -> None:
        self.learner = learner
        self.lesson = lesson
        self.question_plan = question_plan
        self.vocabulary = _vocabulary_seeds(lesson, vocabulary)
        self.examples = _lesson_examples(lesson.markdown)
        self.personal_errors = _personal_errors(personal_errors or [])
        self.common_errors = _common_errors(lesson.metadata)
        self._next_question_number = 1

    def build(self) -> list[LessonQuestion]:
        questions: list[LessonQuestion] = []
        questions.extend(self._multiple_choice_questions())
        questions.extend(self._write_sentence_questions())
        questions.extend(self._vocab_answer_questions())
        questions.extend(self._quick_definition_questions())
        return questions

    def _multiple_choice_questions(self) -> list[LessonQuestion]:
        questions: list[LessonQuestion] = []
        for index in range(self.question_plan.multiple_choice_abcd):
            correct, distractors, explanation = self._multiple_choice_content(index)
            questions.append(
                self._question(
                    type="multiple_choice_abcd",
                    prompt=f"Choose the correct sentence for this lesson: {self.lesson.title}.",
                    choices=_abcd_choices(correct, distractors),
                    correct_answer="A",
                    rubric=LessonQuestionRubric(
                        acceptable_answers=["A"],
                        explanation_vi=explanation,
                    ),
                )
            )
        return questions

    def _write_sentence_questions(self) -> list[LessonQuestion]:
        questions: list[LessonQuestion] = []
        goal = _first_or_default(self.learner.learning_goals, "daily work communication")
        for index in range(self.question_plan.write_sentence):
            vocab = self.vocabulary[index % len(self.vocabulary)]
            questions.append(
                self._question(
                    type="write_sentence",
                    prompt=(
                        f"Write one clear sentence for {goal} using '{vocab.word}' "
                        f"and the lesson pattern."
                    ),
                    correct_answer=vocab.word,
                    target_vocab=[vocab.word],
                    rubric=LessonQuestionRubric(
                        must_include=[vocab.word],
                        target_structure=_target_structure(self.lesson),
                        min_words=4,
                        explanation_vi=(
                            "Cau can dung dung tu/cau truc trong bai va co y nghia ro rang "
                            f"trong ngu canh {self.learner.industry}."
                        ),
                    ),
                )
            )
        return questions

    def _vocab_answer_questions(self) -> list[LessonQuestion]:
        questions: list[LessonQuestion] = []
        offset = self.question_plan.write_sentence
        for index in range(self.question_plan.vocab_answer):
            vocab = self.vocabulary[(offset + index) % len(self.vocabulary)]
            questions.append(
                self._question(
                    type="vocab_answer",
                    prompt=_blanked_example(vocab),
                    correct_answer=vocab.word,
                    target_vocab=[vocab.word],
                    rubric=LessonQuestionRubric(
                        acceptable_answers=[vocab.word],
                        explanation_vi=f"Dap an can dung tu '{vocab.word}' theo ngu canh bai hoc.",
                    ),
                )
            )
        return questions

    def _quick_definition_questions(self) -> list[LessonQuestion]:
        questions: list[LessonQuestion] = []
        offset = self.question_plan.write_sentence + self.question_plan.vocab_answer
        for index in range(self.question_plan.quick_definition):
            vocab = self.vocabulary[(offset + index) % len(self.vocabulary)]
            questions.append(
                self._question(
                    type="quick_definition",
                    prompt=f"What does '{vocab.word}' mean in this lesson context?",
                    correct_answer=vocab.definition_vi,
                    target_vocab=[vocab.word],
                    rubric=LessonQuestionRubric(
                        acceptable_answers=_acceptable_definitions(vocab.definition_vi),
                        explanation_vi=f"'{vocab.word}' trong bai nay co nghia la: {vocab.definition_vi}.",
                    ),
                )
            )
        return questions

    def _multiple_choice_content(self, index: int) -> tuple[str, list[str], str]:
        if index < len(self.personal_errors):
            error = self.personal_errors[index]
            correct, wrong, hint = _personal_error_choice_content(error, index)
            distractors = [wrong, *_fallback_distractors(correct, index)]
            return correct, _dedupe_keep_order(distractors, exclude={correct})[:3], hint

        common_index = index - len(self.personal_errors)
        if common_index < len(self.common_errors):
            error = self.common_errors[common_index]
            correct = _as_text(error.get("correct")) or _fallback_correct_sentence(index)
            wrong = _as_text(error.get("wrong")) or _fallback_wrong_sentence(index)
            hint = _as_text(error.get("hint")) or "Hay chon cau dung theo quy tac trong bai."
            distractors = [wrong, *_fallback_distractors(correct, index)]
            return correct, _dedupe_keep_order(distractors, exclude={correct})[:3], hint

        correct = _first_or_default(self.examples[index : index + 1], _fallback_correct_sentence(index))
        distractors = _fallback_distractors(correct, index)
        return correct, distractors, "Hay chon cau dung theo cau truc va vi du trong bai."

    def _question(self, **kwargs) -> LessonQuestion:
        question = LessonQuestion(
            question_id=f"{self.lesson.lesson_id}-q{self._next_question_number:03d}",
            lesson_id=self.lesson.lesson_id,
            difficulty=self.lesson.cefr_level,
            **kwargs,
        )
        self._next_question_number += 1
        return question


def _validate_question_plan(question_plan: QuestionPlan) -> None:
    if question_plan.total_questions != 12:
        raise ValueError("Lesson practice sets must contain exactly 12 questions")
    for question_type, count in question_plan.counts.items():
        if count < 0:
            raise ValueError(f"{question_type} count must not be negative")


def _practice_set_id(lesson: LessonContent, question_plan: QuestionPlan) -> str:
    if question_plan.practice_set_id_factory is not None:
        return question_plan.practice_set_id_factory(lesson)
    return f"{lesson.lesson_id}-practice-v1"


def _vocabulary_seeds(
    lesson: LessonContent,
    vocabulary: Sequence[LessonVocabularyItem],
) -> list[_VocabularySeed]:
    seeds = [
        _VocabularySeed(
            word=item.word.strip(),
            pos=item.pos.strip() or "unknown",
            definition_vi=item.definition_vi.strip() or "tu vung trong bai hoc",
            example=item.example.strip() or f"{item.word.strip()} appears in this lesson.",
        )
        for item in vocabulary
        if item.word.strip()
    ]

    for word in _metadata_vocab_words(lesson.metadata):
        if word.lower() not in {seed.word.lower() for seed in seeds}:
            seeds.append(
                _VocabularySeed(
                    word=word,
                    pos="unknown",
                    definition_vi=f"tu/cum tu '{word}' trong bai hoc",
                    example=f"The lesson uses {word} in a workplace context.",
                )
            )

    for word in _markdown_candidate_words(lesson.markdown):
        if len(seeds) >= 5:
            break
        if word.lower() not in {seed.word.lower() for seed in seeds}:
            seeds.append(
                _VocabularySeed(
                    word=word,
                    pos="unknown",
                    definition_vi=f"tu/cum tu '{word}' trong bai hoc",
                    example=f"{word} is useful for this lesson.",
                )
            )

    fallback_words = ("am", "is", "are", "not", "meeting")
    for word in fallback_words:
        if len(seeds) >= 5:
            break
        if word.lower() not in {seed.word.lower() for seed in seeds}:
            seeds.append(
                _VocabularySeed(
                    word=word,
                    pos="unknown",
                    definition_vi=f"tu/cum tu '{word}' trong bai hoc",
                    example=f"I use {word} in a simple work sentence.",
                )
            )

    return seeds


def _metadata_vocab_words(metadata: Mapping[str, object]) -> list[str]:
    raw_words = metadata.get("recommended_vocab") or []
    if not isinstance(raw_words, list):
        return []

    words: list[str] = []
    for item in raw_words:
        if isinstance(item, str):
            words.append(item.strip())
        elif isinstance(item, Mapping):
            word = item.get("word") or item.get("term") or item.get("text")
            if isinstance(word, str):
                words.append(word.strip())
    return [word for word in words if word]


def _markdown_candidate_words(markdown: str) -> list[str]:
    candidates = re.findall(r"`([^`\n]{2,40})`|\*\*([^*\n]{2,40})\*\*", markdown)
    words: list[str] = []
    for backtick, bold in candidates:
        value = (backtick or bold).strip()
        if re.fullmatch(r"[A-Za-z][A-Za-z '-]{1,38}", value):
            words.append(value)
    return _dedupe_keep_order(words)


def _lesson_examples(markdown: str) -> list[str]:
    inline_examples = re.findall(r"`([^`\n.!?]{3,120}[.!?])`", markdown)
    examples = [example.strip() for example in inline_examples if " " in example]
    return _dedupe_keep_order(examples)


def _common_errors(metadata: Mapping[str, object]) -> list[Mapping[str, object]]:
    raw_errors = metadata.get("common_errors") or []
    if not isinstance(raw_errors, list):
        return []
    return [error for error in raw_errors if isinstance(error, Mapping)]


def _personal_errors(items: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    result: list[Mapping[str, object]] = []
    for item in items:
        pattern = _as_text(item.get("error_pattern"))
        if not pattern:
            continue
        result.append(item)
        if len(result) >= 3:
            break
    return result


def _personal_error_choice_content(error: Mapping[str, object], index: int) -> tuple[str, str, str]:
    original = _as_text(error.get("original_text"))
    corrected = _as_text(error.get("corrected_text"))
    pattern = _as_text(error.get("error_pattern"))
    explanation = _as_text(error.get("explanation_vi"))

    if original and corrected and original.lower() != corrected.lower():
        correct = corrected
        wrong = original
    else:
        wrong_token, correct_token = _parse_error_pattern(pattern)
        correct, wrong = _sentence_pair_for_tokens(wrong_token, correct_token, index)

    hint = explanation or f"On tap loi ca nhan gan day: {pattern}."
    return correct, wrong, hint


def _parse_error_pattern(pattern: str) -> tuple[str, str]:
    if "->" not in pattern:
        return "wrong", "correct"
    wrong, correct = pattern.split("->", 1)
    return wrong.strip() or "wrong", correct.strip() or "correct"


def _sentence_pair_for_tokens(wrong: str, correct: str, index: int) -> tuple[str, str]:
    if wrong.lower() == "then" and correct.lower() == "than":
        return "This option is better than the previous one.", "This option is better then the previous one."
    if wrong.lower() == "than" and correct.lower() == "then":
        return "We finished the review, then sent the update.", "We finished the review, than sent the update."
    if wrong and correct and re.fullmatch(r"[A-Za-z']{1,24}", wrong) and re.fullmatch(r"[A-Za-z']{1,24}", correct):
        return (
            f"I should use {correct} in this sentence.",
            f"I should use {wrong} in this sentence.",
        )
    return _fallback_correct_sentence(index), _fallback_wrong_sentence(index)


def _target_structure(lesson: LessonContent) -> str:
    skill_type = _as_text(lesson.metadata.get("skill_type"))
    if skill_type:
        return f"{skill_type}: {lesson.title}"
    return lesson.title


def _blanked_example(vocab: _VocabularySeed) -> str:
    escaped_word = re.escape(vocab.word)
    blanked, replacements = re.subn(
        rf"\b{escaped_word}\b",
        "___",
        vocab.example,
        count=1,
        flags=re.IGNORECASE,
    )
    if replacements == 0:
        blanked = f"I use ___ in this lesson context. ({vocab.definition_vi})"
    return f"Complete the sentence: {blanked}"


def _acceptable_definitions(definition_vi: str) -> list[str]:
    answers = [definition_vi]
    for separator in (",", ";"):
        if separator in definition_vi:
            answers.extend(part.strip() for part in definition_vi.split(separator))
    return _dedupe_keep_order(answer for answer in answers if answer)


def _abcd_choices(correct: str, distractors: Sequence[str]) -> list[LessonQuestionChoice]:
    choices = [correct, *_pad_distractors(correct, distractors)]
    return [LessonQuestionChoice(key=key, text=text) for key, text in zip(("A", "B", "C", "D"), choices)]


def _pad_distractors(correct: str, distractors: Sequence[str]) -> list[str]:
    padded = _dedupe_keep_order(distractors, exclude={correct})
    for fallback in _fallback_distractors(correct, 0):
        if len(padded) >= 3:
            break
        if fallback != correct and fallback not in padded:
            padded.append(fallback)
    while len(padded) < 3:
        padded.append(f"{correct} (incorrect option {len(padded) + 1})")
    return padded[:3]


def _fallback_correct_sentence(index: int) -> str:
    sentences = (
        "I am a project assistant.",
        "She is ready for the client meeting.",
        "They are in the meeting room.",
        "The report is not ready yet.",
        "Are you available after lunch?",
    )
    return sentences[index % len(sentences)]


def _fallback_wrong_sentence(index: int) -> str:
    sentences = (
        "I is a project assistant.",
        "She are ready for the client meeting.",
        "They is in the meeting room.",
        "The report is no ready yet.",
        "You is available after lunch?",
    )
    return sentences[index % len(sentences)]


def _fallback_distractors(correct: str, index: int) -> list[str]:
    transformations = [
        (r"\bam\b", "is"),
        (r"\bis\b", "are"),
        (r"\bare\b", "is"),
        (r"\bnot\b", "no"),
    ]
    distractors: list[str] = []
    for pattern, replacement in transformations:
        candidate, replacements = re.subn(pattern, replacement, correct, count=1, flags=re.IGNORECASE)
        if replacements:
            distractors.append(candidate)

    generic = (
        _fallback_wrong_sentence(index),
        "I be ready for the meeting.",
        "She am in the office.",
        "They be available now.",
    )
    distractors.extend(generic)
    return _dedupe_keep_order(distractors, exclude={correct})[:3]


def _first_or_default(values: Sequence[str], default: str) -> str:
    return values[0] if values else default


def _as_text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _dedupe_keep_order(values: Iterable[str], exclude: set[str] | None = None) -> list[str]:
    excluded = exclude or set()
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in excluded or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
