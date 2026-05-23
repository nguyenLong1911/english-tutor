from __future__ import annotations

import json
import logging
import re
import uuid
from datetime import datetime
from typing import Protocol

from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from ...core.database import SessionLocal
from ...models.lesson_progress import LessonProgress
from ...models.schemas import (
    FlashcardBack,
    LearnerProfile,
    LearningState,
    LearningTransition,
    LessonFlashcard,
    LessonPracticeSet,
    LessonQuestion,
    LessonSummary,
    UIDirective,
)
from ...models.user import User
from ...services.error_capture_service import capture_error_and_flashcard
from ...services.learner_profile_provider import get_learner_profile
from ...services.lesson_catalog import get_lesson, list_lessons
from ...services.lesson_question_generator import create_lesson_questions
from ...services.lesson_vocabulary_provider import get_lesson_vocabulary
from ...services.personal_error_context import load_due_error_flashcards, load_personal_error_context


router = APIRouter(tags=["learning"])
logger = logging.getLogger(__name__)

PASS_THRESHOLD = 0.70
DEFAULT_USER_ID = "mock-user"


class LearningStartRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    lesson_id: str | None = None


class LearningUserRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID


class LearningAnswer(BaseModel):
    question_id: str
    answer: str = ""


class LearningSubmitRequest(BaseModel):
    user_id: str = DEFAULT_USER_ID
    practice_set_id: str
    answers: list[LearningAnswer] = Field(default_factory=list)


class LearningStore(Protocol):
    async def get_state(self, user_id: str) -> LearningState | None:
        ...

    async def save_state(self, user_id: str, state: LearningState) -> None:
        ...

    async def get_practice_set(self, user_id: str, practice_set_id: str) -> LessonPracticeSet | None:
        ...

    async def save_practice_set(self, user_id: str, practice_set: LessonPracticeSet) -> None:
        ...


class InMemoryLearningStore:
    """Session-friendly MVP store, shaped so Redis can replace it later."""

    def __init__(self) -> None:
        self._states: dict[str, LearningState] = {}
        self._practice_sets: dict[tuple[str, str], LessonPracticeSet] = {}

    async def get_state(self, user_id: str) -> LearningState | None:
        state = self._states.get(user_id)
        return state.model_copy(deep=True) if state is not None else None

    async def save_state(self, user_id: str, state: LearningState) -> None:
        self._states[user_id] = state.model_copy(deep=True)

    async def get_practice_set(self, user_id: str, practice_set_id: str) -> LessonPracticeSet | None:
        practice_set = self._practice_sets.get((user_id, practice_set_id))
        return practice_set.model_copy(deep=True) if practice_set is not None else None

    async def save_practice_set(self, user_id: str, practice_set: LessonPracticeSet) -> None:
        self._practice_sets[(user_id, practice_set.practice_set_id)] = practice_set.model_copy(deep=True)


