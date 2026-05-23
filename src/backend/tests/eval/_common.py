"""Shared utilities for the eval harness.

Centralises:
* Backend base URL & test user provisioning (idempotent login or register).
* Reading the JSONL cost log to attribute spend to a specific test run.
* Writing structured reports (JSON + Markdown) under ``docs/evaluation/``.

Why a shared helper? Each eval script (chat-quality, RAG, guardrail, stress)
needs the *same* notion of "log-in once, replay N prompts, then summarise the
window of the cost-log produced". Duplicating that bookkeeping across four
files invites drift.
"""

from __future__ import annotations

import contextlib
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

import httpx

BACKEND_URL = os.getenv("EVAL_BACKEND_URL", "http://localhost:8000")
ADMIN_TOKEN = os.getenv("EVAL_ADMIN_TOKEN", "change-me-in-prod")

REPO_ROOT = Path(__file__).resolve().parents[4]
REPORT_DIR = REPO_ROOT / "docs" / "evaluation"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Backend writes here when running via docker-compose (mounted volume).
COST_LOG = REPO_ROOT / "data" / "observability" / "llm_calls.jsonl"


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------


def ensure_eval_user(client: httpx.Client, email: str | None = None, password: str = "Eval-Pass-2026!") -> dict[str, Any]:
    """Idempotently provision a test user; return ``{user_id, email, password}``.

    Strategy: try ``/auth/register`` first; if the email is taken, log in. The
    cookie returned by either flow is stored on the client.
    """
    email = email or f"eval-{uuid.uuid4().hex[:8]}@a20.test"
    payload = {
        "email": email,
        "password": password,
        "cefr_level": "B1",
        "industry": "IT",
        "learning_goals": ["general"],
    }
    r = client.post(f"{BACKEND_URL}/api/v1/auth/register", json=payload, timeout=15)
    if r.status_code in (200, 201):
        return {"user_id": r.json()["user_id"], "email": email, "password": password}
    # Fall through to login
    r = client.post(
        f"{BACKEND_URL}/api/v1/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if r.status_code in (200, 201):
        return {"user_id": r.json()["user_id"], "email": email, "password": password}
    raise RuntimeError(f"Could not provision eval user: register={r.status_code}, body={r.text[:200]}")


# ---------------------------------------------------------------------------
# Cost log helpers
# ---------------------------------------------------------------------------


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def read_cost_window(since_iso: str, caller_prefix: str | None = None) -> list[dict[str, Any]]:
    """Return all cost rows since ``since_iso`` (optionally filtered by caller)."""
    if not COST_LOG.exists():
        return []
    out: list[dict[str, Any]] = []
    with COST_LOG.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("ts", "") < since_iso:
                continue
            if caller_prefix and not str(r.get("caller", "")).startswith(caller_prefix):
                continue
            out.append(r)
    return out


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate cost rows (mirrors ``llm_costs.summarize`` but in-process)."""
    if not rows:
        return {
            "calls": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
            "latency_ms": {"p50": 0.0, "p95": 0.0, "p99": 0.0},
            "by_provider": {},
            "by_model": {},
        }

    latencies = sorted(float(r.get("latency_ms") or 0.0) for r in rows if r.get("status") == "ok")

    def _p(p: float) -> float:
        if not latencies:
            return 0.0
        idx = min(len(latencies) - 1, max(0, int(round(p / 100.0 * (len(latencies) - 1)))))
        return round(latencies[idx], 2)

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

    return {
        "calls": len(rows),
        "prompt_tokens": sum(int(r.get("prompt_tokens") or 0) for r in rows),
        "completion_tokens": sum(int(r.get("completion_tokens") or 0) for r in rows),
        "cost_usd": round(sum(float(r.get("cost_usd") or 0.0) for r in rows), 8),
        "errors": sum(1 for r in rows if r.get("status") != "ok"),
        "latency_ms": {"p50": _p(50), "p95": _p(95), "p99": _p(99)},
        "by_provider": _bucket("provider"),
        "by_model": _bucket("model"),
    }


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def write_json_report(name: str, payload: dict[str, Any]) -> Path:
    """Persist a JSON report under ``docs/evaluation/<name>.json``."""
    path = REPORT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_md_report(name: str, body: str) -> Path:
    """Persist a Markdown report under ``docs/evaluation/<name>.md``."""
    path = REPORT_DIR / f"{name}.md"
    path.write_text(body, encoding="utf-8")
    return path


@contextlib.contextmanager
def stopwatch() -> Iterator[dict[str, float]]:
    """``with stopwatch() as t: ...`` → ``t['elapsed']`` is the wall time in s."""
    t = {"start": time.perf_counter(), "elapsed": 0.0}
    try:
        yield t
    finally:
        t["elapsed"] = time.perf_counter() - t["start"]
