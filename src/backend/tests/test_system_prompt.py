"""Tests for the Luna persona module and identity-leak guardrail."""
from __future__ import annotations

import asyncio

import pytest

from app.services import guardrails as gr
from app.services import system_prompt as sp


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# system_prompt module
# ---------------------------------------------------------------------------


def test_luna_prompt_contains_required_clauses():
    text = sp.LUNA_SYSTEM_PROMPT.lower()
    assert "luna" in text
    assert "a20" in text
    assert "scope" in text
    assert "identity" in text
    assert "ask next" in text
    assert "system details" in text
    # Must explicitly forbid naming the provider.
    for forbidden in ("gemini", "llama", "gpt", "claude", "openai", "meta", "groq"):
        assert forbidden in text


def test_build_messages_with_persona_shape():
    msgs = sp.build_messages_with_persona("Câu hỏi: từ 'depreciate' nghĩa là gì?")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "system"
    assert "Luna" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "depreciate" in msgs[1]["content"]


def test_build_messages_with_persona_includes_only_five_recent_turns():
    msgs = sp.build_messages_with_persona(
        "Câu hiện tại",
        turns=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
            {"role": "assistant", "content": "a3"},
        ],
    )

    assert msgs[0]["role"] == "system"
    assert [msg["content"] for msg in msgs[1:-1]] == ["a1", "u2", "a2", "u3", "a3"]
    assert msgs[-1] == {"role": "user", "content": "Câu hiện tại"}


def test_build_messages_with_persona_extra_system():
    msgs = sp.build_messages_with_persona(
        "irrelevant",
        extra_system="Return JSON only with keys foo, bar.",
    )
    assert "ADDITIONAL INSTRUCTIONS" in msgs[0]["content"]
    assert "Return JSON only" in msgs[0]["content"]
    # Persona must come before the extra block.
    persona_idx = msgs[0]["content"].find("Luna")
    extra_idx = msgs[0]["content"].find("Return JSON only")
    assert 0 <= persona_idx < extra_idx


def test_prepend_persona_merges_existing_system():
    original = [
        {"role": "system", "content": "Return JSON only."},
        {"role": "user", "content": "hi"},
    ]
    out = sp.prepend_persona(original)
    assert len(out) == 2
    assert out[0]["role"] == "system"
    assert "Luna" in out[0]["content"]
    assert "Return JSON only." in out[0]["content"]
    assert out[1] == {"role": "user", "content": "hi"}


def test_prepend_persona_no_existing_system():
    original = [{"role": "user", "content": "hi"}]
    out = sp.prepend_persona(
        original,
        turns=[
            {"role": "assistant", "content": "before"},
            {"role": "user", "content": "after"},
        ],
    )
    assert len(out) == 4
    assert out[1] == {"role": "assistant", "content": "before"}
    assert out[2] == {"role": "user", "content": "after"}
    assert out[3] == {"role": "user", "content": "hi"}


def test_prepend_persona_ignores_invalid_turns():
    original = [{"role": "user", "content": "hi"}]
    out = sp.prepend_persona(
        original,
        turns=[
            {"role": "system", "content": "skip"},
            {"role": "assistant", "content": ""},
            {"role": "assistant", "content": "keep"},
        ],
    )
    assert len(out) == 3
    assert out[0]["role"] == "system"
    assert "Luna" in out[0]["content"]
    assert out[1] == {"role": "assistant", "content": "keep"}
    assert out[2] == {"role": "user", "content": "hi"}


def test_prepend_persona_empty_messages():
    out = sp.prepend_persona([])
    assert len(out) == 1
    assert out[0]["role"] == "system"
    assert "Luna" in out[0]["content"]


# ---------------------------------------------------------------------------
# Identity-leak detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "Tôi là một mô hình ngôn ngữ AI được gọi là LLaMA (Large Language Model Meta AI).",
        "I am a large language model trained by OpenAI.",
        "Mình là Gemini-2.5 do Google phát triển.",
        "I'm a chatbot built on GPT-4.",
        "This response was developed by Anthropic.",
        "Tôi được tạo ra bởi Meta.",
        "Powered by Groq cloud infrastructure.",
        "Hi, I'm Claude-3 from Anthropic.",
    ],
)
def test_detect_identity_leak_positives(text):
    assert gr.detect_identity_leak(text) is not None, f"should flag: {text!r}"


@pytest.mark.parametrize(
    "text",
    [
        "Câu của bạn đã đúng ngữ pháp.",
        "Hãy thử dùng từ 'depreciate' thay vì 'go down'.",
        "The word 'launch' fits this context better.",
        "",
    ],
)
def test_detect_identity_leak_negatives(text):
    assert gr.detect_identity_leak(text) is None


def test_output_guard_blocks_identity_leak():
    state = {
        "user_id": "u1",
        "response": (
            "Tôi là một mô hình ngôn ngữ AI được gọi là LLaMA "
            "(Large Language Model Meta AI). Tôi không phải là Gemini."
        ),
    }
    out = _run(gr.output_guard(state))
    assert out["response"] == gr.SAFE_IDENTITY_REPLY
    assert out["guardrail_output_action"] == "blocked_identity_leak"


def test_output_guard_identity_takes_precedence_over_pii():
    """A reply that leaks BOTH identity and an email should hit the
    identity branch first (it's a stronger violation)."""
    state = {
        "user_id": "u1",
        "response": "I'm GPT-4. Email me at test@x.com.",
    }
    out = _run(gr.output_guard(state))
    assert out["guardrail_output_action"] == "blocked_identity_leak"
    assert out["response"] == gr.SAFE_IDENTITY_REPLY


# ---------------------------------------------------------------------------
# Wiring: scaffolding_engine ENGLISH_RAG path now sends a system message
# ---------------------------------------------------------------------------


def test_quick_qa_sends_persona_system_message(monkeypatch):
    """Regression test for the bug where 'bạn là model gì?' got
    classified as ENGLISH_RAG but the path lacked a system prompt, letting
    the model answer 'I am LLaMA'."""
    pytest.importorskip("sqlalchemy")
    from app.services import scaffolding_engine as se

    captured: dict = {}

    class _FakeLLM:
        enabled = True
        last_provider = "gemini"

        async def generate_chat_completion(self, messages, **kw):
            captured["messages"] = messages
            return "Mình là Luna, gia sư tiếng Anh của A20 Tutor."

    monkeypatch.setattr(se, "get_llm_client", lambda: _FakeLLM())

    state = {
        "user_id": "u1",
        "user_input": "Bạn là model gì?",
        "intent": "ENGLISH_RAG",
        "memory": [],
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "user_profile": {},
        "db": None,
    }
    result = _run(se.scaffolding_engine(state))

    msgs = captured["messages"]
    assert msgs[0]["role"] == "system"
    assert "Luna" in msgs[0]["content"]
    assert "IDENTITY" in msgs[0]["content"]
    assert msgs[1]["role"] == "user"
    assert "model gì" in msgs[1]["content"].lower() or "model gì" in state["user_input"].lower()
    # Sanity: the response surfaced through.
    assert "Luna" in result["response"]
