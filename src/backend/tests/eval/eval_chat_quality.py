"""End-to-end chat quality + RAG-style retrieval evaluation.

Replays a curated **gold set** of learner turns against the live
``POST /api/v1/chat`` endpoint and checks:

1. **HTTP success** — non-2xx counted as failure.
2. **Intent correctness** — the orchestrator's intent_router must match the
   ground-truth intent (PRACTICE / QUICK_QA / PROGRESS) for each turn.
3. **Concept grounding** — for QUICK_QA / PRACTICE turns we encode the expected
   *concept keywords* (e.g. when asking about "affect vs effect" we expect
   the response to mention one of those words or the Vietnamese equivalent).
   This is a coarse RAG-style probe: if the LLM is grounded in the
   pedagogical knowledge stored on the backend it should mention the relevant
   anchors; if it produces vapid prose the recall@1 drops.

The script saves both a JSON ledger (per-turn input/output/judgements/cost)
and a Markdown summary under ``docs/evaluation/``.

Run::

    docker compose up -d
    python -m backend.tests.eval.eval_chat_quality
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

import httpx

from ._common import (
    BACKEND_URL,
    ensure_eval_user,
    now_iso,
    read_cost_window,
    stopwatch,
    summarize_rows,
    write_json_report,
    write_md_report,
)


# ---------------------------------------------------------------------------
# Gold set — small, hand-curated, grounded in v_english_error_bank.json.
#
# `keywords_any`: regex-free, case-insensitive substrings; if ANY appears in
# the response we count the concept as "grounded". For Vietnamese learners
# the Vietnamese gloss is often more informative than the English term, so we
# include both languages where it makes sense.
# ---------------------------------------------------------------------------

GOLD_TURNS: list[dict[str, Any]] = [
    {
        "id": "Q01-affect-effect",
        "message": "What is the difference between 'affect' and 'effect'?",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["affect", "effect", "ảnh hưởng", "tác động", "verb", "noun"],
    },
    {
        "id": "Q02-make-do",
        "message": "When should I use 'make' versus 'do' in English?",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["make", "do", "tạo", "làm", "produce"],
    },
    {
        "id": "Q03-prepositions",
        "message": "I'm confused about 'in', 'on', 'at' for time expressions.",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["in", "on", "at", "time", "thời gian", "preposition"],
    },
    {
        "id": "P01-tense-error",
        "message": "I am study English everyday for 2 hour.",
        "expected_intent": "PRACTICE",
        "keywords_any": ["study", "studying", "hour", "hours", "tense", "everyday", "every day"],
    },
    {
        "id": "P02-article-missing",
        "message": "Yesterday I go to office and meet client for important meeting.",
        "expected_intent": "PRACTICE",
        "keywords_any": ["went", "the", "an", "a ", "article", "past", "tense"],
    },
    {
        "id": "P03-subject-verb",
        "message": "She don't likes coffee on the morning.",
        "expected_intent": "PRACTICE",
        "keywords_any": ["doesn't", "does not", "like", "in the morning", "subject", "verb"],
    },
    {
        "id": "G01-progress",
        "message": "How am I doing this week? What's my progress?",
        "expected_intent": "PROGRESS",
        "keywords_any": ["progress", "tiến", "review", "vocab", "thống kê", "accuracy", "tuần"],
    },
    {
        "id": "Q04-industry-IT",
        "message": "What does 'deployment' mean in software engineering context?",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["deploy", "triển khai", "release", "production", "phần mềm"],
    },
    {
        "id": "Q05-collocation",
        "message": "Is it 'make a decision' or 'do a decision'?",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["make a decision", "make", "decision", "đưa ra"],
    },
    {
        "id": "Q06-pronoun",
        "message": "When do I use 'who' versus 'whom'?",
        "expected_intent": "QUICK_QA",
        "keywords_any": ["who", "whom", "subject", "object", "chủ ngữ", "tân ngữ"],
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


def _keyword_hit(response: str, keywords: list[str]) -> tuple[bool, list[str]]:
    body = response.lower()
    hits = [k for k in keywords if k.lower() in body]
    return (len(hits) > 0), hits


def run_eval() -> dict[str, Any]:
    started_iso = now_iso()
    with httpx.Client() as client:
        user = ensure_eval_user(client, email=f"eval-chat-{uuid.uuid4().hex[:6]}@a20.test")
        user_id = user["user_id"]

        turns: list[dict[str, Any]] = []
        with stopwatch() as t:
            for spec in GOLD_TURNS:
                payload = {
                    "user_id": user_id,
                    "message": spec["message"],
                    "type": spec["expected_intent"],
                }
                t0 = time.perf_counter()
                try:
                    r = client.post(
                        f"{BACKEND_URL}/api/v1/chat",
                        json=payload,
                        timeout=60,
                    )
                    latency = time.perf_counter() - t0
                    if r.status_code != 200:
                        turns.append({
                            "id": spec["id"],
                            "message": spec["message"],
                            "status": f"http_{r.status_code}",
                            "latency_s": round(latency, 3),
                            "error": r.text[:200],
                        })
                        continue
                    body = r.json()
                    response_text = str(body.get("response") or "")
                    intent_match = body.get("intent") == spec["expected_intent"]
                    grounded, hits = _keyword_hit(response_text, spec["keywords_any"])
                    turns.append({
                        "id": spec["id"],
                        "message": spec["message"],
                        "expected_intent": spec["expected_intent"],
                        "actual_intent": body.get("intent"),
                        "intent_match": intent_match,
                        "response": response_text,
                        "grounded": grounded,
                        "matched_keywords": hits,
                        "hint_count": body.get("hint_count"),
                        "latency_s": round(latency, 3),
                        "status": "ok",
                    })
                except Exception as exc:
                    turns.append({
                        "id": spec["id"],
                        "message": spec["message"],
                        "status": f"exception:{type(exc).__name__}",
                        "error": str(exc)[:200],
                        "latency_s": round(time.perf_counter() - t0, 3),
                    })

        wall_s = t["elapsed"]

    # Pull the slice of the cost log produced by this run.
    cost_rows = read_cost_window(started_iso, caller_prefix="backend.chat")
    cost = summarize_rows(cost_rows)

    ok_turns = [t for t in turns if t.get("status") == "ok"]
    intent_acc = sum(1 for t in ok_turns if t.get("intent_match")) / max(len(ok_turns), 1)
    grounded_acc = sum(1 for t in ok_turns if t.get("grounded")) / max(len(ok_turns), 1)

    report = {
        "run": {
            "started_iso": started_iso,
            "wall_seconds": round(wall_s, 3),
            "backend_url": BACKEND_URL,
            "gold_turns": len(GOLD_TURNS),
            "successful_turns": len(ok_turns),
        },
        "quality": {
            "intent_accuracy": round(intent_acc, 4),
            "grounding_recall_at_keyword": round(grounded_acc, 4),
            "error_rate": round(1 - len(ok_turns) / max(len(turns), 1), 4),
        },
        "cost": cost,
        "turns": turns,
    }

    write_json_report("chat_quality_report", report)
    write_md_report("chat_quality_report", _render_md(report))
    return report


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------


def _render_md(report: dict[str, Any]) -> str:
    run = report["run"]
    q = report["quality"]
    c = report["cost"]
    md: list[str] = []
    md.append("# Chat Quality & RAG Evaluation Report\n")
    md.append(f"- **Run started:** {run['started_iso']}\n")
    md.append(f"- **Backend:** {run['backend_url']}\n")
    md.append(f"- **Gold turns:** {run['gold_turns']}  |  **Successful:** {run['successful_turns']}\n")
    md.append(f"- **Wall time:** {run['wall_seconds']}s\n\n")

    md.append("## Quality\n")
    md.append(f"| Metric | Value |\n|---|---|\n")
    md.append(f"| Intent accuracy | {q['intent_accuracy']*100:.1f}% |\n")
    md.append(f"| Grounding recall@keyword | {q['grounding_recall_at_keyword']*100:.1f}% |\n")
    md.append(f"| Error rate | {q['error_rate']*100:.1f}% |\n\n")

    md.append("## Cost & latency (this run only)\n")
    md.append(f"| Calls | Prompt tokens | Completion tokens | Cost USD | p50 ms | p95 ms | p99 ms |\n")
    md.append(f"|---|---|---|---|---|---|---|\n")
    md.append(
        f"| {c['calls']} | {c['prompt_tokens']} | {c['completion_tokens']} | ${c['cost_usd']:.6f} | "
        f"{c['latency_ms']['p50']} | {c['latency_ms']['p95']} | {c['latency_ms']['p99']} |\n\n"
    )

    if c.get("by_provider"):
        md.append("### By provider\n\n| Provider | Calls | Cost USD |\n|---|---|---|\n")
        for prov, b in sorted(c["by_provider"].items(), key=lambda kv: -kv[1]["calls"]):
            md.append(f"| {prov} | {int(b['calls'])} | ${b['cost_usd']:.6f} |\n")
        md.append("\n")
    if c.get("by_model"):
        md.append("### By model\n\n| Model | Calls | Cost USD |\n|---|---|---|\n")
        for m, b in sorted(c["by_model"].items(), key=lambda kv: -kv[1]["calls"]):
            md.append(f"| {m or '<none>'} | {int(b['calls'])} | ${b['cost_usd']:.6f} |\n")
        md.append("\n")

    md.append("## Per-turn results\n\n")
    md.append("| ID | Expected intent | Actual | Intent ✓ | Grounded ✓ | Latency s |\n")
    md.append("|---|---|---|---|---|---|\n")
    for t in report["turns"]:
        if t.get("status") == "ok":
            md.append(
                f"| {t['id']} | {t['expected_intent']} | {t['actual_intent']} | "
                f"{'✓' if t['intent_match'] else '✗'} | "
                f"{'✓' if t['grounded'] else '✗'} | {t['latency_s']} |\n"
            )
        else:
            md.append(f"| {t['id']} | – | – | – | – | err: {t.get('status')} |\n")
    return "".join(md)


if __name__ == "__main__":
    rep = run_eval()
    print(json.dumps(
        {"quality": rep["quality"], "cost": {k: v for k, v in rep["cost"].items() if k != "by_caller"}},
        indent=2,
        ensure_ascii=False,
    ))
