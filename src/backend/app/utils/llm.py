from __future__ import annotations

import asyncio
import contextvars
import json
import logging
import os
import random
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

import requests

from ..core.config import Settings, get_settings
from ..core import llm_costs


logger = logging.getLogger(__name__)
_LLM_REQUEST_TIMEOUT_SECONDS = 18
_MIN_OUTPUT_TOKENS = 160
_DEFAULT_OUTPUT_TOKENS_MULTIPLIER = 10


# Per-call latency, captured by the providers via `time.perf_counter()` and
# passed through ``_record_usage``. Cost tracer logs whatever was provided;
# 0.0 is acceptable for the mock/guardrail short-circuit branches.


class GeminiSafetyBlocked(RuntimeError):
    """Raised when Gemini's safetySettings filter blocks a prompt or response.

    Distinct from generic ``RuntimeError`` so the retry loop can short-
    circuit instead of burning attempts on a deterministic block.
    """


# Per-request usage accumulator. Set by chat.py via `start_usage_tracking()`
# and inspected at the end of the request. None means tracking is disabled
# (e.g. background jobs, tests). Using contextvars keeps concurrent FastAPI
# requests isolated automatically.
_usage_ctx: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "_llm_usage_ctx", default=None
)


def start_usage_tracking() -> dict[str, Any]:
    """Reset and install a fresh usage accumulator for the current task."""
    bucket: dict[str, Any] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "calls": 0,
        "provider": None,
        "model": None,
    }
    _usage_ctx.set(bucket)
    return bucket


def _record_usage(
    provider: str,
    model: str | None,
    prompt: int,
    completion: int,
    *,
    caller: str = "backend.llm",
    latency_ms: float = 0.0,
    status: str = "ok",
    error: str | None = None,
) -> None:
    """Record one LLM call to both the in-request context bucket *and* the
    cost JSONL. The cost row is the durable source of truth; the bucket is a
    per-request hotpath cache surfaced to the response/admin endpoints.
    """
    bucket = _usage_ctx.get()
    if bucket is not None:
        bucket["prompt_tokens"] += prompt
        bucket["completion_tokens"] += completion
        bucket["calls"] += 1
        # Last-write-wins for provider/model (keep what actually answered the user).
        bucket["provider"] = provider
        if model:
            bucket["model"] = model

    try:
        llm_costs.record_call(
            provider=provider,
            model=model,
            caller=caller,
            prompt_tokens=prompt,
            completion_tokens=completion,
            latency_ms=latency_ms,
            status=status,
            error=error,
        )
    except Exception:  # pragma: no cover — never let observability break the path
        logger.exception("llm_costs.record_call failed")


def _latest_user_message(messages: list[dict[str, Any]]) -> str:
    for message in reversed(messages):
        if str(message.get("role", "user")).lower() == "user":
            return str(message.get("content", "")).strip()
    return ""


