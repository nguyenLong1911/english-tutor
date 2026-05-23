from __future__ import annotations

import argparse
import csv
import io
import json
import random
import sys
import time
import urllib.request
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .alignment import build_gold_edits, score_events


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BACKEND_ROOT = SRC_ROOT / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

DATASET_URL = "https://huggingface.co/datasets/lang-uk/Reddit-MultiGEC/resolve/main/reddit_multi_gec.csv"
DATASET_NAME = "lang-uk/Reddit-MultiGEC"
DATASET_LANGUAGE = "english"
LEGACY_FULL_DATASET_CACHE = REPO_ROOT / "data" / "raw" / "huggingface" / "reddit_multigec" / "reddit_multi_gec.csv"
DEFAULT_CACHE = REPO_ROOT / "data" / "raw" / "huggingface" / "reddit_multigec" / "reddit_multi_gec_english.csv"
REPORT_DIR = REPO_ROOT / "docs" / "evaluation"
DEFAULT_PASSWORD = "Eval-Pass-2026!"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _validate_dataset_columns(fieldnames: list[str] | None, source: str) -> None:
    required = {"language", "text", "correction"}
    missing = required - set(fieldnames or [])
    if missing:
        raise ValueError(f"{source} is missing columns: {sorted(missing)}")


def _write_english_rows_from_reader(reader: csv.DictReader, cache_path: Path) -> int:
    _validate_dataset_columns(reader.fieldnames, str(cache_path))
    rows_written = 0
    saw_english_block = False

    with cache_path.open("w", encoding="utf-8", newline="") as output:
        writer = csv.DictWriter(output, fieldnames=["language", "text", "correction"])
        writer.writeheader()
        for row in reader:
            language = str(row.get("language") or "").strip().lower()
            if language != DATASET_LANGUAGE:
                if saw_english_block:
                    break
                continue

            saw_english_block = True
            text = str(row.get("text") or "").strip()
            correction = str(row.get("correction") or "").strip()
            if text and correction and text != correction:
                writer.writerow({"language": DATASET_LANGUAGE, "text": text, "correction": correction})
                rows_written += 1

    if rows_written == 0:
        raise RuntimeError(f"No {DATASET_LANGUAGE} rows were found in {DATASET_NAME}.")
    return rows_written


def _build_english_cache_from_csv(source_path: Path, cache_path: Path) -> Path:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with source_path.open("r", encoding="utf-8", newline="") as handle:
        _write_english_rows_from_reader(csv.DictReader(handle), cache_path)
    return cache_path


def download_english_dataset(cache_path: Path, *, force: bool = False) -> Path:
    """Cache only the English rows used by this eval harness.

    Reddit-MultiGEC publishes the multilingual data as one CSV, but rows are grouped
    by language. Streaming lets us persist only English rows and close the response
    once the English block ends instead of saving the full 100 MB file.
    """
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if cache_path.exists() and not force:
        return cache_path

    if LEGACY_FULL_DATASET_CACHE.exists() and LEGACY_FULL_DATASET_CACHE != cache_path and not force:
        return _build_english_cache_from_csv(LEGACY_FULL_DATASET_CACHE, cache_path)

    with urllib.request.urlopen(DATASET_URL) as response:
        text_stream = io.TextIOWrapper(response, encoding="utf-8", newline="")
        _write_english_rows_from_reader(csv.DictReader(text_stream), cache_path)
    return cache_path


def load_english_rows(csv_path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        _validate_dataset_columns(reader.fieldnames, str(csv_path))
        for row in reader:
            if str(row.get("language") or "").strip().lower() != DATASET_LANGUAGE:
                continue
            text = str(row.get("text") or "").strip()
            correction = str(row.get("correction") or "").strip()
            if text and correction and text != correction:
                rows.append({"text": text, "correction": correction})
    return rows


def sample_rows(rows: list[dict[str, str]], *, sample_size: int, seed: int) -> list[dict[str, str]]:
    rng = random.Random(seed)
    indexed = list(enumerate(rows))
    if sample_size > 0 and sample_size < len(indexed):
        indexed = rng.sample(indexed, sample_size)
    indexed.sort(key=lambda item: item[0])
    return [{"dataset_index": index, **row} for index, row in indexed]


def ensure_eval_user(client: httpx.Client, backend_url: str) -> dict[str, Any]:
    email = f"eval-reddit-gec-{uuid.uuid4().hex[:8]}@a20.test"
    payload = {
        "email": email,
        "password": DEFAULT_PASSWORD,
        "cefr_level": "B1",
        "industry": "general",
        "learning_goals": ["english error correction"],
    }
    response = client.post(f"{backend_url}/api/v1/auth/register", json=payload, timeout=30)
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Could not create eval user: HTTP {response.status_code} {response.text[:300]}")
    return {"user_id": response.json()["user_id"], "email": email}


def query_quick_qa_events(user_id: str, started_at: datetime) -> list[dict[str, Any]]:
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.models.personal_review import UserErrorEvent

    db = SessionLocal()
    try:
        rows = db.execute(
            select(UserErrorEvent)
            .where(UserErrorEvent.user_id == uuid.UUID(user_id), UserErrorEvent.created_at >= started_at.replace(tzinfo=None))
            .order_by(UserErrorEvent.created_at.asc())
        ).scalars().all()
        out: list[dict[str, Any]] = []
        for row in rows:
            metadata = dict(row.source_metadata or {})
            if metadata.get("mode") != "QUICK_QA":
                continue
            out.append(
                {
                    "id": str(row.id),
                    "original_text": row.original_text,
                    "corrected_text": row.corrected_text,
                    "error_type": row.error_type,
                    "error_dimension": row.error_dimension,
                    "error_subtype": row.error_subtype,
                    "error_pattern": row.error_pattern,
                    "confidence": row.confidence,
                    "source_metadata": metadata,
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                }
            )
        return out
    finally:
        db.close()


def read_cost_window(since_iso: str) -> list[dict[str, Any]]:
    path = REPO_ROOT / "data" / "observability" / "llm_calls.jsonl"
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("ts") or "") >= since_iso:
                rows.append(row)
    return rows


