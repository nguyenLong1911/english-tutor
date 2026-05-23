"""Constrained-decoding LLM client for the A20 data-pipeline.

Replaces the previous OpenAI-only implementation with a **Gemini-first**
client (using the official ``google-genai`` SDK) and an optional **Groq SDK**
fallback. The ``openai`` package is intentionally not imported.

Provider selection (first available wins):
1. ``A20_LLM_PROVIDER`` env (``gemini`` | ``groq`` | ``vertex``) — explicit pin.
2. Vertex AI via ``GOOGLE_GENAI_USE_VERTEXAI=True`` + ``GOOGLE_API_KEY``.
3. Gemini Developer API via ``GEMINI_API_KEY``.
4. Groq via ``GROQ_API_KEY``.

Each call is wrapped in :func:`observability.trace_call` so prompt/completion
tokens, latency and cost USD are persisted to JSONL.

Schema enforcement: the JSON response is parsed manually with
``pydantic.model_validate_json``. When Gemini is used we additionally pass
``response_mime_type="application/json"`` and the schema as a JSON-mode hint
to anchor the model into well-formed JSON.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Type, TypeVar

from pydantic import BaseModel, ValidationError

from .observability import trace_call
from .retry import RetryConfig, retry_transient

log = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


# ---------------------------------------------------------------------------
# Provider implementations
# ---------------------------------------------------------------------------


class _GeminiBackend:
    """``google-genai`` SDK backend. Handles both Dev API and Vertex modes."""

    def __init__(self, model: str, api_key: str | None, temperature: float, use_vertex: bool) -> None:
        from google import genai  # local import — keeps cold path light

        self.model = model
        self.temperature = temperature
        self.provider = "gemini"
        if use_vertex:
            kwargs: dict[str, Any] = {"vertexai": True}
            if api_key:
                kwargs["api_key"] = api_key
            else:
                kwargs["project"] = os.getenv("GOOGLE_CLOUD_PROJECT")
                kwargs["location"] = os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1"
            self.client = genai.Client(**kwargs)
        else:
            self.client = genai.Client(api_key=api_key)

    def chat_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> tuple[T, dict[str, int]]:
        from google.genai import types as gtypes  # local import

        contents = [
            gtypes.Content(role="user", parts=[gtypes.Part(text=user_prompt)]),
        ]
        config = gtypes.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_schema=_pydantic_to_genai_schema(schema),
        )
        with trace_call(provider=self.provider, model=self.model, caller="data_pipeline.synth") as ctx:
            resp = self.client.models.generate_content(
                model=self.model, contents=contents, config=config
            )
            text = resp.text or "{}"
            usage = resp.usage_metadata
            ctx["prompt_tokens"] = getattr(usage, "prompt_token_count", 0) or 0
            ctx["completion_tokens"] = getattr(usage, "candidates_token_count", 0) or 0
            tokens = {
                "prompt_tokens": ctx["prompt_tokens"],
                "completion_tokens": ctx["completion_tokens"],
            }
        return schema.model_validate_json(text), tokens


class _GroqBackend:
    """``groq`` Python SDK backend (no openai package)."""

    def __init__(self, model: str, api_key: str, temperature: float) -> None:
        from groq import Groq  # local import

        self.model = model
        self.temperature = temperature
        self.provider = "groq"
        self.client = Groq(api_key=api_key)

    def chat_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> tuple[T, dict[str, int]]:
        with trace_call(provider=self.provider, model=self.model, caller="data_pipeline.synth") as ctx:
            resp = self.client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            text = resp.choices[0].message.content or "{}"
            usage = resp.usage
            ctx["prompt_tokens"] = getattr(usage, "prompt_tokens", 0) or 0
            ctx["completion_tokens"] = getattr(usage, "completion_tokens", 0) or 0
            tokens = {
                "prompt_tokens": ctx["prompt_tokens"],
                "completion_tokens": ctx["completion_tokens"],
            }
        return schema.model_validate_json(text), tokens


# ---------------------------------------------------------------------------
# Schema helper — Pydantic → google-genai response_schema
# ---------------------------------------------------------------------------


def _pydantic_to_genai_schema(schema: Type[BaseModel]) -> Any:
    """Pass the raw Pydantic model class to google-genai.

    google-genai accepts a Pydantic class directly for ``response_schema`` and
    converts it internally. Returning the class avoids manual JSON-schema
    massaging (which is brittle across SDK versions).
    """
    return schema


# ---------------------------------------------------------------------------
# Public client
# ---------------------------------------------------------------------------


class StructuredLLM:
    """Provider-agnostic structured-output client with self-repair on validation.

    Public API matches the previous OpenAI-backed implementation so callers
    (``synthetic.py``, ``generate.py``) need no changes.
    """

    def __init__(
        self,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float = 0.4,
        retry_config: RetryConfig | None = None,
        provider: str | None = None,
    ) -> None:
        self.temperature = temperature
        self._retry = retry_config or RetryConfig()
        self._backend = _select_backend(
            model=model,
            api_key=api_key,
            temperature=temperature,
            forced_provider=provider or os.getenv("A20_LLM_PROVIDER"),
        )
        self.model = self._backend.model
        self.provider = self._backend.provider
        log.info("StructuredLLM ready: provider=%s model=%s", self.provider, self.model)

    # ---------------------------------------------------------------- core
    def parse(
        self,
        system_prompt: str,
        user_prompt: str,
        schema: Type[T],
        *,
        max_repair_attempts: int = 1,
    ) -> T:
        @retry_transient(self._retry)
        def _call(sys_p: str, usr_p: str) -> T:
            obj, _tokens = self._backend.chat_json(sys_p, usr_p, schema)
            return obj

        try:
            return _call(system_prompt, user_prompt)
        except ValidationError as val_err:
            log.warning("Pydantic validation failed: %s", val_err)
            if max_repair_attempts <= 0:
                raise
            repair_user = (
                f"{user_prompt}\n\n"
                "Your previous output failed Pydantic validation with these errors:\n"
                f"{val_err}\n\n"
                "Re-emit ONLY a JSON object that conforms strictly to the schema. "
                "Do not include markdown fences or commentary."
            )
            return _call(system_prompt, repair_user)

    def parse_json(self, system_prompt: str, user_prompt: str, schema: Type[T]) -> T:
        return self.parse(system_prompt, user_prompt, schema)


# ---------------------------------------------------------------------------
# Backend selection
# ---------------------------------------------------------------------------


def _select_backend(
    *,
    model: str | None,
    api_key: str | None,
    temperature: float,
    forced_provider: str | None,
) -> _GeminiBackend | _GroqBackend:
    """Pick the first usable backend per the rules in this module's docstring."""

    use_vertex = (os.getenv("GOOGLE_GENAI_USE_VERTEXAI") or "").strip().lower() in {"1", "true", "yes"}
    vertex_key = api_key or os.getenv("GOOGLE_API_KEY")
    gemini_key = api_key or os.getenv("GEMINI_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")

    want = (forced_provider or "").strip().lower() or None

    if want in {"vertex", "google"} or (want is None and use_vertex):
        try:
            chosen_model = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
            return _GeminiBackend(
                model=chosen_model,
                api_key=vertex_key,
                temperature=temperature,
                use_vertex=True,
            )
        except Exception as exc:
            log.warning("Vertex backend init failed (%s).", exc)
            raise

    if want in {"gemini"} or (want is None and gemini_key):
        try:
            chosen_model = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
            return _GeminiBackend(
                model=chosen_model,
                api_key=gemini_key,
                temperature=temperature,
                use_vertex=False,
            )
        except Exception as exc:
            log.warning("Gemini backend init failed (%s); attempting Groq fallback.", exc)
            if want in {"gemini"}:
                raise

    if want in {"groq", None} and groq_key:
        chosen_model = model or os.getenv("GROQ_MODEL") or "llama-3.3-70b-versatile"
        return _GroqBackend(model=chosen_model, api_key=groq_key, temperature=temperature)

    raise RuntimeError(
        "No LLM provider available. Set GEMINI_API_KEY (Developer API) or "
        "GOOGLE_GENAI_USE_VERTEXAI=True with ADC, or GROQ_API_KEY as fallback."
    )
