"""LLM call observability — token usage, cost, latency tracing.

A single source of truth for *every* model call made by the project. Both the
data-pipeline (synthetic generation, judge, embeddings) and the FastAPI backend
(chat, intent classification, scaffolding) emit ``LLMCallRecord`` rows here.

Design goals
------------
1. **Zero hidden state.** Every call gets a JSONL row appended to
   ``data/observability/llm_calls.jsonl`` *atomically* (open-append-close).
2. **Cost-correct, provider-aware.** A small in-source price table converts
   prompt/completion tokens to USD; unknown models fall back to 0 USD with
   ``cost_known=false`` so dashboards can highlight them.
3. **Latency-aware.** Records monotonic wall-time around the network call.
4. **Stateless aggregation.** ``summarize()`` re-reads the JSONL with optional
   filters (provider/model/since) — no in-process counters that drift.
5. **Safe in concurrent code.** A module-level ``threading.Lock`` serialises
   appends; the JSONL writer is buffered + flushed on each row.

The schema is intentionally additive — old rows stay readable when new fields
are added (``json.loads`` ignores extras; downstream reports use ``.get``).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .paths import DATA

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pricing — USD per 1M tokens, as of 2026-05.  Update freely; unknown models
# do not crash, they record cost=0 with cost_known=False.
# ---------------------------------------------------------------------------

PRICE_TABLE_USD_PER_M: dict[str, tuple[float, float]] = {
    # Google Gemini (Generative Language API / Vertex). Prices for paid tier.
    "gemini-2.5-pro":         (1.25, 10.00),
    "gemini-2.5-flash":       (0.30,  2.50),
    "gemini-2.5-flash-lite":  (0.10,  0.40),
    "gemini-1.5-pro":         (1.25,  5.00),
    "gemini-1.5-flash":       (0.075, 0.30),
    "gemini-1.5-flash-8b":    (0.0375, 0.15),
    # Embedding models (priced per 1M tokens, only input counts).
    "text-embedding-004":     (0.025, 0.0),
    "gemini-embedding-001":   (0.15,  0.0),

    # Groq (hosted Llama / Mixtral).  Free-tier billable equivalent.
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant":    (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "mixtral-8x7b-32768":      (0.24, 0.24),
    "gemma2-9b-it":            (0.20, 0.20),
}

# Singleton lock for the JSONL writer.
_WRITE_LOCK = threading.Lock()

# Default output path resolves to <repo>/data/observability/llm_calls.jsonl
# (env override: A20_OBSERVABILITY_PATH).
_DEFAULT_PATH = (
    DATA / "observability" / "llm_calls.jsonl"
)


def _resolve_path() -> Path:
    p = Path(os.getenv("A20_OBSERVABILITY_PATH") or _DEFAULT_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ---------------------------------------------------------------------------
# Record
# ---------------------------------------------------------------------------


@dataclass
class LLMCallRecord:
    """One LLM call.  Keep field order stable for grep-ability."""

    ts: str  # ISO-8601 UTC
    call_id: str
    provider: str          # "gemini" | "groq" | "mock" | "guardrail" | ...
    model: str | None
    caller: str            # free-form: "chat:intent_router", "synth:errors", ...
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float
    cost_known: bool
    latency_ms: float
    status: str            # "ok" | "error" | "blocked"
    error: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Cost computation
# ---------------------------------------------------------------------------


def _normalize_model(model: str | None) -> str:
    if not model:
        return ""
    m = model.lower().strip()
    # Strip Gemini version suffixes (e.g. "gemini-2.5-flash-001" → "gemini-2.5-flash")
    if m.startswith("gemini-") and m.count("-") >= 3:
        parts = m.split("-")
        if parts[-1].isdigit() or len(parts[-1]) <= 4:
            m = "-".join(parts[:-1])
    return m


def estimate_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> tuple[float, bool]:
    """Return ``(cost_usd, cost_known)``.  Unknown models return ``(0.0, False)``."""
    key = _normalize_model(model)
    if not key or key not in PRICE_TABLE_USD_PER_M:
        return 0.0, False
    in_per_m, out_per_m = PRICE_TABLE_USD_PER_M[key]
    cost = (prompt_tokens / 1_000_000) * in_per_m + (completion_tokens / 1_000_000) * out_per_m
    return round(cost, 8), True


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def record_call(
    *,
    provider: str,
    model: str | None,
    caller: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: float,
    status: str = "ok",
    error: str | None = None,
    user_id: str | None = None,
    session_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> LLMCallRecord:
    """Append a single LLM call record to the observability log.

    Safe to call from sync or async code; serialised by a process-wide lock.
    Failure to write is *logged* but never raised — observability must never
    break the request path.
    """
    cost_usd, cost_known = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    rec = LLMCallRecord(
        ts=datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        call_id=uuid.uuid4().hex,
        provider=provider,
        model=model,
        caller=caller,
        prompt_tokens=int(prompt_tokens or 0),
        completion_tokens=int(completion_tokens or 0),
        total_tokens=int((prompt_tokens or 0) + (completion_tokens or 0)),
        cost_usd=cost_usd,
        cost_known=cost_known,
        latency_ms=round(latency_ms, 2),
        status=status,
        error=error,
        user_id=user_id,
        session_id=session_id,
        meta=meta or {},
    )
    try:
        path = _resolve_path()
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(rec.as_json())
                f.write("\n")
                f.flush()
    except Exception as exc:  # pragma: no cover — never fail the caller
        log.warning("observability: failed to write record: %s", exc)
    return rec


@contextmanager
def trace_call(
    *,
    provider: str,
    model: str | None,
    caller: str,
    user_id: str | None = None,
    session_id: str | None = None,
    meta: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Context manager that records latency + a final record automatically.

    Usage::

        with trace_call(provider="gemini", model="gemini-2.5-flash", caller="chat") as ctx:
            text = call_model(...)
            ctx["prompt_tokens"] = usage.prompt_tokens
            ctx["completion_tokens"] = usage.completion_tokens

    On exception the record is logged with ``status="error"`` and re-raised.
    """
    ctx: dict[str, Any] = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "status": "ok",
        "error": None,
    }
    t0 = time.perf_counter()
    try:
        yield ctx
    except Exception as exc:
        ctx["status"] = "error"
        ctx["error"] = f"{type(exc).__name__}: {exc}"[:300]
        raise
    finally:
        latency_ms = (time.perf_counter() - t0) * 1000.0
        record_call(
            provider=provider,
            model=model,
            caller=caller,
            prompt_tokens=int(ctx.get("prompt_tokens") or 0),
            completion_tokens=int(ctx.get("completion_tokens") or 0),
            latency_ms=latency_ms,
            status=str(ctx.get("status") or "ok"),
            error=ctx.get("error"),
            user_id=user_id,
            session_id=session_id,
            meta=meta,
        )