class SqlLearningStore:
    """Postgres-backed lesson progress with in-memory fallback for non-UUID test users."""

    def __init__(self, fallback: LearningStore | None = None) -> None:
        self._fallback = fallback or InMemoryLearningStore()

    def _load_user_uuid(self, user_id: str):
        try:
            parsed = uuid.UUID(str(user_id))
        except (TypeError, ValueError, AttributeError):
            return None

        with SessionLocal() as db:
            if db.get(User, parsed) is None:
                return None
        return parsed

    def _row_to_state(self, rows: list[LessonProgress]) -> LearningState | None:
        if not rows:
            return None

        completed_lessons = [row.lesson_id for row in rows if row.status == "completed"]
        current = next((row for row in rows if row.is_current), None) or max(rows, key=lambda row: row.updated_at or row.started_at)

        transition = None
        if current.last_transition_to_step:
            transition = LearningTransition(
                from_step=current.last_transition_from_step or "NONE",
                to_step=current.last_transition_to_step,
                reason=current.last_transition_reason or "state_restored",
                created_at=current.last_transition_at or current.updated_at or current.started_at,
            )

        return LearningState(
            active_lesson_id=current.lesson_id,
            active_lesson_path=current.active_lesson_path,
            current_step=_status_to_step(current.status),
            practice_set_id=current.practice_set_id,
            practice_completed=bool(current.practice_completed),
            flashcards_completed=bool(current.flashcards_completed),
            completed_lessons=completed_lessons,
            last_transition=transition,
            latest_practice_result=current.latest_practice_result,
        )

    async def get_state(self, user_id: str) -> LearningState | None:
        user_uuid = self._load_user_uuid(user_id)
        if user_uuid is None:
            return await self._fallback.get_state(user_id)

        with SessionLocal() as db:
            rows = list(
                db.execute(
                    select(LessonProgress)
                    .where(LessonProgress.user_id == user_uuid)
                    .order_by(LessonProgress.updated_at.desc(), LessonProgress.started_at.desc())
                ).scalars()
            )
        return self._row_to_state(rows)

    async def save_state(self, user_id: str, state: LearningState) -> None:
        user_uuid = self._load_user_uuid(user_id)
        if user_uuid is None:
            await self._fallback.save_state(user_id, state)
            return
        if not state.active_lesson_id:
            return

        with SessionLocal() as db:
            db.execute(
                update(LessonProgress)
                .where(LessonProgress.user_id == user_uuid)
                .values(is_current=False, updated_at=datetime.utcnow())
            )
            row = db.get(LessonProgress, (user_uuid, state.active_lesson_id))
            if row is None:
                row = LessonProgress(
                    user_id=user_uuid,
                    lesson_id=state.active_lesson_id,
                    started_at=datetime.utcnow(),
                )
                db.add(row)

            practice_result = state.latest_practice_result or {}
            row.status = _step_to_status(state.current_step)
            row.is_current = True
            row.active_lesson_path = state.active_lesson_path
            row.practice_set_id = state.practice_set_id
            row.practice_completed = bool(state.practice_completed)
            row.flashcards_completed = bool(state.flashcards_completed)
            row.latest_practice_result = practice_result or None
            row.latest_score = practice_result.get("score")
            row.latest_total = practice_result.get("total")
            row.latest_accuracy = practice_result.get("accuracy")
            row.updated_at = datetime.utcnow()
            row.completed_at = row.updated_at if state.current_step == "LESSON_COMPLETE" else None
            if state.last_transition is not None:
                row.last_transition_from_step = state.last_transition.from_step
                row.last_transition_to_step = state.last_transition.to_step
                row.last_transition_reason = state.last_transition.reason
                row.last_transition_at = state.last_transition.created_at
            db.commit()

    async def get_practice_set(self, user_id: str, practice_set_id: str) -> LessonPracticeSet | None:
        return await self._fallback.get_practice_set(user_id, practice_set_id)

    async def save_practice_set(self, user_id: str, practice_set: LessonPracticeSet) -> None:
        await self._fallback.save_practice_set(user_id, practice_set)


learning_store: LearningStore = SqlLearningStore()


@router.get("/learning/current")
async def current_learning_state(user_id: str = Query(...)) -> dict:
    state = await learning_store.get_state(user_id) or LearningState()
    lesson = _active_lesson_payload(state)
    screen = _screen_for_step(state.current_step)

    response = _learning_response(
        agent_message=_message_for_current_state(state),
        state=state,
        lesson=lesson,
        ui_directive=UIDirective(
            screen=screen,
            action="OPEN" if state.active_lesson_id else "NONE",
            lesson_id=state.active_lesson_id,
            practice_set_id=state.practice_set_id,
            reason="current_state",
        ),
        suggested_actions=_suggested_actions_for_step(state.current_step),
    )
    _log_frontend_payload("learning.current.lesson", _lesson_log_summary(response))
    return response


@router.post("/learning/start")
async def start_learning(payload: LearningStartRequest) -> dict:
    learner = get_learner_profile(payload.user_id)
    existing_state = await learning_store.get_state(payload.user_id)
    lesson_id = payload.lesson_id

    if lesson_id is None and existing_state and _can_resume(existing_state):
        lesson_id = existing_state.active_lesson_id

    if lesson_id is None:
        lesson_id = _first_incomplete_lesson_id(learner, existing_state)

    lesson = _require_lesson(lesson_id)
    state = _state_for_lesson(existing_state or LearningState(), lesson, "LESSON_READING", "start_learning")
    await learning_store.save_state(payload.user_id, state)

    response = _learning_response(
        agent_message="Bạn đang đọc bài học này. Khi sẵn sàng, mình có thể mở tab Ôn tập cho bài này.",
        state=state,
        lesson=lesson.model_dump(mode="json"),
        ui_directive=UIDirective(
            screen="LESSON_READER",
            action="OPEN",
            lesson_id=lesson.lesson_id,
            reason="start_learning",
        ),
        suggested_actions=_reading_actions(),
    )
    _log_frontend_payload("learning.start.lesson", _lesson_log_summary(response))
    return response


