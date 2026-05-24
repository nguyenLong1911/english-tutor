from __future__ import annotations

import asyncio
from uuid import uuid4

from app.services import eval_error_spans
from app.models.processed_dataset_schemas import ChatRequest


def _run(coro):
    return asyncio.run(coro)


def test_extract_eval_sentence_from_runner_prompt():
    message = (
        "Return only a JSON array of incorrect spans from the learner sentence.\n\n"
        "Learner sentence:\nShe go to school yesterday."
    )

    assert eval_error_spans.extract_eval_sentence(message) == "She go to school yesterday."


def test_eval_error_spans_returns_machine_readable_json(monkeypatch):
    captured = {}

    class _LLM:
        last_provider = "gemini"
        last_model = "gemini-test-model"

        async def generate_chat_completion(self, messages, temperature=0.7, max_tokens=500):
            captured["messages"] = messages
            captured["temperature"] = temperature
            captured["max_tokens"] = max_tokens
            return '["go"]'

    monkeypatch.setattr(eval_error_spans, "get_llm_client", lambda: _LLM())

    response = _run(
        eval_error_spans.run_error_span_eval(
            ChatRequest(
                user_id=uuid4(),
                type="EVAL_ERROR_SPANS",
                message="Learner sentence:\nShe go to school yesterday.",
            )
        )
    )

    assert response.intent == "EVAL_ERROR_SPANS"
    assert response.response == '["go"]'
    assert "She go to school yesterday." in captured["messages"][1]["content"]
    assert captured["temperature"] == 0.0


def test_eval_error_spans_rejects_mock_provider(monkeypatch):
    class _LLM:
        last_provider = "mock"
        last_model = None

        async def generate_chat_completion(self, messages, temperature=0.7, max_tokens=500):
            return "Mình đã nhận câu của bạn"

    monkeypatch.setattr(eval_error_spans, "get_llm_client", lambda: _LLM())

    try:
        _run(
            eval_error_spans.run_error_span_eval(
                ChatRequest(
                    user_id=uuid4(),
                    type="EVAL_ERROR_SPANS",
                    message="Learner sentence:\nShe go to school yesterday.",
                )
            )
        )
    except eval_error_spans.LiveEvalProviderRequired as exc:
        assert "live LLM provider" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("mock provider must block evaluation")