def summarize_cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "calls": len(rows),
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
        "cost_usd": round(sum(float(row.get("cost_usd") or 0.0) for row in rows), 8),
        "errors": sum(1 for row in rows if row.get("status") != "ok"),
        "by_provider": Counter(str(row.get("provider") or "<none>") for row in rows),
        "by_model": Counter(str(row.get("model") or "<none>") for row in rows),
    }


def render_md(report: dict[str, Any]) -> str:
    metrics = report["metrics"]
    run = report["run"]
    lines = [
        "# Reddit-MultiGEC QUICK_QA Error Recall Evaluation\n\n",
        f"- **Dataset:** {run['dataset']} ({run['dataset_url']})\n",
        f"- **Language:** {run['language']}\n",
        f"- **Sample size:** {run['sample_size']} / {run['english_rows_available']}\n",
        f"- **Seed:** {run['seed']}\n",
        f"- **Backend:** {run['backend_url']}\n\n",
        "## Metrics\n\n",
        "| Metric | Value |\n|---|---:|\n",
        f"| Edit recall | {metrics['edit_recall'] * 100:.2f}% |\n",
        f"| Matched / gold edits | {metrics['matched_gold_edits']} / {metrics['total_gold_edits']} |\n",
        f"| Sentence full-match rate | {metrics['sentence_full_match_rate'] * 100:.2f}% |\n",
        f"| Sample coverage | {metrics['sample_coverage'] * 100:.2f}% |\n",
        f"| False positive events | {metrics['false_positive_events']} |\n",
        f"| Failed requests | {metrics['failed_requests']} |\n\n",
        "## Top Missed Edits\n\n",
    ]
    if report["top_missed_edits"]:
        lines.append("| Wrong | Correct | Count |\n|---|---|---:|\n")
        for item in report["top_missed_edits"]:
            lines.append(f"| {item['wrong']} | {item['correct']} | {item['count']} |\n")
    else:
        lines.append("No missed edits.\n")
    return "".join(lines)


