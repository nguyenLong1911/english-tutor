from __future__ import annotations

import asyncio

from app.services.langgraph_orchestrator import _fallback_intent
from app.services import langgraph_orchestrator as orch
from app.api.v1.chat import _classify_intent
from app.utils.llm import _fallback_intent_for_text


def _assert_all_fallbacks(message: str, expected: str) -> None:
    assert _fallback_intent(message) == expected
    assert _fallback_intent_for_text(message) == expected
    assert _classify_intent(message) == expected


def test_vietnamese_meaning_question_without_question_mark_is_quick_qa():
    message = "hello có nghĩa là gì"

    _assert_all_fallbacks(message, "ENGLISH_RAG")


def test_short_greeting_is_quick_qa_not_practice():
    _assert_all_fallbacks("hi", "ENGLISH_RAG")


def test_confused_about_statement_is_quick_qa():
    message = "I'm confused about 'in', 'on', 'at' for time expressions."

    _assert_all_fallbacks(message, "ENGLISH_RAG")


def test_vietnamese_luyen_tap_question_stays_practice():
    message = "Tôi muốn luyện tập?"

    _assert_all_fallbacks(message, "ENGLISH_RAG")


def test_vietnamese_open_review_question_stays_learning_navigation_not_practice():
    message = "Mở ôn tập cho bài này?"

    _assert_all_fallbacks(message, "ENGLISH_RAG")


def test_vietnamese_identity_questions_are_quick_qa_without_question_mark():
    for message in ("tôi là ai", "toi la ai", "bạn là ai", "mình đang ở đâu"):
        _assert_all_fallbacks(message, "ENGLISH_RAG")


def test_clear_english_practice_attempt_stays_practice():
    _assert_all_fallbacks("I am study English everyday for 2 hour", "ENGLISH_RAG")


def test_vietnamese_sentence_check_with_quoted_english_stays_practice():
    _assert_all_fallbacks('Tôi nói "This plan is more then expected." đã đúng chưa?', "ENGLISH_RAG")


def test_ielts_target_score_question_is_quick_qa_not_progress():
    _assert_all_fallbacks("How can I get IELTS score 7.0?", "ENGLISH_RAG")


def test_progress_request_is_progress():
    _assert_all_fallbacks("How am I doing this week? What's my progress?", "ENGLISH_RAG")


def test_intent_router_falls_back_to_heuristic_when_llm_classifier_fails(monkeypatch):
    class _BrokenLLM:
        async def generate_chat_completion(self, *args, **kwargs):
            raise RuntimeError("llm down")

    monkeypatch.setattr(orch, "get_llm_client", lambda: _BrokenLLM())

    state = {"user_input": "What is my progress?", "intent": "ENGLISH_RAG"}
    result = asyncio.run(orch.intent_router(state))

    assert result["intent"] == "ENGLISH_RAG"


def test_intent_router_passes_identity_question_through_without_blocking(monkeypatch):
    class _ExplodingLLM:
        async def generate_chat_completion(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("intent_router should not call the llm")

    monkeypatch.setattr(orch, "get_llm_client", lambda: _ExplodingLLM())

    state = {"user_input": "tôi là ai", "intent": "ENGLISH_RAG"}
    result = asyncio.run(orch.intent_router(state))

    assert result["intent"] == "ENGLISH_RAG"
    assert not result.get("guardrail_blocked", False)


def test_intent_router_passes_non_learning_message_through_without_out_of_scope_block():
    state = {"user_input": "Bạn có những thông tin gì về tôi?", "intent": "ENGLISH_RAG"}
    result = asyncio.run(orch.intent_router(state))

    assert result["intent"] == "ENGLISH_RAG"
    assert not result.get("guardrail_blocked", False)