def _extract_classification_subject(prompt: str) -> str:
    match = re.search(r"user message\s*:\s*(.+)$", prompt, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()
    return prompt.strip()


def _fallback_user_facing_response(prompt: str) -> str | None:
    lower = prompt.lower()
    if (
        "write one short, friendly vietnamese reply for an english-learning app." in lower
        and "the learner cannot move to the next lesson yet because the current lesson is unfinished" in lower
    ):
        return (
            "Bạn vẫn đang học dở bài hiện tại. Mình có thể mở lại để bạn học tiếp,"
            " hoặc nếu muốn qua bài mới thì hãy nói \"bỏ qua bài này\" nhé."
        )
    return None


def _fallback_intent_for_text(text: str) -> str:
    lower = text.lower().strip()
    normalized = lower.replace("đ", "d")
    normalized = unicodedata.normalize("NFD", normalized)
    normalized = "".join(char for char in normalized if unicodedata.category(char) != "Mn")
    _ = normalized
    return "ENGLISH_RAG"


def _looks_like_progress_request(lower: str, normalized: str) -> bool:
    progress_markers = (
        "progress",
        "tien do",
        "tiến độ",
        "stats",
        "statistics",
        "accuracy",
        "history",
        "performance",
        "current level",
        "my level",
        "review stats",
        "how am i doing",
        "how did i do",
        "hoc toi dau",
        "học tới đâu",
    )
    if any(marker in lower or marker in normalized for marker in progress_markers):
        return True
    return bool(re.search(r"\b(my|current|latest|this week|weekly)\s+(score|scores)\b", lower))


def _looks_like_sentence_check(text: str, normalized: str) -> bool:
    if not any(
        marker in normalized
        for marker in (
            "dung chua",
            "co dung khong",
            "sai khong",
            "sua cau",
            "kiem tra cau",
            "check cau",
            "correct this",
            "is this correct",
        )
    ):
        return False
    return bool(
        re.search(r'"[^"]*[A-Za-z][^"]*"', text)
        or re.search(r"'[^']*[A-Za-z][^']*'", text)
        or re.search(r"\b[A-Z][A-Za-z']+\s+[A-Za-z']+\b", text)
    )


def _looks_like_english_practice_attempt(text: str) -> bool:
    stripped = text.strip()
    if not re.search(r"[A-Za-z]", stripped):
        return False
    if stripped.endswith("?"):
        return False
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", stripped)
    if len(words) < 3:
        return False
    question_starts = {"what", "how", "why", "when", "where", "who", "whom", "is", "are", "can", "do", "does", "should"}
    return words[0].lower() not in question_starts


def _looks_like_groq_model(model: str | None) -> bool:
    candidate = (model or "").strip().lower()
    if not candidate:
        return False
    if "/" in candidate:
        return True
    return candidate.startswith(
        (
            "openai/gpt-oss",
            "llama-",
            "meta-llama",
            "mixtral",
            "mistral",
            "qwen",
            "gemma",
            "deepseek",
        )
    )


def _resolve_groq_model(settings, explicit_model: str | None) -> str:
    if explicit_model:
        return explicit_model

    fields_set = getattr(settings, "model_fields_set", set())
    groq_model = (settings.GROQ_MODEL or "").strip()
    if "GROQ_MODEL" in fields_set and groq_model:
        return groq_model

    llm_model = (settings.LLM_MODEL or "").strip()
    if _looks_like_groq_model(llm_model):
        return llm_model

    return groq_model


def _is_groq_reasoning_model(model: str | None) -> bool:
    candidate = (model or "").strip().lower()
    return candidate.startswith("openai/gpt-oss")


def _normalize_output_tokens(max_tokens: int) -> int:
    settings = get_settings()
    multiplier = int(
        getattr(settings, "LLM_OUTPUT_TOKENS_MULTIPLIER", _DEFAULT_OUTPUT_TOKENS_MULTIPLIER)
        or _DEFAULT_OUTPUT_TOKENS_MULTIPLIER
    )
    multiplier = max(multiplier, 1)
    base_tokens = max(int(max_tokens or 0), _MIN_OUTPUT_TOKENS)
    return base_tokens * multiplier


def _normalize_groq_output_tokens(max_tokens: int) -> int:
    settings = get_settings()
    cap = max(int(getattr(settings, "GROQ_MAX_OUTPUT_TOKENS", 4096) or 4096), _MIN_OUTPUT_TOKENS)
    return min(_normalize_output_tokens(max_tokens), cap)


def _looks_like_practice_assessment(messages: list[dict[str, Any]]) -> bool:
    for message in messages:
        content = str(message.get("content") or "")
        if "Return only valid JSON with keys: status, response_vi, corrected_text" in content:
            return True
        if "Latest learner message:" in content and "Personal recurring errors" in content:
            return True
    return False


def _groq_reasoning_effort_for_messages(messages: list[dict[str, Any]]) -> str:
    return "medium" if _looks_like_practice_assessment(messages) else "low"


def _gemini_thinking_budget_for_messages(messages: list[dict[str, Any]]) -> int:
    return 128 if _looks_like_practice_assessment(messages) else 0


def _collect_groq_api_keys(settings: Settings) -> list[str]:
    raw_keys: list[str] = []
    for attr in ("GROQ_API_KEY", "GROQ_API_KEY_1", "GROQ_API_KEY_2"):
        value = str(getattr(settings, attr, "") or "").strip()
        if value:
            raw_keys.append(value)

    numbered: list[tuple[int, str]] = []
    for key, value in os.environ.items():
        if not key.startswith("GROQ_API_KEY_"):
            continue
        suffix = key[len("GROQ_API_KEY_") :]
        if not suffix.isdigit():
            continue
        cleaned = str(value or "").strip()
        if cleaned:
            numbered.append((int(suffix), cleaned))

    raw_keys.extend(value for _, value in sorted(numbered))

    seen: set[str] = set()
    ordered: list[str] = []
    for value in raw_keys:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


class GroqLLMClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.api_keys = [api_key] if api_key else _collect_groq_api_keys(settings)
        self._key_index = 0
        self.api_key = self.api_keys[0] if self.api_keys else ""
        self.model = _resolve_groq_model(settings, model)
        self.base_url = "https://api.groq.com/openai/v1"
        self.last_provider = "uninitialized"
        # {"prompt_tokens": int, "completion_tokens": int}; reset every call.
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        self.last_model: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _rotate_key(self) -> bool:
        if self._key_index + 1 >= len(self.api_keys):
            return False
        self._key_index += 1
        self.api_key = self.api_keys[self._key_index]
        return True

    def _fallback_response(self, messages: list[dict[str, Any]]) -> str:
        prompt = _latest_user_message(messages)
        lower = prompt.lower()
        # detect classification prompts more robustly (e.g. "Classify the user's intent ...")
        if "classify" in lower and "intent" in lower:
            return _fallback_intent_for_text(_extract_classification_subject(prompt))
        if user_facing := _fallback_user_facing_response(prompt):
            return user_facing
        if "hint" in lower:
            return "Hãy nhìn vào từ khóa chính trong câu và kiểm tra xem nó có đúng sắc thái nghĩa trong ngữ cảnh không."
        if prompt.strip():
            return f"Mình đã nhận câu của bạn: {prompt.strip()[:160]}"
        return "Mình chưa nhận được nội dung hợp lệ."

    def _request_once(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": _normalize_groq_output_tokens(max_tokens),
        }
        if _is_groq_reasoning_model(self.model):
            # GPT-OSS spends part of the completion budget on hidden reasoning
            # even when `message.reasoning` is omitted. Hide the reasoning
            # from the response, but allow a little more effort for practice
            # assessment prompts where generic one-line feedback hurts UX.
            payload["include_reasoning"] = False
            payload["reasoning_effort"] = _groq_reasoning_effort_for_messages(messages)

        payload_chars = len(json.dumps(payload, ensure_ascii=False, default=str))
        logger.debug(
            "groq.request model=%s messages=%s payload_chars=%s max_tokens=%s",
            self.model,
            len(messages),
            payload_chars,
            payload["max_tokens"],
        )
        response = requests.post(url, json=payload, headers=headers, timeout=_LLM_REQUEST_TIMEOUT_SECONDS)
        response.raise_for_status()
        body = response.json()

        choices = body.get("choices") or []
        if not choices:
            raise RuntimeError("Groq returned no choices")

        text = choices[0].get("message", {}).get("content", "").strip()
        if not text:
            raise RuntimeError("Groq returned an empty response")

        usage = body.get("usage") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(usage.get("completion_tokens", 0) or 0),
        }
        self.last_model = self.model
        return text

    async def generate_chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        if not self.enabled:
            self.last_provider = "mock"
            text = self._fallback_response(messages)
            _record_usage("mock", None, 0, 0)
            return text

        last_error: Exception | None = None
        max_attempts = max(2, len(self.api_keys) + 1)
        for attempt in range(max_attempts):
            t0 = time.perf_counter()
            try:
                text = await asyncio.to_thread(self._request_once, messages, temperature, max_tokens)
                self.last_provider = "groq"
                _record_usage(
                    "groq",
                    self.last_model,
                    self.last_usage.get("prompt_tokens", 0),
                    self.last_usage.get("completion_tokens", 0),
                    caller="backend.chat:groq",
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                )
                return text
            except requests.exceptions.HTTPError as exc:
                last_error = exc
                status_code = exc.response.status_code
                if status_code in {401, 403, 429} and self._rotate_key():
                    logger.warning(
                        "Groq request failed with status=%s on key_index=%s; rotating to backup key_index=%s",
                        status_code,
                        self._key_index - 1,
                        self._key_index,
                    )
                    continue
                retryable = status_code == 429 or 500 <= status_code < 600
                if not retryable or attempt == max_attempts - 1:
                    break
            except Exception as exc:  # pragma: no cover - transient network fallback
                last_error = exc
                if attempt == max_attempts - 1:
                    break

            await asyncio.sleep((2**attempt) + random.random() * 0.25)

        logger.warning("Groq request failed: %s, checking Gemini fallback", last_error)
        gemini = GeminiLLMClient(settings=get_settings())
        if gemini.enabled:
            logger.warning("Groq request failed (%s), falling back to Gemini", last_error)
            text = await gemini.generate_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
            self.last_provider = gemini.last_provider
            self.last_usage = dict(gemini.last_usage)
            self.last_model = gemini.last_model
            return text

        logger.warning("Groq request failed and Gemini is unavailable, falling back to mock response: %s", last_error)
        self.last_provider = "mock"
        text = self._fallback_response(messages)
        _record_usage(
            "mock",
            None,
            0,
            0,
            caller="backend.chat:mock",
            status="error",
            error=str(last_error)[:200] if last_error else None,
        )
        return text

    async def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        return await self.generate_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)


