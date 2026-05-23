"""Estimate USD cost of an LLM call from token counts.

Prices (USD per 1M tokens) are kept inline so we don't need a network call
just to log a cost; update this dict when providers change pricing. Numbers
below mirror public pricing as of mid-2026 and are intentionally rounded
generously upward so the admin dashboard stays a *ceiling* estimate.
"""
from __future__ import annotations

# (input_per_million, output_per_million) in USD
_PRICING: dict[str, tuple[float, float]] = {
    # Groq
    "llama-3.1-8b-instant": (0.05, 0.08),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "mixtral-8x7b-32768": (0.24, 0.24),
    "openai/gpt-oss-120b": (0.15, 0.60),
    "openai/gpt-oss-20b": (0.075, 0.30),
    # Gemini
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-flash-lite": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-embedding-001": (0.15, 0.0),
    # OpenAI
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    # Mock / unknown providers cost $0
    "mock": (0.0, 0.0),
    "uninitialized": (0.0, 0.0),
}


def estimate_cost_usd(model: str | None, tokens_in: int, tokens_out: int) -> float:
    """Return cost in USD for a single LLM call. Unknown models default to $0."""
    key = (model or "").lower()
    pricing = _PRICING.get(key)
    if pricing is None:
        # Try a prefix match so e.g. "gemini-1.5-flash-latest" still resolves.
        for known, value in _PRICING.items():
            if key.startswith(known):
                pricing = value
                break
    if pricing is None:
        return 0.0
    in_rate, out_rate = pricing
    return (tokens_in * in_rate + tokens_out * out_rate) / 1_000_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate when the provider doesn't return usage stats.

    Uses the conventional ~4 characters / token heuristic for English; this
    is good enough for cost ceilings on a hobby project."""
    if not text:
        return 0
    return max(1, len(text) // 4)
