from __future__ import annotations

import asyncio
from urllib.error import HTTPError

import pytest
import requests

from app.core.config import get_settings
from app.utils import llm as llm_module
from app.utils.llm import GeminiLLMClient, GroqLLMClient


def _run(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    llm_module._llm_client = None
    llm_module._llm_client_signature = None
    yield
    get_settings.cache_clear()
    llm_module._llm_client = None
    llm_module._llm_client_signature = None


def test_gemini_falls_back_to_groq(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    get_settings.cache_clear()

    def raise_gemini_error(*args, **kwargs):
        raise HTTPError("https://generativelanguage.googleapis.com", 401, "Unauthorized", None, None)

    async def groq_success(self, messages, temperature=0.7, max_tokens=500):
        self.last_provider = "groq"
        return "groq-response"

    monkeypatch.setattr(GeminiLLMClient, "_request_once", raise_gemini_error)
    monkeypatch.setattr(GroqLLMClient, "generate_chat_completion", groq_success)

    client = GeminiLLMClient(api_key="gemini-key", model="gemini-2.0-flash")
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Say QUICK_QA only."}],
            temperature=0,
            max_tokens=16,
        )
    )

    assert result == "groq-response"
    assert client.last_provider == "groq"


def test_gemini_then_groq_then_mock(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    get_settings.cache_clear()

    def raise_gemini_error(*args, **kwargs):
        raise HTTPError("https://generativelanguage.googleapis.com", 401, "Unauthorized", None, None)

    def raise_groq_error(*args, **kwargs):
        raise HTTPError("https://api.groq.com/openai/v1/chat/completions", 401, "Unauthorized", None, None)

    monkeypatch.setattr(GeminiLLMClient, "_request_once", raise_gemini_error)
    monkeypatch.setattr(GroqLLMClient, "_request_once", raise_groq_error)

    client = GeminiLLMClient(api_key="gemini-key", model="gemini-2.0-flash")
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Say QUICK_QA only."}],
            temperature=0,
            max_tokens=16,
        )
    )

    assert result.startswith("Mình đã nhận câu của bạn:")
    assert client.last_provider == "mock"


def test_groq_falls_back_to_gemini_before_mock(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    get_settings.cache_clear()

    def raise_groq_error(*args, **kwargs):
        raise requests.exceptions.HTTPError(response=type("_Resp", (), {"status_code": 429})())

    async def gemini_success(self, messages, temperature=0.7, max_tokens=500):
        self.last_provider = "gemini"
        self.last_usage = {"prompt_tokens": 2, "completion_tokens": 3}
        self.last_model = "gemini-test"
        return "gemini-response"

    monkeypatch.setattr(GroqLLMClient, "_request_once", raise_groq_error)
    monkeypatch.setattr(GeminiLLMClient, "generate_chat_completion", gemini_success)

    client = GroqLLMClient()
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Say OK"}],
            temperature=0,
            max_tokens=20,
        )
    )

    assert result == "gemini-response"
    assert client.last_provider == "gemini"
    assert client.last_model == "gemini-test"


def test_mock_fallback_returns_user_facing_message_for_next_lesson_block_prompt():
    client = GroqLLMClient(api_key=None, model="test-model")
    result = _run(
        client.generate_chat_completion(
            [
                {
                    "role": "user",
                    "content": (
                        "Write one short, friendly Vietnamese reply for an English-learning app.\n"
                        "Situation:\n"
                        "- Learner asked: Chuyển tôi tới bài giảng mới\n"
                        "- Current lesson: Present Simple with 'to be'\n"
                        "- Current step: LESSON_READING\n"
                        "- The learner cannot move to the next lesson yet because the current lesson is unfinished.\n"
                        "- Ask them to continue the current lesson, or explicitly say 'bỏ qua bài này' if they really want to skip.\n"
                        "- Keep it natural, warm, and concise.\n"
                        "- Do not mention policy, system, UI directive, or technical details.\n"
                        "- Return only the final learner-facing message."
                    ),
                }
            ],
            temperature=0.4,
            max_tokens=90,
        )
    )

    assert "bỏ qua bài này" in result
    assert "Write one short, friendly Vietnamese reply" not in result
    assert "Current lesson:" not in result


