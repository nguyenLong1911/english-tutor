from __future__ import annotations

import asyncio
import uuid

import pytest

from app.api.v1 import learning as learning_module
from app.models.processed_dataset_schemas import LessonVocabularyItem
from app.services import corpus_retrieval
from app.services import langgraph_orchestrator as orch
from app.services import scaffolding_engine as scaffolding_module


class _FakeLLM:
    enabled = True
    last_provider = "test"

    async def generate_chat_completion(self, messages, **kwargs):
        _ = kwargs
        content = messages[-1]["content"]
        if "Classify the user's intent" in content:
            return "ENGLISH_RAG"
        if "cannot move to the next lesson yet because the current lesson is unfinished" in content:
            return "Mình thấy bạn vẫn đang học dở bài này. Nếu muốn, mình mở tiếp để bạn học nốt; còn nếu muốn qua bài mới thì cứ nói \"bỏ qua bài này\" nhé."
        return "Câu trả lời nhanh cho câu hỏi tiếng Anh của bạn."


class _NoopMemory:
    def search_memory(self, *args, **kwargs):
        return []


def _test_vocabulary(*args, **kwargs):
    return [
        LessonVocabularyItem(
            word_id=f"test-word-{idx}",
            word=word,
            pos="noun",
            definition_vi=f"nghia cua {word}",
            example=f"We use {word} at work.",
            source="test",
        )
        for idx, word in enumerate(("meeting", "deadline", "report", "client", "agenda"), start=1)
    ]


@pytest.fixture(autouse=True)
def reset_learning_store_and_llm(monkeypatch):
    learning_module.learning_store = learning_module.InMemoryLearningStore()
    fake_llm = _FakeLLM()
    monkeypatch.setattr(orch, "get_llm_client", lambda: fake_llm)
    monkeypatch.setattr(orch, "get_memory", lambda: _NoopMemory())
    monkeypatch.setattr(scaffolding_module, "get_llm_client", lambda: fake_llm)
    monkeypatch.setattr(learning_module, "_load_due_error_cards_for_user", lambda user_id: [])
    monkeypatch.setattr(learning_module, "_load_personal_errors_for_user", lambda user_id: [])
    monkeypatch.setattr(learning_module, "get_lesson_vocabulary", _test_vocabulary)
    yield


def _run(coro):
    return asyncio.run(coro)


def _user_id() -> str:
    return f"phase4-{uuid.uuid4().hex}"


def _state(user_id: str, message: str) -> dict:
    return {
        "user_id": user_id,
        "user_input": message,
        "intent": "ENGLISH_RAG",
        "memory": [],
        "response": "",
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "last_practice_input": "",
        "user_profile": {"cefr_level": "A2", "industry": "business", "learning_goals": []},
        "db": None,
    }


def test_chat_start_learning_returns_lesson_reader_directive():
    result = _run(orch.run_chat_pipeline(_state(_user_id(), "let's start learning")))

    assert result["learning_intent"] == "START_LEARNING"
    assert result["ui_directive"]["screen"] == "LESSON_READER"
    assert result["learning_state"]["current_step"] == "LESSON_READING"
    assert result["response"] == result["agent_message"]


def test_open_first_lesson_command_routes_to_learning_not_practice():
    result = _run(orch.run_chat_pipeline(_state(_user_id(), "Mở bài giảng đầu tiên đi")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "START_LEARNING"
    assert result["ui_directive"]["screen"] == "LESSON_READER"


def test_chat_flashcards_during_active_lesson_returns_flashcard_runner():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "I want flashcards now")))

    assert result["learning_intent"] == "LESSON_FLASHCARD"
    assert result["ui_directive"]["screen"] == "FLASHCARD_RUNNER"
    assert result["learning_state"]["current_step"] == "FLASHCARD"


def test_open_flashcard_command_routes_to_flashcard_runner():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "Mở flashcard cho bài này")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "LESSON_FLASHCARD"
    assert result["ui_directive"]["screen"] == "FLASHCARD_RUNNER"


def test_chat_practice_during_active_lesson_returns_practice_runner_and_practice_set():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "give me exercises")))
    practice_set_id = result["ui_directive"]["practice_set_id"]
    practice_set = _run(learning_module.learning_store.get_practice_set(user_id, practice_set_id))

    assert result["learning_intent"] == "LESSON_PRACTICE"
    assert result["ui_directive"]["screen"] == "PRACTICE_RUNNER"
    assert practice_set_id
    assert practice_set is not None
    assert practice_set.total_questions == 12


def test_ielts_target_score_question_routes_to_quick_qa_not_progress():
    result = _run(
        orch.run_chat_pipeline(
            _state(_user_id(), "What do I need to do to achieve an IELTS score of 7.0? Give me real info.")
        )
    )

    assert result["intent"] == "ENGLISH_RAG"


def test_lesson_questions_passes_personal_errors_to_generator(monkeypatch):
    captured = {}
    original_generator = learning_module.create_lesson_questions

    async def _capturing_generator(learner, lesson, vocabulary, question_plan=None, personal_errors=None):
        captured["personal_errors"] = personal_errors
        if question_plan is None:
            return await original_generator(learner, lesson, vocabulary, personal_errors=personal_errors)
        return await original_generator(learner, lesson, vocabulary, question_plan, personal_errors=personal_errors)

    monkeypatch.setattr(
        learning_module,
        "_load_personal_errors_for_user",
        lambda user_id: [{"error_pattern": "then -> than", "error_type": "grammar"}],
    )
    monkeypatch.setattr(learning_module, "create_lesson_questions", _capturing_generator)

    result = _run(
        learning_module.lesson_questions(
            "A2_present_simple_be",
            payload=learning_module.LearningUserRequest(user_id=_user_id()),
            user_id=None,
        )
    )

    assert result["total_questions"] == 12
    assert captured["personal_errors"] == [{"error_pattern": "then -> than", "error_type": "grammar"}]