@router.post("/learning/{lesson_id}/questions")
async def lesson_questions(
    lesson_id: str,
    payload: LearningUserRequest | None = Body(default=None),
    user_id: str | None = Query(default=None),
) -> dict:
    resolved_user_id = _resolve_user_id(payload, user_id)
    learner = get_learner_profile(resolved_user_id)
    lesson = _require_lesson(lesson_id)
    vocabulary = get_lesson_vocabulary(lesson_id, learner)
    personal_errors = _load_personal_errors_for_user(resolved_user_id)
    practice_set = await create_lesson_questions(
        learner,
        lesson,
        vocabulary,
        personal_errors=personal_errors,
    )

    state = await learning_store.get_state(resolved_user_id) or LearningState()
    state = _state_for_lesson(state, lesson, "PRACTICE", "practice_started")
    state.practice_set_id = practice_set.practice_set_id
    state.practice_completed = False
    await learning_store.save_practice_set(resolved_user_id, practice_set)
    await learning_store.save_state(resolved_user_id, state)

    response = {
        **practice_set.model_dump(mode="json"),
        "agent_message": "Đây là 12 câu ôn tập cho bài học này.",
        "learning_state": _state_payload(state),
        "ui_directive": UIDirective(
            screen="PRACTICE_RUNNER",
            action="OPEN",
            lesson_id=lesson_id,
            practice_set_id=practice_set.practice_set_id,
            reason="practice_started",
        ).model_dump(mode="json"),
        "suggested_actions": _practice_actions(),
    }
    _log_frontend_payload("learning.questions", _questions_log_summary(response))
    return response


@router.post("/learning/{lesson_id}/questions/submit")
async def submit_lesson_questions(lesson_id: str, payload: LearningSubmitRequest) -> dict:
    practice_set = await learning_store.get_practice_set(payload.user_id, payload.practice_set_id)
    if practice_set is None or practice_set.lesson_id != lesson_id:
        raise HTTPException(status_code=404, detail="practice set not found")

    answer_map = {answer.question_id: answer.answer for answer in payload.answers}
    feedback = [_grade_question(question, answer_map.get(question.question_id, "")) for question in practice_set.questions]
    score = sum(1 for item in feedback if item["correct"])
    total = practice_set.total_questions
    accuracy = score / total if total else 0.0
    passed = accuracy >= PASS_THRESHOLD
    next_step = "FLASHCARD" if passed else "PRACTICE"

    state = await learning_store.get_state(payload.user_id) or LearningState(active_lesson_id=lesson_id)
    lesson = _require_lesson(lesson_id)
    state = _state_for_lesson(state, lesson, "PRACTICE", "questions_submitted")
    state.practice_set_id = practice_set.practice_set_id
    state.practice_completed = passed
    state.latest_practice_result = {
        "score": score,
        "total": total,
        "accuracy": round(accuracy, 4),
        "passed": passed,
        "practice_set_id": practice_set.practice_set_id,
    }
    await learning_store.save_state(payload.user_id, state)
    _persist_lesson_practice_errors(
        user_id=payload.user_id,
        lesson_id=lesson_id,
        practice_set_id=practice_set.practice_set_id,
        practice_set=practice_set,
        answer_map=answer_map,
        feedback=feedback,
    )

    if passed:
        agent_message = (
            f"Chúc mừng, bạn hoàn thành bộ ôn tập với {score}/{total}. "
            "Bạn muốn sang flashcard, ôn tập lại, hay đọc lại bài?"
        )
    else:
        agent_message = (
            f"Bạn làm được {score}/{total}. Mình gợi ý ôn tập thêm một vòng ngắn "
            "trước khi sang flashcard."
        )

    return {
        "score": score,
        "total": total,
        "accuracy": round(accuracy, 4),
        "passed": passed,
        "feedback": feedback,
        "next_step": next_step,
        "agent_message": agent_message,
        "learning_state": _state_payload(state),
        "ui_directive": UIDirective(
            screen="PRACTICE_RESULT",
            action="OPEN",
            lesson_id=lesson_id,
            practice_set_id=practice_set.practice_set_id,
            reason="questions_submitted",
        ).model_dump(mode="json"),
        "suggested_actions": _practice_result_actions(),
    }