# ---------------------------------------------------------------------------
# Aggregation (stateless re-read of the JSONL)
# ---------------------------------------------------------------------------


def iter_records(path: Path | None = None) -> Iterator[dict[str, Any]]:
    p = Path(path) if path else _resolve_path()
    if not p.exists():
        return
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def summarize(
    *,
    path: Path | None = None,
    since_iso: str | None = None,
    provider: str | None = None,
    caller_prefix: str | None = None,
) -> dict[str, Any]:
    """Aggregate metrics from the JSONL log.

    Returns a dict with totals, per-provider, per-model, per-caller stats and
    latency percentiles (p50/p95/p99).
    """
    rows: list[dict[str, Any]] = []
    for r in iter_records(path):
        if since_iso and r.get("ts", "") < since_iso:
            continue
        if provider and r.get("provider") != provider:
            continue
        if caller_prefix and not str(r.get("caller", "")).startswith(caller_prefix):
            continue
        rows.append(r)

    def _pct(xs: list[float], p: float) -> float:
        if not xs:
            return 0.0
        xs2 = sorted(xs)
        idx = min(len(xs2) - 1, max(0, int(round((p / 100.0) * (len(xs2) - 1)))))
        return round(xs2[idx], 2)

    def _bucket(key: str) -> dict[str, dict[str, float]]:
        buckets: dict[str, dict[str, float]] = {}
        for r in rows:
            k = str(r.get(key) or "<none>")
            b = buckets.setdefault(k, {"calls": 0, "prompt_tokens": 0, "completion_tokens": 0, "cost_usd": 0.0})
            b["calls"] += 1
            b["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
            b["completion_tokens"] += int(r.get("completion_tokens") or 0)
            b["cost_usd"] += float(r.get("cost_usd") or 0.0)
        return buckets

    latencies = [float(r.get("latency_ms") or 0.0) for r in rows if r.get("status") == "ok"]
    return {
        "window": {
            "rows": len(rows),
            "since": since_iso,
            "provider_filter": provider,
            "caller_prefix_filter": caller_prefix,
        },
        "totals": {
            "calls": len(rows),
            "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
            "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in rows),
            "cost_usd": round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 6),
            "errors": sum(1 for r in rows if r.get("status") != "ok"),
            "unknown_price_calls": sum(1 for r in rows if not r.get("cost_known", False)),
        },
        "latency_ms": {
            "p50": _pct(latencies, 50),
            "p95": _pct(latencies, 95),
            "p99": _pct(latencies, 99),
        },
        "by_provider": _bucket("provider"),
        "by_model": _bucket("model"),
        "by_caller": _bucket("caller"),
    }


def reset_log(path: Path | None = None) -> Path:
    """Truncate the JSONL (used by evaluation scripts to scope a run)."""
    p = Path(path) if path else _resolve_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("", encoding="utf-8")
    return p