def test_lesson_flashcards_appends_due_personal_error_cards(monkeypatch):
    monkeypatch.setattr(
        learning_module,
        "_load_due_error_cards_for_user",
        lambda user_id: [
            {
                "card_kind": "error",
                "card_id": "error-card-1",
                "flashcard_id": "error-card-1",
                "lesson_id": None,
                "word": "Personal correction",
                "pos": "grammar",
                "front": "Sua loi trong cau: This is better ____ that.",
                "back": {"definition_vi": "This is better than that.", "example": "This is better than that."},
                "source": "chat",
                "error_type": "grammar",
                "cloze_text": "This is better ____ that.",
                "explanation_vi": "Dung than khi so sanh.",
            }
        ],
    )

    result = _run(learning_module.lesson_flashcards("A2_present_simple_be", user_id=_user_id()))

    assert result["total_cards"] == 6
    assert result["cards"][-1]["card_kind"] == "error"
    assert "lỗi cá nhân" in result["agent_message"]


def test_vietnamese_review_request_routes_to_lesson_practice_instead_of_chat_practice():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "Tôi muốn vào chế độ ôn tập")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "LESSON_PRACTICE"
    assert result["ui_directive"]["screen"] == "PRACTICE_RUNNER"
    assert result["response"] == result["agent_message"]


def test_vietnamese_review_request_without_active_lesson_still_prioritizes_learning_flow():
    result = _run(orch.run_chat_pipeline(_state(_user_id(), "Tôi muốn ôn tập phần bài học này")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "LESSON_PRACTICE"
    assert result["ui_directive"]["screen"] == "PRACTICE_RUNNER"
    assert result["response"] == result["agent_message"]


def test_vietnamese_luyen_tap_keeps_practice_mode_instead_of_opening_review_tab():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "Tôi muốn luyện tập")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "NONE"
    assert result["ui_directive"] is None


def test_chat_current_lesson_status_returns_learning_state():
    user_id = _user_id()
    started = _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "what is my current lesson?")))

    assert result["learning_intent"] == "LESSON_STATUS"
    assert result["learning_state"]["active_lesson_id"] == started["learning_state"]["active_lesson_id"]
    assert result["ui_directive"]["screen"] == "LESSON_READER"


def test_next_lesson_block_uses_friendlier_llm_message_when_current_lesson_unfinished():
    user_id = _user_id()
    _run(orch.run_chat_pipeline(_state(user_id, "start learning")))

    result = _run(orch.run_chat_pipeline(_state(user_id, "Oke bắt đầu bài giảng mới đi")))

    assert result["learning_intent"] == "NEXT_LESSON"
    assert result["ui_directive"]["screen"] == "LESSON_READER"
    assert "bỏ qua bài này" in result["agent_message"]
    assert result["agent_message"] != "Bài hiện tại chưa hoàn thành. Nếu muốn chuyển bài, hãy nói rõ là bạn muốn bỏ qua bài này."


def test_non_learning_quick_qa_keeps_no_ui_directive():
    result = _run(orch.run_chat_pipeline(_state(_user_id(), "What does 'meeting' mean?")))

    assert result["intent"] == "ENGLISH_RAG"
    assert result["learning_intent"] == "NONE"
    assert result["ui_directive"] is None


def test_memory_retrieval_skips_mem0_when_profile_memory_degraded(monkeypatch):
    class _ExplodingMemory:
        def search_memory(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("degraded request should not call Mem0 search")

    monkeypatch.setattr(orch, "get_memory", lambda: _ExplodingMemory())

    state = _state(_user_id(), "What does 'meeting' mean?")
    state["intent"] = "ENGLISH_RAG"
    state["memory_degraded"] = True

    result = _run(orch.memory_retrieval(state))

    assert result["memory"] == []


def test_memory_retrieval_does_not_call_static_corpus_on_hotpath(monkeypatch):
    class _Memory:
        def search_memory(self, *args, **kwargs):
            return [{"content": "Learner confuses then and than."}]

    def _explode(*args, **kwargs):  # pragma: no cover
        raise AssertionError("static corpus retrieval must stay out of chat runtime")

    monkeypatch.setenv("CORPUS_RETRIEVAL_ENABLED", "true")
    monkeypatch.setattr(orch, "get_memory", lambda: _Memory())
    monkeypatch.setattr(corpus_retrieval, "search_many", _explode)

    state = _state(_user_id(), "Can you check this sentence?")
    state["intent"] = "ENGLISH_RAG"
    state["corpus_hits"] = {"error": [{"text": "stale"}]}
    state["corpus_flat"] = [{"text": "stale"}]

    result = _run(orch.memory_retrieval(state))

    assert result["memory"] == [{"content": "Learner confuses then and than."}]
    assert "corpus_hits" not in result
    assert "corpus_flat" not in result


def test_vietnamese_sentence_check_routes_to_practice_for_error_capture():
    assert orch._fallback_intent('Tôi nói "This plan is more then expected." đã đúng chưa?') == "ENGLISH_RAG"