def _persist_lesson_practice_errors(
    *,
    user_id: str,
    lesson_id: str,
    practice_set_id: str,
    practice_set: LessonPracticeSet,
    answer_map: dict[str, str],
    feedback: list[dict],
) -> None:
    try:
        user_uuid = uuid.UUID(str(user_id))
    except ValueError:
        return

    feedback_by_id = {item["question_id"]: item for item in feedback}
    with SessionLocal() as db:
        user = db.get(User, user_uuid)
        if user is None:
            return
        for question in practice_set.questions:
            item = feedback_by_id.get(question.question_id)
            if not item or item.get("correct"):
                continue
            learner_answer = (answer_map.get(question.question_id) or "").strip()
            expected = str(item.get("correct_answer") or question.correct_answer or "").strip()
            if not learner_answer and not expected:
                continue
            try:
                capture_error_and_flashcard(
                    db,
                    user_id=user_uuid,
                    original_text=learner_answer or f"(blank answer) {question.prompt}",
                    payload={
                        "corrected_text": expected,
                        "error_pattern": f"{learner_answer or '(blank)'} -> {expected}",
                        "error_type": _error_type_for_question(question),
                        "explanation_vi": item.get("explanation_vi"),
                        "confidence": 0.8,
                    },
                    source="review",
                    cefr_level=user.cefr_level,
                    industry=user.industry,
                    source_metadata={
                        "lesson_id": lesson_id,
                        "practice_set_id": practice_set_id,
                        "question_id": question.question_id,
                        "question_type": question.type,
                        "prompt": question.prompt,
                    },
                    commit=True,
                )
            except Exception:
                logger.exception(
                    "learning: failed to persist practice error user_id=%s lesson_id=%s question_id=%s",
                    user_id,
                    lesson_id,
                    question.question_id,
                )
                db.rollback()


def _error_type_for_question(question: LessonQuestion) -> str:
    return {
        "multiple_choice_abcd": "grammar",
        "write_sentence": "writing",
        "vocab_answer": "vocab",
        "quick_definition": "vocab",
    }.get(question.type, "grammar")


@router.get("/learning/{lesson_id}/flashcards")
async def lesson_flashcards(lesson_id: str, user_id: str = Query(default=DEFAULT_USER_ID)) -> dict:
    learner = get_learner_profile(user_id)
    lesson = _require_lesson(lesson_id)
    vocabulary = get_lesson_vocabulary(lesson_id, learner)
    vocab_cards = [
        LessonFlashcard(
            card_id=item.word_id,
            lesson_id=lesson_id,
            word=item.word,
            pos=item.pos,
            front=item.word,
            back=FlashcardBack(definition_vi=item.definition_vi, example=item.example),
            source=item.source,
        )
        for item in vocabulary[:5]
    ]
    cards = [
        {"card_kind": "vocab", **card.model_dump(mode="json")}
        for card in vocab_cards
    ]
    personal_error_cards = _load_due_error_cards_for_user(user_id)
    cards.extend(personal_error_cards)

    state = await learning_store.get_state(user_id) or LearningState()
    state = _state_for_lesson(state, lesson, "FLASHCARD", "flashcards_started")
    await learning_store.save_state(user_id, state)

    response = {
        "lesson_id": lesson_id,
        "total_cards": len(cards),
        "cards": cards,
        "agent_message": (
            "Bạn đang ôn từ vựng của bài này, kèm thẻ lỗi cá nhân đến hạn."
            if personal_error_cards
            else "Bạn đang ôn từ vựng của bài này. Xem hết các thẻ rồi có thể hoàn thành bài học."
        ),
        "learning_state": _state_payload(state),
        "ui_directive": UIDirective(
            screen="FLASHCARD_RUNNER",
            action="OPEN",
            lesson_id=lesson_id,
            reason="flashcards_started",
        ).model_dump(mode="json"),
        "suggested_actions": _flashcard_actions(),
    }
    _log_frontend_payload("learning.vocabulary.flashcards", _flashcards_log_summary(response))
    return response