def test_groq_uses_llm_model_when_provider_is_groq_and_groq_model_is_unset(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    get_settings.cache_clear()

    client = GroqLLMClient()

    assert client.model == "openai/gpt-oss-20b"


def test_groq_model_explicit_override_beats_llm_model(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    get_settings.cache_clear()

    client = GroqLLMClient()

    assert client.model == "llama-3.3-70b-versatile"


def test_get_llm_client_refreshes_when_groq_key_appears(monkeypatch):
    monkeypatch.setenv("CHAT_LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    get_settings.cache_clear()

    first = llm_module.get_llm_client()

    assert isinstance(first, GeminiLLMClient)
    assert first.enabled is False

    monkeypatch.setenv("GROQ_API_KEY", "groq-key")

    second = llm_module.get_llm_client()

    assert isinstance(second, GroqLLMClient)
    assert second.enabled is True
    assert second.api_key == "groq-key"


def test_gpt_oss_groq_requests_disable_reasoning(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    get_settings.cache_clear()

    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "TEST_OK"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    client = GroqLLMClient()
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Reply with exactly TEST_OK"}],
            temperature=0,
            max_tokens=20,
        )
    )

    assert result == "TEST_OK"
    assert captured["json"]["max_tokens"] == 1600
    assert captured["json"]["include_reasoning"] is False
    assert captured["json"]["reasoning_effort"] == "low"


def test_groq_output_tokens_are_capped(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    monkeypatch.setenv("GROQ_MAX_OUTPUT_TOKENS", "4096")
    get_settings.cache_clear()

    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": "TEST_OK"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    client = GroqLLMClient()
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Reply with exactly TEST_OK"}],
            temperature=0,
            max_tokens=3200,
        )
    )

    assert result == "TEST_OK"
    assert captured["json"]["max_tokens"] == 4096


def test_gpt_oss_groq_practice_assessment_uses_medium_reasoning(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "groq-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    get_settings.cache_clear()

    captured: dict[str, object] = {}

    class _Resp:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": '{"status":"correct","response_vi":"OK"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            }

    def fake_post(url, json=None, headers=None, timeout=None):
        captured["json"] = json
        return _Resp()

    monkeypatch.setattr(requests, "post", fake_post)

    client = GroqLLMClient()
    result = _run(
        client.generate_chat_completion(
            [
                {
                    "role": "system",
                    "content": "Return only valid JSON with keys: status, response_vi, corrected_text",
                },
                {
                    "role": "user",
                    "content": "Latest learner message:\nShe are hungry, so she gets a pancake.",
                },
            ],
            temperature=0.2,
            max_tokens=500,
        )
    )

    assert '"status":"correct"' in result
    assert captured["json"]["include_reasoning"] is False
    assert captured["json"]["reasoning_effort"] == "medium"


def test_global_output_floor_applies_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    get_settings.cache_clear()

    client = GeminiLLMClient()
    payload = client._messages_to_payload(
        [{"role": "user", "content": "Say hello"}],
        temperature=0.2,
        max_tokens=20,
    )

    assert payload["generationConfig"]["maxOutputTokens"] == 1600


def test_gemini_practice_assessment_enables_small_thinking_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gem-key")
    get_settings.cache_clear()

    client = GeminiLLMClient()
    payload = client._messages_to_payload(
        [
            {
                "role": "system",
                "content": "Return only valid JSON with keys: status, response_vi, corrected_text",
            },
            {
                "role": "user",
                "content": "Latest learner message:\nShe are hungry, so she gets a pancake.",
            },
        ],
        temperature=0.2,
        max_tokens=500,
    )

    assert payload["generationConfig"]["maxOutputTokens"] == 5000
    assert llm_module._gemini_thinking_budget_for_messages(
        [
            {
                "role": "system",
                "content": "Return only valid JSON with keys: status, response_vi, corrected_text",
            }
        ]
    ) == 128


def test_output_token_multiplier_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LLM_OUTPUT_TOKENS_MULTIPLIER", "3")
    get_settings.cache_clear()

    assert llm_module._normalize_output_tokens(500) == 1500


def test_groq_rotates_to_backup_key_on_429(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "primary-key")
    monkeypatch.setenv("GROQ_API_KEY_1", "backup-key")
    monkeypatch.setenv("GROQ_MODEL", "openai/gpt-oss-20b")
    get_settings.cache_clear()

    seen_auth_headers: list[str] = []

    class _Resp:
        def __init__(self, status_code: int, body: dict[str, object]):
            self.status_code = status_code
            self._body = body

        def raise_for_status(self):
            if self.status_code >= 400:
                raise requests.exceptions.HTTPError(response=self)

        def json(self):
            return self._body

    def fake_post(url, json=None, headers=None, timeout=None):
        seen_auth_headers.append(headers["Authorization"])
        if len(seen_auth_headers) == 1:
            return _Resp(429, {"error": {"message": "rate limit"}})
        return _Resp(
            200,
            {
                "choices": [{"message": {"content": "TEST_OK"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    monkeypatch.setattr(requests, "post", fake_post)

    client = GroqLLMClient()
    result = _run(
        client.generate_chat_completion(
            [{"role": "user", "content": "Reply with exactly TEST_OK"}],
            temperature=0,
            max_tokens=20,
        )
    )

    assert result == "TEST_OK"
    assert seen_auth_headers == ["Bearer primary-key", "Bearer backup-key"]