def _pick_gemini_key(settings: Settings | None = None) -> str:
    """Return the first usable Gemini credential.

    Why this exists: two distinct credential formats coexist in the wild —
    classic API keys (``AIzaSy...``) which the ``?key=`` REST param accepts,
    and short-lived OAuth tokens (``AQ.Ab...``) issued by gcloud / Workload
    Identity which the SDK auto-detects and sends as ``Authorization:
    Bearer``. We prefer ``GOOGLE_API_KEY`` when it carries the OAuth prefix
    (since that's the actually-working credential in the current GCP project
    after the legacy ``AIzaSy`` key was blocked at the org level).
    """
    s = settings or get_settings()
    if s.GOOGLE_API_KEY and s.GOOGLE_API_KEY.startswith("AQ."):
        return s.GOOGLE_API_KEY
    return s.GEMINI_API_KEY or s.GOOGLE_API_KEY or ""


class GeminiLLMClient:
    """Gemini client backed by the ``google-genai`` SDK.

    The SDK transparently handles both ``AIzaSy...`` keys (Dev API
    ``?key=``) and ``AQ.Ab...`` OAuth tokens (Bearer), which is why we use
    it instead of the prior urllib direct-HTTP implementation: direct HTTP
    silently 401s for OAuth tokens.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        *,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        self.api_key = api_key or _pick_gemini_key(settings)
        self.model = model or settings.LLM_MODEL
        self.last_provider = "uninitialized"
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}
        self.last_model: str | None = None
        self._client: Any = None  # google.genai.Client, lazy init

    def _genai_client(self) -> Any:
        if self._client is None:
            from google import genai  # local import keeps import time low
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def count_tokens(self, text: str) -> int:
        """Lightweight estimate; Gemini token counting is not exposed here."""
        return max(1, len(text.strip()) // 4) if text.strip() else 0

    def _messages_to_payload(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int) -> dict[str, Any]:
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []

        for message in messages:
            role = (message.get("role") or "user").lower()
            content = message.get("content") or ""
            if not content:
                continue
            if role == "system":
                system_parts.append(str(content))
                continue
            gemini_role = "user" if role in {"user", "tool"} else "model"
            contents.append({"role": gemini_role, "parts": [{"text": str(content)}]})

        # Provider-level guardrail (L1). Apply Google's content filters
        # explicitly so behaviour is deterministic across regions/models —
        # the API default differs by model family and has changed between
        # Gemini 1.5 and 2.5 lines.
        settings = get_settings()
        threshold = (settings.GEMINI_SAFETY_THRESHOLD or "BLOCK_MEDIUM_AND_ABOVE").upper()
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": threshold},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": threshold},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": threshold},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": threshold},
        ]

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": _normalize_output_tokens(max_tokens),
            },
            "safetySettings": safety_settings,
        }

        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}

        return payload

    def _should_try_vertex_first(self) -> bool:
        return bool(self.api_key and self.api_key.startswith("AQ."))

    def _vertex_host(self) -> str:
        location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip() or "us-central1"
        if location == "global":
            return "https://aiplatform.googleapis.com"
        return f"https://{location}-aiplatform.googleapis.com"

    def _vertex_model_path(self) -> str:
        project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
        location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip() or "us-central1"
        if project:
            return f"projects/{project}/locations/{location}/publishers/google/models/{self.model}"
        return f"publishers/google/models/{self.model}"

    def _request_once_vertex(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int) -> str:
        payload = self._messages_to_payload(messages, temperature=temperature, max_tokens=max_tokens)
        generation_config = dict(payload.get("generationConfig") or {})
        # Gemini 2.5 can waste the full budget on hidden thinking for short
        # turns, but fully disabling it also makes grammar assessment terse.
        generation_config["thinkingConfig"] = {
            "thinkingBudget": _gemini_thinking_budget_for_messages(messages)
        }
        payload["generationConfig"] = generation_config

        response = requests.post(
            f"{self._vertex_host()}/v1/{self._vertex_model_path()}:generateContent",
            params={"key": self.api_key},
            json=payload,
            timeout=_LLM_REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        body = response.json()

        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError("Vertex Gemini returned no candidates")

        first = candidates[0]
        finish_reason = str(first.get("finishReason", "") or "").upper()
        if finish_reason.endswith("SAFETY"):
            raise GeminiSafetyBlocked("response blocked: SAFETY")

        content = first.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(str(part.get("text", "")) for part in parts if part.get("text")).strip()
        if not text:
            raise RuntimeError(f"Vertex Gemini returned empty text (finish_reason={finish_reason or 'UNKNOWN'})")

        usage = body.get("usageMetadata") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("promptTokenCount", 0) or 0),
            "completion_tokens": int(usage.get("candidatesTokenCount", 0) or 0),
        }
        self.last_model = body.get("modelVersion") or self.model
        return text

    def _fallback_response(self, messages: list[dict[str, Any]]) -> str:
        prompt = _latest_user_message(messages)
        lower = prompt.lower()

        # If this is a classification-style prompt, return a single token fallback
        if "classify" in lower and "intent" in lower:
            return _fallback_intent_for_text(_extract_classification_subject(prompt))
        if user_facing := _fallback_user_facing_response(prompt):
            return user_facing

        if "hint" in lower:
            return "Hãy nhìn vào từ khóa chính trong câu và kiểm tra xem nó có đúng sắc thái nghĩa trong ngữ cảnh không."
        if prompt.strip():
            return f"Mình đã nhận câu của bạn: {prompt.strip()[:160]}"
        return "Mình chưa nhận được nội dung hợp lệ."

    def _request_once(self, messages: list[dict[str, Any]], temperature: float, max_tokens: int) -> str:
        if self._should_try_vertex_first():
            try:
                return self._request_once_vertex(messages, temperature, max_tokens)
            except Exception as exc:
                logger.warning("Vertex Gemini request failed, falling back to legacy Gemini SDK: %s", exc)

        from google.genai import types as gtypes  # local import — cheap after first call

        # Reuse the existing role/system normalisation, then translate into the
        # SDK's typed objects. We don't reuse the urllib payload structure
        # because the SDK accepts a higher-level shape and handles safety
        # settings explicitly.
        rest_payload = self._messages_to_payload(messages, temperature=temperature, max_tokens=max_tokens)
        contents: list[Any] = []
        for c in rest_payload.get("contents", []):
            parts = [gtypes.Part(text=p.get("text", "")) for p in c.get("parts", [])]
            contents.append(gtypes.Content(role=c.get("role", "user"), parts=parts))

        cfg_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": _normalize_output_tokens(max_tokens),
            "safety_settings": [
                gtypes.SafetySetting(category=s["category"], threshold=s["threshold"])
                for s in rest_payload.get("safetySettings", [])
            ],
        }
        if hasattr(gtypes, "ThinkingConfig"):
            cfg_kwargs["thinking_config"] = gtypes.ThinkingConfig(
                thinking_budget=_gemini_thinking_budget_for_messages(messages)
            )
        gen_cfg = gtypes.GenerateContentConfig(**cfg_kwargs)
        sys_inst = rest_payload.get("systemInstruction")
        if sys_inst and sys_inst.get("parts"):
            gen_cfg.system_instruction = sys_inst["parts"][0].get("text", "")

        try:
            response = self._genai_client().models.generate_content(
                model=self.model, contents=contents, config=gen_cfg
            )
        except Exception as exc:
            # The SDK surfaces both transport errors and API errors via its
            # ClientError hierarchy. We re-raise so the outer retry loop can
            # decide whether to back off; safety blocks come through as
            # ``finish_reason='SAFETY'`` on the response below, not here.
            raise

        # Safety / block surfacing — the SDK populates ``prompt_feedback``
        # only when the *prompt* was blocked; ``finish_reason`` is on the
        # candidate when the *response* was blocked.
        pf = getattr(response, "prompt_feedback", None)
        if pf and getattr(pf, "block_reason", None):
            raise GeminiSafetyBlocked(f"prompt blocked: {pf.block_reason}")

        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            raise RuntimeError("Gemini returned no candidates")
        if str(getattr(candidates[0], "finish_reason", "")).upper().endswith("SAFETY"):
            raise GeminiSafetyBlocked("response blocked: SAFETY")

        text = (response.text or "").strip()
        if not text:
            raise RuntimeError("Gemini returned an empty response")

        usage = getattr(response, "usage_metadata", None)
        self.last_usage = {
            "prompt_tokens": int(getattr(usage, "prompt_token_count", 0) or 0),
            "completion_tokens": int(getattr(usage, "candidates_token_count", 0) or 0),
        }
        self.last_model = self.model
        return text

    async def generate_chat_completion(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        if not self.enabled:
            groq = GroqLLMClient()
            if groq.enabled:
                logger.info("Gemini not available, falling back to Groq")
                text = await groq.generate_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
                self.last_provider = groq.last_provider
                self.last_usage = dict(groq.last_usage)
                self.last_model = groq.last_model
                return text
            self.last_provider = "mock"
            text = self._fallback_response(messages)
            _record_usage("mock", None, 0, 0, caller="backend.chat:mock", status="error", error="gemini-disabled")
            return text

        last_error: Exception | None = None
        for attempt in range(2):
            t0 = time.perf_counter()
            try:
                text = await asyncio.to_thread(self._request_once, messages, temperature, max_tokens)
                self.last_provider = "gemini"
                _record_usage(
                    "gemini",
                    self.last_model,
                    self.last_usage.get("prompt_tokens", 0),
                    self.last_usage.get("completion_tokens", 0),
                    caller="backend.chat:gemini",
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                )
                return text
            except GeminiSafetyBlocked as exc:
                # Deterministic block — don't retry, don't fall through to
                # Groq (it would likely just produce content we'd then have
                # to filter again). Return the canned guardrail message.
                logger.warning("Gemini safety block: %s", exc)
                self.last_provider = "guardrail"
                _record_usage(
                    "guardrail",
                    self.last_model,
                    0,
                    0,
                    caller="backend.chat:guardrail",
                    latency_ms=(time.perf_counter() - t0) * 1000.0,
                    status="blocked",
                    error=str(exc)[:200],
                )
                from ..services.guardrails import SAFE_REJECTION_MESSAGE
                return SAFE_REJECTION_MESSAGE
            except Exception as exc:
                # ``google.genai`` raises ClientError / ServerError with a
                # ``.code`` attribute (HTTP status). Retry on 429 / 5xx, give
                # up on auth (401/403) and validation errors immediately so
                # we don't burn the retry budget on a deterministic failure.
                last_error = exc
                if isinstance(exc, GeminiSafetyBlocked):
                    raise
                code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
                retryable = code in (None, 429) or (isinstance(code, int) and 500 <= code < 600)
                if not retryable or attempt == 1:
                    break

            await asyncio.sleep((2**attempt) + random.random() * 0.25)

        groq = GroqLLMClient()
        if groq.enabled:
            logger.warning("Gemini request failed (%s), falling back to Groq", last_error)
            text = await groq.generate_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)
            self.last_provider = groq.last_provider
            self.last_usage = dict(groq.last_usage)
            self.last_model = groq.last_model
            return text
        logger.warning("Gemini request failed, using fallback response: %s", last_error)
        self.last_provider = "mock"
        text = self._fallback_response(messages)
        _record_usage(
            "mock",
            None,
            0,
            0,
            caller="backend.chat:mock",
            status="error",
            error=str(last_error)[:200] if last_error else None,
        )
        return text

    async def generate(
        self,
        messages: list[dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 500,
    ) -> str:
        return await self.generate_chat_completion(messages, temperature=temperature, max_tokens=max_tokens)


_llm_client: GeminiLLMClient | GroqLLMClient | None = None
_llm_client_signature: tuple[str, str, str, str] | None = None


def _load_live_settings() -> Settings:
    """Read the latest env-backed settings without relying on the global cache.

    `get_settings()` is intentionally cached for hot paths, but that also means
    a long-lived process can keep using an empty/stale LLM key after `.env` or
    injected env vars have changed. The chat LLM singleton therefore refreshes
    itself from a live Settings instance.
    """
    return Settings()


def _client_signature(provider: str, settings: Settings) -> tuple[str, str, str, str]:
    if provider == "groq":
        groq_keys = "|".join(_collect_groq_api_keys(settings))
        return (
            provider,
            groq_keys,
            _resolve_groq_model(settings, None),
            settings.LLM_MODEL,
        )
    return (
        provider,
        _pick_gemini_key(settings),
        settings.LLM_MODEL,
        settings.GROQ_API_KEY,
    )


def _build_llm_client(provider: str, settings: Settings) -> GeminiLLMClient | GroqLLMClient:
    if provider == "groq":
        groq = GroqLLMClient(model=_resolve_groq_model(settings, None), settings=settings)
        if groq.enabled:
            return groq
    return GeminiLLMClient(
        api_key=_pick_gemini_key(settings),
        model=settings.LLM_MODEL,
        settings=settings,
    )


def get_llm_client() -> GeminiLLMClient | GroqLLMClient:
    global _llm_client, _llm_client_signature
    provider = os.getenv("CHAT_LLM_PROVIDER", "gemini").strip().lower()
    settings = _load_live_settings()
    signature = _client_signature(provider, settings)

    if _llm_client is None or _llm_client_signature != signature:
        _llm_client = _build_llm_client(provider, settings)
        _llm_client_signature = signature
    return _llm_client
