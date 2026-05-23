"""LLM safety guardrails (input + output) for the chat pipeline.

Two lightweight, pure-Python LangGraph nodes:

- ``input_guard``  — scans ``state["user_input"]`` for prompt-injection /
  jailbreak attempts (OWASP LLM01). On a hit it sets
  ``state["guardrail_blocked"] = True`` and pre-fills a safe response;
  the orchestrator's conditional edge then jumps straight to
  ``output_guard`` so no LLM/Mem0 calls happen.

- ``output_guard`` — scans ``state["response"]`` for leaked system
  prompts and identity/provider leaks. User-facing content is preserved
  verbatim; PII redaction helpers remain available for offline use but
  are no longer applied to normal chat responses.

Heavier moderation (Google's content filters) lives at the provider
layer in :mod:`app.utils.llm` via Gemini ``safetySettings``. Both layers
are gated by config flags so they can be disabled in tests / scripts.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from ..core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompt-injection / jailbreak patterns. Compiled once at import time.
# Each entry targets a documented attack vector; keep this list curated —
# over-broad patterns produce false positives on legitimate study prompts
# (e.g. "ignore the comma" should NOT be blocked).
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"ignore\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions?|prompts?|rules?|directives?|messages?)",
        r"disregard\s+(?:all\s+|the\s+|your\s+)?(?:previous|prior|above|earlier|preceding)\s+(?:instructions?|prompts?|rules?)",
        r"forget\s+(?:everything|all|your\s+(?:instructions?|prompt|rules?|training))",
        r"reveal\s+(?:your\s+)?(?:full\s+|entire\s+)?(?:system\s+)?(?:prompt|instructions?|rules?)",
        r"(?:print|show|output|repeat|display)\s+(?:your\s+)?(?:full\s+|entire\s+)?(?:system\s+)?(?:prompt|instructions?)",
        r"(?:you\s+are\s+now|from\s+now\s+on\s+you\s+are|act\s+as|pretend\s+(?:you\s+are|to\s+be))\s+(?:a\s+|an\s+)?(?:dan|jailbroken|unrestricted|evil|developer\s+mode|do\s+anything\s+now)",
        r"(?:bypass|override|disable|turn\s+off)\s+(?:your\s+)?(?:safety|guardrails?|filters?|restrictions?|content\s+polic)",
        r"<\|im_(?:start|end)\|>",
        r"<<\s*sys\s*>>",
        r"\[INST\]",
        r"###\s*(?:system|instruction)\s*[:\n]",
    )
)


# ---------------------------------------------------------------------------
# PII patterns — helper-only. User input may contain PII legitimately
# (Context Injection §9.2 lets users paste business email). We keep the
# helper for offline scripts/tests, but the live chat path no longer
# rewrites learner-facing output spans.
# ---------------------------------------------------------------------------
_PII_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
        "[redacted-email]",
    ),
    (
        # Vietnamese phone: +84..., 84..., or 0... with 9-10 trailing digits.
        re.compile(r"(?<!\d)(?:\+?84|0)\d{9,10}(?!\d)"),
        "[redacted-phone]",
    ),
    (
        # Generic long numeric run (credit card / national id-ish). Crude on
        # purpose: we'd rather over-redact in LLM output than leak.
        re.compile(r"(?<!\d)\d{12,19}(?!\d)"),
        "[redacted-number]",
    ),
)


# Markers indicating the model parroted the system prompt back. Keep
# lower-case and short; we match against ``response.lower()``.
_SYSTEM_LEAK_MARKERS: tuple[str, ...] = (
    "you are a20 tutor",
    "you are an a20 tutor",
    "system prompt:",
    "[system]",
    "<<sys>>",
    "<|im_start|>system",
)


# Identity-leak patterns. The Luna persona forbids the model from
# disclosing which provider powers it, but smaller models (Groq's Llama
# fallback in particular) sometimes ignore the directive. This is the
# last-line defence: anything in the reply that names a known LLM /
# provider triggers a canned redirect. Word-boundaries so we don't trip
# on legitimate vocabulary teaching (e.g. "bard" the noun, "claude" as a
# French given name in an example sentence are unlikely but possible —
# accepted false-positive cost is low for a tutoring app).
_IDENTITY_LEAK_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\b(?:i\s+am|i'm|tôi\s+là|mình\s+là)\s+(?:a\s+|an\s+)?(?:large\s+language\s+model|llm|ai\s+model|chatbot)\b",
        r"\b(?:llama|llama-?\d|meta\s*ai|meta\s+llama)\b",
        r"\b(?:gemini(?:-\d[.\d]*)?|google\s+(?:bard|gemini)|bard\s+(?:by|from)\s+google)\b",
        r"\bgpt-?\d[.\d]*\b",
        r"\b(?:chatgpt|openai)\b",
        r"\b(?:claude(?:-\d[.\d]*)?|anthropic)\b",
        r"\b(?:groq(?:cloud)?|mistral(?:-\d[.\d]*)?)\b",
        r"\b(?:được\s+(?:phát\s+triển|tạo\s+ra|xây\s+dựng)\s+bởi)\s+(?:meta|google|openai|anthropic|groq|mistral)\b",
        r"\b(?:developed|created|built|trained)\s+by\s+(?:meta|google|openai|anthropic|groq|mistral)\b",
    )
)


SAFE_IDENTITY_REPLY = (
    "Mình là Luna — gia sư tiếng Anh của A20 Tutor. "
    "Mình chỉ hỗ trợ luyện tiếng Anh. Bạn muốn mình giúp gì với "
    "tiếng Anh hôm nay?"
)


def detect_identity_leak(text: str) -> str | None:
    """Return the first matching pattern source, or ``None`` if clean."""
    if not text:
        return None
    for pattern in _IDENTITY_LEAK_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


# Single canned reply for both injection blocks and system-leak blocks.
# Vietnamese to match the rest of the user-facing copy in the codebase.
SAFE_REJECTION_MESSAGE = (
    "Mình chỉ hỗ trợ luyện tiếng Anh theo phạm vi của A20 Tutor. "
    "Mình không thể làm theo yêu cầu thay đổi vai trò hoặc bỏ qua hướng "
    "dẫn hệ thống. Bạn muốn quay lại bài luyện gần nhất hay thử một câu mới?"
)


def detect_prompt_injection(text: str) -> str | None:
    """Return the matching pattern source, or ``None`` if input is clean.

    Exposed for unit tests and ad-hoc scripts; the LangGraph node uses
    this internally.
    """
    if not text:
        return None
    for pattern in _INJECTION_PATTERNS:
        if pattern.search(text):
            return pattern.pattern
    return None


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Apply PII regex replacements; return ``(cleaned, redaction_kinds)``."""
    if not text:
        return text, []
    redactions: list[str] = []
    out = text
    for pattern, replacement in _PII_PATTERNS:
        if pattern.search(out):
            redactions.append(replacement)
            out = pattern.sub(replacement, out)
    return out, redactions