def run_eval(args: argparse.Namespace) -> dict[str, Any]:
    started_iso = now_iso()
    dataset_path = download_english_dataset(Path(args.cache), force=args.refresh_dataset)
    english_rows = load_english_rows(dataset_path)
    selected_rows = sample_rows(english_rows, sample_size=args.sample_size, seed=args.seed)

    with httpx.Client() as client:
        ready = client.get(f"{args.backend.rstrip('/')}/ready", timeout=15)
        if ready.status_code != 200:
            raise RuntimeError(f"Backend is not ready: HTTP {ready.status_code} {ready.text[:300]}")
        user = ensure_eval_user(client, args.backend.rstrip("/"))
        user_id = user["user_id"]
        requests_for_user = 0

        sample_results: list[dict[str, Any]] = []
        for idx, row in enumerate(selected_rows, start=1):
            if args.requests_per_user > 0 and requests_for_user >= args.requests_per_user:
                user = ensure_eval_user(client, args.backend.rstrip("/"))
                user_id = user["user_id"]
                requests_for_user = 0

            gold_edits = build_gold_edits(row["text"], row["correction"])
            sample_started = datetime.utcnow()
            payload = {
                "user_id": user_id,
                "type": "QUICK_QA",
                "message": (
                    "Please check this English sentence for grammar, vocabulary, spelling, "
                    f"and naturalness errors. Sentence: \"{row['text']}\""
                ),
            }
            request_started = time.perf_counter()
            status = "ok"
            response_body: dict[str, Any] = {}
            try:
                response = client.post(f"{args.backend.rstrip('/')}/api/v1/chat", json=payload, timeout=args.timeout)
                requests_for_user += 1
                latency_s = time.perf_counter() - request_started
                if response.status_code != 200:
                    status = f"http_{response.status_code}"
                    response_body = {"raw": response.text[:1000]}
                else:
                    response_body = response.json()
            except Exception as exc:
                latency_s = time.perf_counter() - request_started
                status = f"exception:{type(exc).__name__}"
                response_body = {"error": str(exc)}

            events = query_quick_qa_events(user_id, sample_started) if status == "ok" else []
            score = score_events(gold_edits, events)
            sample_results.append(
                {
                    "id": f"english-{row['dataset_index']}",
                    "dataset_index": row["dataset_index"],
                    "status": status,
                    "latency_s": round(latency_s, 3),
                    "text": row["text"],
                    "correction": row["correction"],
                    "gold_edits": [edit.as_dict() for edit in gold_edits],
                    "captured_events": events,
                    "matched_edits": score["matched_edits"],
                    "total_gold_edits": score["gold_edits"],
                    "edit_recall": round(score["edit_recall"], 4),
                    "sentence_full_match": score["sentence_full_match"],
                    "false_positive_events": score["false_positive_events"],
                    "missed_edits": score["missed_edits"],
                    "response_intent": (response_body.get("intent") if isinstance(response_body, dict) else None),
                }
            )
            if args.progress_every > 0 and idx % args.progress_every == 0:
                ok_so_far = sum(1 for item in sample_results if item["status"] == "ok")
                matched_so_far = sum(item["matched_edits"] for item in sample_results if item["status"] == "ok")
                total_so_far = sum(item["total_gold_edits"] for item in sample_results if item["status"] == "ok")
                recall_so_far = matched_so_far / total_so_far if total_so_far else 0.0
                print(
                    json.dumps(
                        {
                            "progress": idx,
                            "ok": ok_so_far,
                            "edit_recall_so_far": round(recall_so_far, 4),
                            "matched_gold_edits": matched_so_far,
                            "total_gold_edits": total_so_far,
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
            if args.limit and idx >= args.limit:
                break

    ok_samples = [row for row in sample_results if row["status"] == "ok"]
    total_gold = sum(row["total_gold_edits"] for row in ok_samples)
    matched_gold = sum(row["matched_edits"] for row in ok_samples)
    missed_counter = Counter(
        (missed.get("wrong", ""), missed.get("correct", ""))
        for row in ok_samples
        for missed in row["missed_edits"]
    )
    cost = summarize_cost(read_cost_window(started_iso))
    report = {
        "run": {
            "started_iso": started_iso,
            "ended_iso": now_iso(),
            "dataset": DATASET_NAME,
            "dataset_url": DATASET_URL,
            "dataset_cache": str(dataset_path),
            "language": DATASET_LANGUAGE,
            "sample_size": len(sample_results),
            "english_rows_available": len(english_rows),
            "seed": args.seed,
            "backend_url": args.backend.rstrip("/"),
            "config": {"quick_qa_error_capture_expected": True},
        },
        "metrics": {
            "edit_recall": matched_gold / total_gold if total_gold else 0.0,
            "matched_gold_edits": matched_gold,
            "total_gold_edits": total_gold,
            "sentence_full_match_rate": (
                sum(1 for row in ok_samples if row["sentence_full_match"]) / len(ok_samples)
                if ok_samples
                else 0.0
            ),
            "sample_coverage": len(ok_samples) / len(sample_results) if sample_results else 0.0,
            "false_positive_events": sum(row["false_positive_events"] for row in ok_samples),
            "failed_requests": len(sample_results) - len(ok_samples),
        },
        "cost": {
            **cost,
            "by_provider": dict(cost["by_provider"]),
            "by_model": dict(cost["by_model"]),
        },
        "top_missed_edits": [
            {"wrong": wrong, "correct": correct, "count": count}
            for (wrong, correct), count in missed_counter.most_common(20)
        ],
        "samples": sample_results,
    }

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "reddit_multigec_quick_qa_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (REPORT_DIR / "reddit_multigec_quick_qa_report.md").write_text(render_md(report), encoding="utf-8")
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate QUICK_QA English error recall on Reddit-MultiGEC.")
    parser.add_argument("--backend", default="http://localhost:8000")
    parser.add_argument("--sample-size", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=134)
    parser.add_argument("--cache", default=str(DEFAULT_CACHE), help="English-only dataset cache path.")
    parser.add_argument("--refresh-dataset", action="store_true")
    parser.add_argument("--timeout", type=float, default=90.0)
    parser.add_argument("--limit", type=int, default=0, help="Optional hard stop for smoke runs.")
    parser.add_argument("--requests-per-user", type=int, default=45, help="Rotate eval users before hitting chat rate limits.")
    parser.add_argument("--progress-every", type=int, default=25, help="Print JSON progress every N samples.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    report = run_eval(args)
    print(json.dumps({"run": report["run"], "metrics": report["metrics"], "cost": report["cost"]}, ensure_ascii=False, indent=2))
    return 0 if report["metrics"]["failed_requests"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
