"""Mem0 persistent memory latency + recall benchmark.

Probes the live Mem0 manager (via the backend container) for:
    * add latency (write path)
    * search latency p50/p95/p99 (read path)
    * recall@k for a tiny gold set (does Mem0 retrieve the seeded fact?)

Run inside the backend container (volume-mounted)::

    docker compose exec backend python -m tests.eval.mem0_benchmark
"""
from __future__ import annotations

import json
import statistics
import time
import uuid
from pathlib import Path

from app.core.mem0_client import get_memory  # type: ignore

REPORT_DIR = Path("/app/data/observability")
REPORT_DIR.mkdir(parents=True, exist_ok=True)


GOLD_FACTS = [
    ("affects vs effects", "User confuses 'affect' (verb) with 'effect' (noun)."),
    ("make vs do", "User mixes 'make' and 'do' collocations like 'make homework'."),
    ("prepositions", "User struggles with prepositions of time: 'in', 'on', 'at'."),
    ("present perfect", "User omits auxiliary 'have' in present perfect tense."),
    ("subject-verb", "User makes subject-verb agreement errors with 'one of'."),
    ("article a/an", "User drops articles 'a/an' before count nouns."),
    ("phrasal verbs", "User translates phrasal verbs literally from Vietnamese."),
    ("collocations", "User says 'strong rain' instead of 'heavy rain'."),
    ("tense backshift", "User forgets to backshift tense in reported speech."),
    ("modal verbs", "User confuses 'must' (obligation) vs 'have to' (necessity)."),
]

QUERIES = [
    ("affect or effect?", "affect"),
    ("how to use make vs do?", "make"),
    ("when to use in/on/at?", "preposition"),
    ("present perfect rule", "present perfect"),
    ("subject verb agreement", "subject-verb"),
    ("article a or an", "article"),
    ("phrasal verb translate", "phrasal"),
    ("strong rain or heavy rain", "collocation"),
    ("reported speech tense", "backshift"),
    ("must vs have to", "modal"),
    # extra probes that should NOT be confidently recalled
    ("what is photosynthesis", None),
    ("recipe for pho", None),
]


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, int(round(p / 100.0 * (len(s) - 1)))))
    return round(s[idx], 2)


def main() -> int:
    mm = get_memory()
    mm.warmup()
    user_id = f"bench-{uuid.uuid4().hex[:8]}"
    print(f"[mem0-bench] user={user_id}  stub={mm.using_stub}")

    add_latencies: list[float] = []
    for tag, content in GOLD_FACTS:
        t0 = time.perf_counter()
        try:
            mm.add_memory(user_id, content, metadata={"tag": tag})
        except Exception as exc:  # pragma: no cover
            print(f"[mem0-bench] add failed for {tag}: {exc}")
            continue
        add_latencies.append((time.perf_counter() - t0) * 1000)

    search_latencies: list[float] = []
    hits = 0
    misses_intended = 0
    recall_at_3 = 0
    for q, expected in QUERIES:
        t0 = time.perf_counter()
        try:
            res = mm.search_memory(user_id, q, limit=3)
        except Exception as exc:
            print(f"[mem0-bench] search failed: {exc}")
            continue
        search_latencies.append((time.perf_counter() - t0) * 1000)
        # mem0 returns either list[dict] or {results:[...]}; normalize:
        items = res.get("results", res) if isinstance(res, dict) else res
        flat = " ".join(
            (it.get("memory") or it.get("content") or "")
            for it in (items or [])
        ).lower()
        if expected is None:
            # control queries: ok either way; not counted toward recall
            misses_intended += 1
            continue
        if expected.lower() in flat:
            recall_at_3 += 1
            hits += 1

    total_real = len(QUERIES) - misses_intended
    report = {
        "user_id": user_id,
        "using_stub": mm.using_stub,
        "n_facts_seeded": len(add_latencies),
        "add_latency_ms": {
            "p50": _pct(add_latencies, 50),
            "p95": _pct(add_latencies, 95),
            "p99": _pct(add_latencies, 99),
            "mean": round(statistics.fmean(add_latencies), 2) if add_latencies else 0,
        },
        "search_latency_ms": {
            "p50": _pct(search_latencies, 50),
            "p95": _pct(search_latencies, 95),
            "p99": _pct(search_latencies, 99),
            "mean": round(statistics.fmean(search_latencies), 2) if search_latencies else 0,
        },
        "recall_at_3": round(recall_at_3 / total_real, 3) if total_real else 0.0,
        "n_real_queries": total_real,
        "n_control_queries": misses_intended,
    }

    out = REPORT_DIR / "mem0_benchmark.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    # Best-effort cleanup
    try:
        mm.delete_user_memory(user_id)
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
