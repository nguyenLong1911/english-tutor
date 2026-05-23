"""Concurrency ladder stress test against the ``/api/v1/chat`` endpoint.

Runs increasing concurrency tiers (default 10 → 25 → 50 → 100) and records,
per tier:

* total / successful / error counts and 4xx / 5xx breakdown,
* latency p50 / p95 / p99 (wall time around the HTTP call),
* tokens & USD consumed in the tier (filtered from the cost JSONL).

Why per-tier rather than a single 100-user run? The chat endpoint is
rate-limited (50 req/user/day) and we want to see *where* the system starts
to degrade. A ladder makes that elbow visible.

Run::

    docker compose up -d
    python -m backend.tests.eval.stress_chat --tiers 10 25 50
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
import uuid
from statistics import median
from typing import Any

import httpx

from ._common import (
    BACKEND_URL,
    ensure_eval_user,
    now_iso,
    read_cost_window,
    summarize_rows,
    write_json_report,
    write_md_report,
)

DEFAULT_TIERS = (10, 25, 50, 100)
PROMPTS = [
    "How do I use past simple tense?",
    "What does 'deployment' mean in IT?",
    "Difference between 'much' and 'many'?",
    "How am I doing this week?",
    "Is it 'in the morning' or 'on the morning'?",
    "Help me with my essay introduction.",
    "What's a phrasal verb?",
    "Why is it 'three months ago' and not 'before three months'?",
]


# ---------------------------------------------------------------------------
# Per-user simulation
# ---------------------------------------------------------------------------


async def one_user(
    client: httpx.AsyncClient,
    user_id: str,
    idx: int,
    n_prompts: int = 2,
) -> dict[str, Any]:
    """Send ``n_prompts`` chat messages on a fresh cookie."""
    latencies: list[float] = []
    errors: list[str] = []

    for j in range(n_prompts):
        msg = PROMPTS[(idx + j) % len(PROMPTS)]
        t0 = time.perf_counter()
        try:
            r = await client.post(
                f"{BACKEND_URL}/api/v1/chat",
                json={"user_id": user_id, "message": msg, "type": "QUICK_QA"},
                timeout=60,
            )
            latencies.append(time.perf_counter() - t0)
            if r.status_code >= 400:
                errors.append(f"http_{r.status_code}")
        except Exception as exc:
            errors.append(f"exc:{type(exc).__name__}")
            latencies.append(time.perf_counter() - t0)
    return {"latencies": latencies, "errors": errors}


async def run_tier(concurrency: int) -> dict[str, Any]:
    """One tier: spawn ``concurrency`` user sessions in parallel."""
    started_iso = now_iso()

    # Provision users sequentially (cookie-jar per user); only the chat hot
    # path needs to be concurrent to measure server-side contention.
    users: list[str] = []
    async with httpx.AsyncClient() as setup_client:
        # ensure_eval_user is sync — wrap via to_thread to avoid blocking the loop.
        from anyio import to_thread

        async def _provision(i: int) -> str:
            import httpx as _hx
            with _hx.Client() as c:
                u = ensure_eval_user(c, email=f"stress-{concurrency}-{i}-{uuid.uuid4().hex[:6]}@a20.test")
            return u["user_id"]

        users = await asyncio.gather(*[_provision(i) for i in range(concurrency)])

    t0 = time.perf_counter()
    limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        results = await asyncio.gather(*[one_user(client, users[i], i) for i in range(concurrency)])
    wall_s = time.perf_counter() - t0

    all_latencies = sorted(l for r in results for l in r["latencies"])
    all_errors = [e for r in results for e in r["errors"]]
    total = len(all_latencies)

    def _pct(p: float) -> float:
        if not all_latencies:
            return 0.0
        idx = min(len(all_latencies) - 1, max(0, int(round(p / 100.0 * (len(all_latencies) - 1)))))
        return round(all_latencies[idx] * 1000, 2)

    # Pull cost rows produced during this tier.
    cost_rows = read_cost_window(started_iso, caller_prefix="backend.chat")
    cost = summarize_rows(cost_rows)

    return {
        "concurrency": concurrency,
        "started_iso": started_iso,
        "wall_seconds": round(wall_s, 3),
        "total_requests": total,
        "errors": len(all_errors),
        "error_rate": round(len(all_errors) / max(total + len(all_errors), 1), 4),
        "throughput_rps": round((total) / max(wall_s, 0.001), 2),
        "latency_ms": {
            "p50": _pct(50),
            "p95": _pct(95),
            "p99": _pct(99),
            "max": round((all_latencies[-1] * 1000) if all_latencies else 0, 2),
        },
        "cost": cost,
        "error_samples": all_errors[:10],
    }


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


async def run_all(tiers: tuple[int, ...]) -> dict[str, Any]:
    started_iso = now_iso()
    tier_results = []
    for c in tiers:
        print(f"[stress] tier concurrency={c} starting ...")
        res = await run_tier(c)
        print(
            f"[stress] tier={c}  ok={res['total_requests']}  "
            f"errs={res['errors']}  p95={res['latency_ms']['p95']}ms  "
            f"rps={res['throughput_rps']}  cost=${res['cost']['cost_usd']:.4f}"
        )
        tier_results.append(res)
        # Cool-down so the next tier sees a clean rate limit.
        await asyncio.sleep(2)

    report = {
        "run": {"started_iso": started_iso, "backend_url": BACKEND_URL, "tiers": list(tiers)},
        "tiers": tier_results,
    }
    write_json_report("stress_test_report", report)
    write_md_report("stress_test_report", _render_md(report))
    return report


def _render_md(report: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# Stress Test Report — /api/v1/chat\n")
    out.append(f"- **Run started:** {report['run']['started_iso']}\n")
    out.append(f"- **Backend:** {report['run']['backend_url']}\n")
    out.append(f"- **Tiers:** {report['run']['tiers']}\n\n")

    out.append("## Concurrency ladder\n\n")
    out.append("| Tier | Requests | Errors | Error % | RPS | p50 ms | p95 ms | p99 ms | Cost USD |\n")
    out.append("|---|---|---|---|---|---|---|---|---|\n")
    for t in report["tiers"]:
        l = t["latency_ms"]
        out.append(
            f"| {t['concurrency']} | {t['total_requests']} | {t['errors']} | "
            f"{t['error_rate']*100:.1f}% | {t['throughput_rps']} | "
            f"{l['p50']} | {l['p95']} | {l['p99']} | ${t['cost']['cost_usd']:.4f} |\n"
        )
    out.append("\n## Cost & tokens per tier\n\n")
    out.append("| Tier | LLM calls | Prompt tok | Completion tok | USD | USD / req |\n|---|---|---|---|---|---|\n")
    for t in report["tiers"]:
        c = t["cost"]
        per_req = c["cost_usd"] / max(t["total_requests"], 1)
        out.append(
            f"| {t['concurrency']} | {c['calls']} | {c['prompt_tokens']} | "
            f"{c['completion_tokens']} | ${c['cost_usd']:.4f} | ${per_req:.6f} |\n"
        )

    samples = [e for t in report["tiers"] for e in t.get("error_samples", [])]
    if samples:
        out.append("\n## Error samples (first 10 across all tiers)\n\n")
        for s in samples[:10]:
            out.append(f"- {s}\n")
    return "".join(out)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tiers", type=int, nargs="+", default=list(DEFAULT_TIERS))
    args = parser.parse_args()
    rep = asyncio.run(run_all(tuple(args.tiers)))
    summary = [{
        "concurrency": t["concurrency"],
        "ok": t["total_requests"],
        "errors": t["errors"],
        "p95_ms": t["latency_ms"]["p95"],
        "cost_usd": t["cost"]["cost_usd"],
    } for t in rep["tiers"]]
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