@router.post("/learning/{lesson_id}/complete")
async def complete_lesson(
    lesson_id: str,
    payload: LearningUserRequest | None = Body(default=None),
    user_id: str | None = Query(default=None),
) -> dict:
    resolved_user_id = _resolve_user_id(payload, user_id)
    learner = get_learner_profile(resolved_user_id)
    lesson = _require_lesson(lesson_id)
    state = await learning_store.get_state(resolved_user_id) or LearningState()
    state = _state_for_lesson(state, lesson, "LESSON_COMPLETE", "lesson_completed")
    state.flashcards_completed = True
    if lesson_id not in state.completed_lessons:
        state.completed_lessons.append(lesson_id)

    next_lesson = _next_incomplete_lesson(learner.cefr_level, state.completed_lessons)
    await learning_store.save_state(resolved_user_id, state)

    next_lesson_id = next_lesson.lesson_id if next_lesson else None
    response = {
        "completed_lesson_id": lesson_id,
        "next_lesson_id": next_lesson_id,
        "next_lesson": next_lesson.model_dump(mode="json") if next_lesson else None,
        "next_step": "LESSON_READING" if next_lesson else "NONE",
        "agent_message": "Bài học đã hoàn thành. Bạn muốn mở bài tiếp theo ngay bây giờ không?",
        "learning_state": _state_payload(state),
        "ui_directive": UIDirective(
            screen="LESSON_COMPLETE",
            action="OPEN",
            lesson_id=lesson_id,
            next_lesson_id=next_lesson_id,
            reason="lesson_completed",
        ).model_dump(mode="json"),
        "suggested_actions": _complete_actions(next_lesson_id),
    }
    _log_frontend_payload("learning.complete.next_lesson", response)
    return response


def _resolve_user_id(payload: LearningUserRequest | None, user_id: str | None) -> str:
    if user_id:
        return user_id
    if payload and payload.user_id:
        return payload.user_id
    return DEFAULT_USER_ID


def _load_personal_errors_for_user(user_id: str) -> list[dict]:
    try:
        with SessionLocal() as db:
            return load_personal_error_context(db, user_id=user_id, limit=5)
    except Exception:
        logger.exception("learning: failed to load personal error context user_id=%s", user_id)
        return []


def _load_due_error_cards_for_user(user_id: str) -> list[dict]:
    try:
        with SessionLocal() as db:
            return load_due_error_flashcards(db, user_id=user_id, limit=2)
    except Exception:
        logger.exception("learning: failed to load due error flashcards user_id=%s", user_id)
        return []


def _require_lesson(lesson_id: str):
    try:
        return get_lesson(lesson_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="lesson not found") from exc


def _can_resume(state: LearningState) -> bool:
    return bool(state.active_lesson_id and state.current_step != "LESSON_COMPLETE")


def _first_incomplete_lesson_id(learner: LearnerProfile, state: LearningState | None) -> str:
    next_lesson = _next_incomplete_lesson(learner.cefr_level, (state.completed_lessons if state else []))
    if next_lesson is None:
        lessons = list_lessons(learner.cefr_level)
        if not lessons:
            raise HTTPException(status_code=404, detail="no lessons found for learner level")
        return lessons[0].lesson_id
    return next_lesson.lesson_id


def _next_incomplete_lesson(cefr_level: str, completed_lessons: list[str]) -> LessonSummary | None:
    completed = set(completed_lessons)
    for lesson in list_lessons(cefr_level):
        if lesson.lesson_id not in completed:
            return lesson
    return None


def _step_to_status(step: str) -> str:
    return {
        "NONE": "none",
        "LESSON_READING": "reading",
        "PRACTICE": "practice",
        "FLASHCARD": "flashcard",
        "LESSON_COMPLETE": "completed",
    }.get(step, "reading")


def _status_to_step(status: str) -> str:
    return {
        "none": "NONE",
        "reading": "LESSON_READING",
        "practice": "PRACTICE",
        "flashcard": "FLASHCARD",
        "completed": "LESSON_COMPLETE",
    }.get((status or "").lower(), "NONE")


