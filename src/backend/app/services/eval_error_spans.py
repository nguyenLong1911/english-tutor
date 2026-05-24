from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Any

from ..models.processed_dataset_schemas import ChatRequest, ChatResponse
from ..utils.llm import get_llm_client, start_usage_tracking


logger = logging.getLogger(__name__)
EVAL_ERROR_SPANS_TYPE = "EVAL_ERROR_SPANS"
LIVE_EVAL_PROVIDERS = {"gemini", "groq"}


class LiveEvalProviderRequired(RuntimeError):
    pass


def is_error_span_eval(payload: ChatRequest) -> bool:
    return str(payload.type or "").strip().upper() == EVAL_ERROR_SPANS_TYPE


def extract_eval_sentence(message: str) -> str:
    text = str(message or "").strip()
    marker = "Learner sentence:"
    if marker.lower() in text.lower():
        match = re.search(r"learner sentence\s*:\s*(.+)\s*$", text, flags=re.IGNORECASE | re.DOTALL)
        if match:
            return match.group(1).strip()
    return text


def extract_json_string_array(text: str) -> list[str] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^`{1,3}(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*`{1,3}$", "", cleaned)

    candidates = [cleaned]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    if start != -1 and end > start:
        candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return [item.strip() for item in parsed if item.strip()]
    return None


async def run_error_span_eval(payload: ChatRequest, request: Any | None = None) -> ChatResponse:
    """Machine-readable eval path for offline benchmarks only.

    Product chat never sends ``type=EVAL_ERROR_SPANS``. Keeping this as a
    separate branch avoids perturbing LangGraph, memory writes, user sessions,
    learner-facing guardrails, or the Vietnamese UX prompt.
    """
    trace_id = str(getattr(getattr(request, "state", None), "trace_id", "") or uuid.uuid4())
    sentence = extract_eval_sentence(payload.message)
    messages = [
        {
            "role": "system",
            "content": (
                "You are an English grammar error-span detector for automated evaluation. "
                "Return only a JSON array of incorrect spans copied verbatim from the learner sentence. "
                "Do not explain, do not correct, and do not include replacements. "
                "If there are no errors, return []."
            ),
        },
        {"role": "user", "content": f"Learner sentence:\n{sentence}"},
    ]
    usage_bucket = start_usage_tracking()
    started_at = time.perf_counter()
    llm = get_llm_client()
    raw = await llm.generate_chat_completion(messages, temperature=0.0, max_tokens=700)
    provider = str(usage_bucket.get("provider") or getattr(llm, "last_provider", "") or "").lower()
    if provider not in LIVE_EVAL_PROVIDERS:
        raise LiveEvalProviderRequired(f"Evaluation requires a live LLM provider, got {provider or 'unknown'}")

    spans = extract_json_string_array(raw)
    response_text = json.dumps(spans if spans is not None else [], ensure_ascii=False)
    logger.info(
        "eval_error_spans_complete trace_id=%s user_id=%s provider=%s model=%s llm_calls=%s latency_ms=%s parsed=%s spans=%s",
        trace_id,
        payload.user_id,
        provider,
        usage_bucket.get("model") or getattr(llm, "last_model", None) or getattr(llm, "model", None),
        usage_bucket.get("calls", 0),
        int((time.perf_counter() - started_at) * 1000),
        spans is not None,
        len(spans or []),
    )
    return ChatResponse(response=response_text, hint_count=0, intent=EVAL_ERROR_SPANS_TYPE, session_id=None)
