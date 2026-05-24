from __future__ import annotations

import asyncio

from app.services import scaffolding_engine as scaffolding_module


def _run(coro):
    return asyncio.run(coro)


class _FakeLLM:
    enabled = True

    def __init__(self, *, provider: str, response: str) -> None:
        self.last_provider = provider
        self.last_model = "fake-model"
        self.last_usage = {"prompt_tokens": 12, "completion_tokens": 24}
        self._response = response
        self.calls = []

    async def generate_chat_completion(self, messages, temperature=0.7, max_tokens=500):
        self.calls.append({"messages": messages, "temperature": temperature, "max_tokens": max_tokens})
        return self._response


def test_regular_chat_uses_assessment_contract(monkeypatch):
    fake_llm = _FakeLLM(
        provider="gemini",
        response=(
            '{"status":"unavailable","response_vi":"`affect` thường là động từ, còn `effect` thường là danh từ.",'
            '"corrected_text":"","error_pattern":"","wrong_word":"","correct_word":"",'
            '"error_type":"","error_dimension":"","error_subtype":"","explanation_vi":"","confidence":0.0}'
        ),
    )
    monkeypatch.setattr(scaffolding_module, "get_llm_client", lambda: fake_llm)

    state = {
        "user_id": "user-1",
        "user_input": "Giải thích sự khác biệt affect và effect",
        "intent": "ENGLISH_RAG",
        "memory": [],
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "db": None,
    }

    result = _run(scaffolding_module.scaffolding_engine(state))

    assert result["response"] == "`affect` thường là động từ, còn `effect` thường là danh từ."
    assert fake_llm.calls
    assert result["practice_assessment"]["status"] == "unavailable"
    assert result["practice_assessment"]["error_pattern"] == ""
    assert "Return only valid JSON with keys: status, response_vi, corrected_text" in fake_llm.calls[0]["messages"][-1]["content"]
    assert result["new_facts"] == []


def test_greeting_also_uses_assessment_contract(monkeypatch):
    fake_llm = _FakeLLM(
        provider="gemini",
        response=(
            '{"status":"unavailable","response_vi":"Xin chào Linh! Hôm nay mình học tiếng Anh nhé.",'
            '"corrected_text":"","error_pattern":"","wrong_word":"","correct_word":"",'
            '"error_type":"","error_dimension":"","error_subtype":"","explanation_vi":"","confidence":0.0}'
        ),
    )
    monkeypatch.setattr(scaffolding_module, "get_llm_client", lambda: fake_llm)

    state = {
        "user_id": "user-1",
        "user_input": "hi",
        "intent": "ENGLISH_RAG",
        "memory": [],
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "user_profile": {
            "display_name": "Linh",
            "cefr_level": "B1",
            "industry": "marketing",
            "learning_goals": ["thuyết trình", "viết email"],
            "preferred_study_time": "10 phút",
        },
        "db": None,
    }

    result = _run(scaffolding_module.scaffolding_engine(state))

    assert "Xin chào Linh" in result["response"]
    assert fake_llm.calls
    assert result["practice_assessment"]["status"] == "unavailable"
    assert result["new_facts"] == []


def test_mock_fallback_returns_generic_response(monkeypatch):
    fake_llm = _FakeLLM(provider="mock", response="mocked")
    monkeypatch.setattr(scaffolding_module, "get_llm_client", lambda: fake_llm)

    state = {
        "user_id": "user-1",
        "user_input": "This unclear input",
        "intent": "ENGLISH_RAG",
        "memory": [],
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "db": None,
    }

    result = _run(scaffolding_module.scaffolding_engine(state))

    assert result["response"] == "Mình đã nhận câu hỏi tiếng Anh của bạn: This unclear input"


def test_practice_message_preserves_structured_assessment_for_capture(monkeypatch):
    fake_llm = _FakeLLM(
        provider="gemini",
        response=(
            '{"status":"needs_revision","response_vi":"Câu này nên dùng affect.",'
            '"corrected_text":"The new deployment will affect our project timeline.",'
            '"error_pattern":"effect -> affect","wrong_word":"effect","correct_word":"affect",'
            '"error_type":"vocab","error_dimension":"vocab","error_subtype":"word_choice",'
            '"explanation_vi":"Affect thường là động từ; effect thường là danh từ.",'
            '"confidence":0.93}'
        ),
    )
    monkeypatch.setattr(scaffolding_module, "get_llm_client", lambda: fake_llm)

    state = {
        "user_id": "user-1",
        "user_input": "The new deployment will effect our project timeline.",
        "type": "PRACTICE",
        "intent": "ENGLISH_RAG",
        "memory": [],
        "hint_count": 0,
        "new_facts": [],
        "turns": [],
        "db": None,
    }

    result = _run(scaffolding_module.scaffolding_engine(state))

    assert result["response"] == "Câu này nên dùng affect."
    assert result["practice_assessment"]["status"] == "needs_revision"
    assert result["practice_assessment"]["error_pattern"] == "effect -> affect"
    assert "Return only valid JSON with keys: status, response_vi, corrected_text" in fake_llm.calls[0]["messages"][-1]["content"]


def test_english_rag_prompt_includes_personal_error_context():
    messages = scaffolding_module._build_english_rag_prompt(
        {
            "user_profile": {"cefr_level": "A2", "industry": "business", "learning_goals": []},
            "memory": [],
            "turns": [],
            "personal_error_context": [
                {
                    "error_type": "grammar",
                    "error_pattern": "then -> than",
                    "corrected_text": "This is better than that.",
                    "explanation_vi": "Dung than khi so sanh.",
                    "recent_count": 2,
                }
            ],
        },
        "Giải thích giúp mình",
        None,
    )

    user_message = messages[-1]["content"]
    assert "Personal recurring errors" in user_message
    assert "then -> than" in user_message
    assert "Giải thích giúp mình" in user_message
    assert "Reference corpus context" not in user_message


def test_english_rag_prompt_treats_learner_memory_question_as_in_scope():
    messages = scaffolding_module._build_practice_assessment_prompt(
        {
            "user_profile": {
                "display_name": "Linh",
                "cefr_level": "B1",
                "industry": "marketing",
                "learning_goals": ["viết email"],
            },
            "memory": [{"content": "Learner prefers short business examples."}],
            "turns": [],
            "personal_error_context": [{"error_pattern": "effect -> affect"}],
        },
        "Bạn biết gì về tôi?",
        None,
    )

    prompt = messages[-1]["content"]
    assert "Bạn biết gì về tôi?" in prompt
    assert "hỏi bạn biết/nhớ gì về họ" in prompt
    assert "answer from the learner profile/progress/personal context" in prompt
    assert "Linh" in prompt
    assert "effect -> affect" in prompt


def test_english_rag_prompt_carries_recent_five_turns():
    messages = scaffolding_module._build_english_rag_prompt(
        {
            "user_profile": {},
            "memory": [],
            "turns": [
                {"role": "user", "content": "c1"},
                {"role": "assistant", "content": "c2"},
                {"role": "user", "content": "c3"},
                {"role": "assistant", "content": "c4"},
                {"role": "user", "content": "c5"},
                {"role": "assistant", "content": "c6"},
            ],
        },
        "Cần sửa lại gì thế",
        None,
    )

    assert messages[0]["role"] == "system"
    assert [msg["content"] for msg in messages[1:-1]] == ["c2", "c3", "c4", "c5", "c6"]
    assert messages[-1]["role"] == "user"
    assert "Cần sửa lại gì thế" in messages[-1]["content"]