def _state_for_lesson(state: LearningState, lesson, to_step, reason: str) -> LearningState:
    previous_step = state.current_step
    lesson_changed = state.active_lesson_id is not None and state.active_lesson_id != lesson.lesson_id
    if lesson_changed:
        state.practice_set_id = None
        state.practice_completed = False
        state.flashcards_completed = False
        state.latest_practice_result = None

    state.active_lesson_id = lesson.lesson_id
    state.active_lesson_path = lesson.lesson_path
    state.current_step = to_step
    state.last_transition = LearningTransition(
        from_step=previous_step,
        to_step=to_step,
        reason=reason,
        created_at=datetime.utcnow(),
    )
    return state


def _active_lesson_payload(state: LearningState) -> dict | None:
    if not state.active_lesson_id:
        return None
    try:
        return get_lesson(state.active_lesson_id).model_dump(mode="json")
    except KeyError:
        return None


def _screen_for_step(step: str):
    return {
        "NONE": "CHAT",
        "LESSON_READING": "LESSON_READER",
        "PRACTICE": "PRACTICE_RUNNER",
        "FLASHCARD": "FLASHCARD_RUNNER",
        "LESSON_COMPLETE": "LESSON_COMPLETE",
    }.get(step, "CHAT")


def _message_for_current_state(state: LearningState) -> str:
    if state.current_step == "LESSON_READING":
        return "Bạn đang đọc bài học này. Khi sẵn sàng, mình có thể mở tab Ôn tập."
    if state.current_step == "PRACTICE":
        return "Bạn đang ở tab Ôn tập của bài này. Hoàn thành câu hỏi để xem kết quả."
    if state.current_step == "FLASHCARD":
        return "Bạn đang ôn từ vựng của bài này. Xem hết flashcards rồi có thể hoàn thành bài học."
    if state.current_step == "LESSON_COMPLETE":
        return "Bài học này đã hoàn thành. Bạn có thể mở bài tiếp theo."
    return "Bạn chưa có bài học đang mở. Hãy bắt đầu học để nhận bài đầu tiên."


def _learning_response(
    *,
    agent_message: str,
    state: LearningState,
    lesson: dict | None,
    ui_directive: UIDirective,
    suggested_actions: list[dict[str, str]],
) -> dict:
    return {
        "state": _state_payload(state),
        "learning_state": _state_payload(state),
        "lesson": lesson,
        "agent_message": agent_message,
        "ui_directive": ui_directive.model_dump(mode="json"),
        "suggested_actions": suggested_actions,
    }


def _log_frontend_payload(event: str, payload: dict) -> None:
    logger.info("frontend_payload.%s %s", event, json.dumps(payload, ensure_ascii=False, default=str))


def _lesson_log_summary(payload: dict) -> dict:
    lesson = payload.get("lesson") or {}
    metadata = lesson.get("metadata") or {}
    state = payload.get("learning_state") or payload.get("state") or {}
    markdown = lesson.get("markdown") or ""
    return {
        "lesson": {
            "lesson_id": lesson.get("lesson_id"),
            "title": lesson.get("title"),
            "cefr_level": lesson.get("cefr_level"),
            "skill_type": lesson.get("skill_type"),
            "lesson_path": lesson.get("lesson_path"),
            "metadata_path": lesson.get("metadata_path"),
            "order_index": lesson.get("order_index"),
            "objectives": metadata.get("objectives"),
            "recommended_vocab": metadata.get("recommended_vocab"),
            "exercise_types": metadata.get("exercise_types"),
            "markdown_chars": len(markdown),
        },
        "state": {
            "active_lesson_id": state.get("active_lesson_id"),
            "current_step": state.get("current_step"),
            "completed_lessons": state.get("completed_lessons"),
        },
        "ui_directive": payload.get("ui_directive"),
    }


def _questions_log_summary(payload: dict) -> dict:
    state = payload.get("learning_state") or {}
    return {
        "lesson_id": payload.get("lesson_id"),
        "practice_set_id": payload.get("practice_set_id"),
        "total_questions": payload.get("total_questions"),
        "question_counts": payload.get("question_counts"),
        "question_types": [
            {"question_id": question.get("question_id"), "type": question.get("type")}
            for question in payload.get("questions", [])
        ],
        "state": {
            "active_lesson_id": state.get("active_lesson_id"),
            "current_step": state.get("current_step"),
            "practice_set_id": state.get("practice_set_id"),
        },
        "ui_directive": payload.get("ui_directive"),
        "suggested_actions": payload.get("suggested_actions"),
    }


