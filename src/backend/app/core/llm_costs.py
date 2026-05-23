"""Per-call LLM cost & latency tracer for the backend.

Writes the same JSONL schema as ``data_pipeline.observability`` (so a single
dashboard can aggregate calls coming from both the data-pipeline scripts and
the FastAPI runtime). Path is configurable via ``A20_OBSERVABILITY_PATH``;
defaults to ``/app/data/observability/llm_calls.jsonl`` which is mounted
from the host (see ``docker-compose.yml``).

Schema fields (all optional consumers — append-only, additive evolution):
  ts, call_id, provider, model, caller, prompt_tokens, completion_tokens,
  total_tokens, cost_usd, cost_known, latency_ms, status, error,
  user_id, session_id, meta
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Same price table as data_pipeline.observability; kept in sync manually.
PRICE_TABLE_USD_PER_M: dict[str, tuple[float, float]] = {
    "gemini-2.5-pro":         (1.25, 10.00),
    "gemini-2.5-flash":       (0.30,  2.50),
    "gemini-2.5-flash-lite":  (0.10,  0.40),
    "gemini-1.5-pro":         (1.25,  5.00),
    "gemini-1.5-flash":       (0.075, 0.30),
    "gemini-1.5-flash-8b":    (0.0375, 0.15),
    "text-embedding-004":     (0.025, 0.0),
    "gemini-embedding-001":   (0.15,  0.0),
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "llama-3.1-8b-instant":    (0.05, 0.08),
    "llama-3.1-70b-versatile": (0.59, 0.79),
    "mixtral-8x7b-32768":      (0.24, 0.24),
    "gemma2-9b-it":            (0.20, 0.20),
    "openai/gpt-oss-120b":     (0.15, 0.60),
    "openai/gpt-oss-20b":      (0.075, 0.30),
}

_WRITE_LOCK = threading.Lock()


def _default_path() -> Path:
    # /app/data/observability/... when running in Docker; fall back to repo path.
    return Path(
        os.getenv("A20_OBSERVABILITY_PATH")
        or "/app/data/observability/llm_calls.jsonl"
    )


def _normalize_model(model: str | None) -> str:
    if not model:
        return ""
    m = model.lower().strip()
    if m.startswith("gemini-") and m.count("-") >= 3:
        parts = m.split("-")
        if parts[-1].isdigit() or len(parts[-1]) <= 4:
            m = "-".join(parts[:-1])
    return m


def estimate_cost_usd(model: str | None, prompt_tokens: int, completion_tokens: int) -> tuple[float, bool]:
    key = _normalize_model(model)
    if not key or key not in PRICE_TABLE_USD_PER_M:
        return 0.0, False
    in_per_m, out_per_m = PRICE_TABLE_USD_PER_M[key]
    cost = (prompt_tokens / 1_000_000) * in_per_m + (completion_tokens / 1_000_000) * out_per_m
    return round(cost, 8), True


def _write(record: dict[str, Any]) -> None:
    try:
        path = _default_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        with _WRITE_LOCK:
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
                f.write("\n")
                f.flush()
    except Exception as exc:  # pragma: no cover — never break the request
        logger.warning("llm_costs: failed to write record: %s", exc)


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
) -> dict[str, Any]:
    cost_usd, cost_known = estimate_cost_usd(model, prompt_tokens, completion_tokens)
    rec = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
        "call_id": uuid.uuid4().hex,
        "provider": provider,
        "model": model,
        "caller": caller,
        "prompt_tokens": int(prompt_tokens or 0),
        "completion_tokens": int(completion_tokens or 0),
        "total_tokens": int((prompt_tokens or 0) + (completion_tokens or 0)),
        "cost_usd": cost_usd,
        "cost_known": cost_known,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "error": error,
        "user_id": user_id,
        "session_id": session_id,
        "meta": meta or {},
    }
    # Offload disk write to a thread so async hot paths stay non-blocking.
    try:
        loop = asyncio.get_running_loop()
        loop.run_in_executor(None, _write, rec)
    except RuntimeError:
        _write(rec)
    return rec


def summarize(
    *,
    path: Path | None = None,
    since_iso: str | None = None,
    provider: str | None = None,
    caller_prefix: str | None = None,
) -> dict[str, Any]:
    p = Path(path) if path else _default_path()
    if not p.exists():
        return {"window": {"rows": 0}, "totals": {"calls": 0, "cost_usd": 0.0}, "by_provider": {}, "by_model": {}, "by_caller": {}}

    rows: list[dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
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
        "window": {"rows": len(rows), "since": since_iso},
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