def detect_system_leak(text: str) -> bool:
    if not text:
        return False
    low = text.lower()
    return any(marker in low for marker in _SYSTEM_LEAK_MARKERS)


# ---------------------------------------------------------------------------
# LangGraph nodes
# ---------------------------------------------------------------------------


async def input_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Pre-LLM guard: block prompt-injection attempts in ``user_input``."""
    settings = get_settings()
    if not settings.GUARDRAILS_ENABLED or not settings.GUARDRAILS_BLOCK_PROMPT_INJECTION:
        return state

    user_input = str(state.get("user_input") or "")
    matched = detect_prompt_injection(user_input)
    if matched is None:
        return state

    logger.warning(
        "guardrail.input_blocked user_id=%s reason=prompt_injection pattern=%r",
        state.get("user_id"),
        matched,
    )
    state["guardrail_blocked"] = True
    state["guardrail_reason"] = "prompt_injection"
    state["response"] = SAFE_REJECTION_MESSAGE
    # Keep the rest of the state shape valid for downstream serialisation.
    state.setdefault("intent", "ENGLISH_RAG")
    state.setdefault("hint_count", state.get("hint_count", 0))
    state.setdefault("new_facts", [])
    return state


async def output_guard(state: dict[str, Any]) -> dict[str, Any]:
    """Post-LLM guard: block system-prompt and identity leaks in reply."""
    settings = get_settings()
    if not settings.GUARDRAILS_ENABLED:
        return state

    response = str(state.get("response") or "")
    if not response:
        return state

    # If input_guard already short-circuited, the canned message is safe;
    # don't waste cycles on it.
    if state.get("guardrail_blocked"):
        return state

    if settings.GUARDRAILS_BLOCK_SYSTEM_LEAK and detect_system_leak(response):
        logger.warning(
            "guardrail.output_blocked user_id=%s reason=system_leak",
            state.get("user_id"),
        )
        state["response"] = SAFE_REJECTION_MESSAGE
        state["guardrail_output_action"] = "blocked_system_leak"
        return state

    # Identity-leak check: Luna persona forbids naming the provider, but
    # smaller fallback models occasionally ignore that. Replace with a
    # neutral redirect that keeps the learner on-task.
    if settings.GUARDRAILS_BLOCK_IDENTITY_LEAK:
        identity_match = detect_identity_leak(response)
        if identity_match is not None:
            logger.warning(
                "guardrail.output_blocked user_id=%s reason=identity_leak pattern=%r",
                state.get("user_id"),
                identity_match,
            )
            state["response"] = SAFE_IDENTITY_REPLY
            state["guardrail_output_action"] = "blocked_identity_leak"
            return state

    return state