def _flashcards_log_summary(payload: dict) -> dict:
    state = payload.get("learning_state") or {}
    return {
        "lesson_id": payload.get("lesson_id"),
        "total_cards": payload.get("total_cards"),
        "card_metadata": [
            {
                "card_id": card.get("card_id"),
                "lesson_id": card.get("lesson_id"),
                "pos": card.get("pos"),
                "source": card.get("source"),
            }
            for card in payload.get("cards", [])
        ],
        "state": {
            "active_lesson_id": state.get("active_lesson_id"),
            "current_step": state.get("current_step"),
            "flashcards_completed": state.get("flashcards_completed"),
        },
        "ui_directive": payload.get("ui_directive"),
        "suggested_actions": payload.get("suggested_actions"),
    }


def _state_payload(state: LearningState) -> dict:
    return state.model_dump(mode="json")


def _grade_question(question: LessonQuestion, answer: str) -> dict:
    normalized_answer = _normalize_answer(answer)
    correct = False
    if question.type == "multiple_choice_abcd":
        correct = normalized_answer == _normalize_answer(question.correct_answer)
    elif question.type == "write_sentence":
        correct = _grade_write_sentence(question, answer)
    else:
        acceptable = question.rubric.acceptable_answers or [question.correct_answer]
        correct = any(_answers_match(normalized_answer, accepted) for accepted in acceptable)

    return {
        "question_id": question.question_id,
        "type": question.type,
        "correct": correct,
        "correct_answer": question.correct_answer,
        "explanation_vi": question.rubric.explanation_vi,
    }


def _grade_write_sentence(question: LessonQuestion, answer: str) -> bool:
    normalized = _normalize_answer(answer)
    if not normalized:
        return False
    for required in question.rubric.must_include:
        if _normalize_answer(required) not in normalized:
            return False
    if question.rubric.min_words and len(re.findall(r"\b\w+\b", answer)) < question.rubric.min_words:
        return False
    return True


def _answers_match(normalized_answer: str, accepted: str) -> bool:
    normalized_accepted = _normalize_answer(accepted)
    if not normalized_answer or not normalized_accepted:
        return False
    return (
        normalized_answer == normalized_accepted
        or normalized_answer in normalized_accepted
        or normalized_accepted in normalized_answer
    )


def _normalize_answer(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def _reading_actions() -> list[dict[str, str]]:
    return [
        {"label": "Ôn tập", "intent": "LESSON_PRACTICE"},
        {"label": "Mở flashcard", "intent": "LESSON_FLASHCARD"},
    ]


def _practice_actions() -> list[dict[str, str]]:
    return [
        {"label": "Nộp câu trả lời", "intent": "SUBMIT_PRACTICE"},
        {"label": "Đọc lại bài", "intent": "READ_LESSON"},
    ]


def _practice_result_actions() -> list[dict[str, str]]:
    return [
        {"label": "Mở flashcard", "intent": "LESSON_FLASHCARD"},
        {"label": "Ôn tập lại", "intent": "LESSON_PRACTICE"},
        {"label": "Đọc lại bài", "intent": "READ_LESSON"},
    ]


def _flashcard_actions() -> list[dict[str, str]]:
    return [
        {"label": "Hoàn thành bài", "intent": "LESSON_COMPLETE"},
        {"label": "Ôn tập lại", "intent": "LESSON_PRACTICE"},
    ]


def _complete_actions(next_lesson_id: str | None) -> list[dict[str, str]]:
    actions = [{"label": "Đọc lại bài", "intent": "READ_LESSON"}]
    if next_lesson_id:
        actions.insert(0, {"label": "Mở bài tiếp theo", "intent": "NEXT_LESSON"})
    return actions


def _suggested_actions_for_step(step: str) -> list[dict[str, str]]:
    if step == "LESSON_READING":
        return _reading_actions()
    if step == "PRACTICE":
        return _practice_actions()
    if step == "FLASHCARD":
        return _flashcard_actions()
    if step == "LESSON_COMPLETE":
        return _complete_actions(None)
    return [{"label": "Bắt đầu học", "intent": "START_LEARNING"}]
