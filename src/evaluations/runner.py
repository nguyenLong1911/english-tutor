from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from .models import CaseResult, EvalCase, EvalStep, StepResult, Verdict
from .reporters import render_markdown_report, write_json, write_jsonl


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "data" / "evaluation" / "memory_recall" / "memory_recall.v1.jsonl"
DEFAULT_OUT = REPO_ROOT / "docs" / "evaluation" / "runs"
DEFAULT_DATA_OUT = REPO_ROOT / "data" / "evaluation" / "runs"
COST_LOG = REPO_ROOT / "data" / "observability" / "llm_calls.jsonl"
DEFAULT_PASSWORD = "Eval-Pass-2026!"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO_ROOT, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            raw = line.strip()
            if not raw:
                continue
            payload = json.loads(raw)
            steps = [
                EvalStep(
                    id=str(step["id"]),
                    action=str(step["action"]),
                    user=str(step.get("user") or "primary"),
                    message=step.get("message"),
                    message_type=str(step.get("message_type") or "PRACTICE"),
                    expect=dict(step.get("expect") or {}),
                )
                for step in payload.get("steps", [])
            ]
            if not steps:
                raise ValueError(f"{path}:{line_no}: case has no steps")
            cases.append(
                EvalCase(
                    id=str(payload["id"]),
                    title=str(payload["title"]),
                    priority=str(payload.get("priority") or "P1"),
                    objective=str(payload.get("objective") or ""),
                    persona=dict(payload.get("persona") or {}),
                    steps=steps,
                    evidence=dict(payload.get("evidence") or {}),
                )
            )
    return cases


def _write_dataset_snapshot(dataset: Path, run_dir: Path) -> None:
    shutil.copy2(dataset, run_dir / "dataset_snapshot.jsonl")


def _copy_screenshots(src: Path | None, run_dir: Path) -> list[str]:
    screenshot_dir = run_dir / "screenshots"
    screenshot_dir.mkdir(parents=True, exist_ok=True)
    if src is None or not src.exists():
        return []
    copied: list[str] = []
    for path in sorted(src.iterdir()):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
            continue
        target = screenshot_dir / path.name
        shutil.copy2(path, target)
        copied.append(str(target.relative_to(run_dir)))
    return copied


def _cost_rows_since(started_at: str) -> list[dict[str, Any]]:
    if not COST_LOG.exists():
        return []
    rows: list[dict[str, Any]] = []
    with COST_LOG.open("r", encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("ts") or "") >= started_at and str(row.get("caller") or "").startswith("backend.chat"):
                rows.append(row)
    return rows


def _pct(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(p / 100.0 * (len(ordered) - 1)))))
    return round(ordered[idx], 2)


def _summarize_cost(rows: list[dict[str, Any]]) -> dict[str, Any]:
    latencies = [float(row.get("latency_ms") or 0) for row in rows if row.get("status") == "ok"]
    return {
        "calls": len(rows),
        "prompt_tokens": sum(int(row.get("prompt_tokens") or 0) for row in rows),
        "completion_tokens": sum(int(row.get("completion_tokens") or 0) for row in rows),
        "cost_usd": round(sum(float(row.get("cost_usd") or 0.0) for row in rows), 8),
        "llm_error_calls": sum(1 for row in rows if row.get("status") != "ok"),
        "llm_latency_ms": {"p50": _pct(latencies, 50), "p95": _pct(latencies, 95), "p99": _pct(latencies, 99)},
    }


def _contains_any(text: str, needles: list[str]) -> tuple[bool, list[str]]:
    normalized = text.lower()
    hits = [needle for needle in needles if str(needle).lower() in normalized]
    return bool(hits), hits


def _check_expectation(status_code: int, response_text: str, latency_ms: int, expect: dict[str, Any]) -> tuple[Verdict, dict[str, Any], str]:
    checks: dict[str, Any] = {"status_code": status_code}
    expected_status = expect.get("status_code")
    expected_any = expect.get("status_code_any")
    if expected_status is not None:
        checks["status_code_match"] = status_code == int(expected_status)
        if not checks["status_code_match"]:
            return "fail", checks, f"Expected HTTP {expected_status}, got {status_code}."
    if expected_any is not None:
        allowed = {int(item) for item in expected_any}
        checks["status_code_any_match"] = status_code in allowed
        if not checks["status_code_any_match"]:
            return "fail", checks, f"Expected HTTP in {sorted(allowed)}, got {status_code}."

    max_latency = expect.get("max_latency_ms")
    if max_latency is not None:
        checks["max_latency_ms"] = int(max_latency)
        checks["latency_ok"] = latency_ms <= int(max_latency)
        if not checks["latency_ok"]:
            return "fail", checks, f"Expected latency <= {max_latency}ms, got {latency_ms}ms."

    must_include = [str(item) for item in expect.get("must_include_any") or []]
    if must_include:
        ok, hits = _contains_any(response_text, must_include)
        checks["must_include_any"] = must_include
        checks["matched_include"] = hits
        if not ok:
            return "fail", checks, f"Response did not include any expected memory cue: {must_include}."

    must_not_include = [str(item) for item in expect.get("must_not_include_any") or []]
    if must_not_include:
        bad, hits = _contains_any(response_text, must_not_include)
        checks["must_not_include_any"] = must_not_include
        checks["matched_forbidden"] = hits
        if bad:
            return "fail", checks, f"Response included forbidden/cross-user cue: {hits}."

    return "pass", checks, "Step met expected checks."


class MemoryRecallRunner:
    def __init__(self, *, backend_url: str, run_id: str, settle_seconds: float) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.run_id = run_id
        self.settle_seconds = settle_seconds
        self.users: dict[str, dict[str, Any]] = {}

    def _trace_id(self, case_id: str, step_id: str) -> str:
        return f"{self.run_id}.{case_id}.{step_id}"[:96]

    def check_ready(self, client: httpx.Client) -> dict[str, Any]:
        response = client.get(f"{self.backend_url}/ready", timeout=10)
        payload = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"raw": response.text}
        payload["http_status"] = response.status_code
        return payload

    def ensure_user(self, client: httpx.Client, label: str, persona: dict[str, Any]) -> dict[str, Any]:
        existing = self.users.get(label)
        if existing is not None:
            return existing

        email = f"eval-memory-{self.run_id.lower()}-{label}-{uuid.uuid4().hex[:6]}@a20.test"
        payload = {
            "email": email,
            "password": DEFAULT_PASSWORD,
            "cefr_level": persona.get("cefr_level") or "B1",
            "industry": persona.get("industry") or "IT",
            "learning_goals": persona.get("learning_goals") or ["general"],
        }
        response = client.post(f"{self.backend_url}/api/v1/auth/register", json=payload, timeout=20)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"Could not create eval user {label}: HTTP {response.status_code} {response.text[:200]}")
        user = {"user_id": response.json()["user_id"], "email": email, "password": DEFAULT_PASSWORD, "client": client}
        self.users[label] = user
        return user

    def run_step(self, client: httpx.Client, case: EvalCase, step: EvalStep) -> StepResult:
        user = self.ensure_user(client, step.user, case.persona)
        trace_id = self._trace_id(case.id, step.id)
        started = time.perf_counter()
        request_payload: dict[str, Any] = {}
        response_payload: dict[str, Any] = {}

        try:
            if step.action == "chat":
                request_payload = {
                    "user_id": user["user_id"],
                    "message": step.message,
                    "type": step.message_type,
                }
                response = client.post(
                    f"{self.backend_url}/api/v1/chat",
                    json=request_payload,
                    headers={"X-Trace-Id": trace_id},
                    timeout=90,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                response_payload = self._response_payload(response)
                response_text = json.dumps(response_payload, ensure_ascii=False)
                verdict, checks, feedback = _check_expectation(response.status_code, response_text, latency_ms, step.expect)
                return StepResult(case.id, step.id, step.action, verdict, trace_id, latency_ms, feedback, request_payload, response_payload, checks)

            if step.action == "reset_session":
                request_payload = {"user_id": user["user_id"]}
                response = client.delete(
                    f"{self.backend_url}/api/v1/session/{user['user_id']}",
                    headers={"X-Trace-Id": trace_id},
                    timeout=30,
                )
                if self.settle_seconds > 0:
                    time.sleep(self.settle_seconds)
                latency_ms = int((time.perf_counter() - started) * 1000)
                response_payload = self._response_payload(response)
                verdict, checks, feedback = _check_expectation(response.status_code, json.dumps(response_payload), latency_ms, step.expect)
                return StepResult(case.id, step.id, step.action, verdict, trace_id, latency_ms, feedback, request_payload, response_payload, checks)

            if step.action == "gdpr_delete":
                request_payload = {"password": DEFAULT_PASSWORD}
                response = client.post(
                    f"{self.backend_url}/api/v1/gdpr/delete",
                    json=request_payload,
                    headers={"X-Trace-Id": trace_id},
                    timeout=40,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                response_payload = self._response_payload(response)
                verdict, checks, feedback = _check_expectation(response.status_code, json.dumps(response_payload), latency_ms, step.expect)
                return StepResult(case.id, step.id, step.action, verdict, trace_id, latency_ms, feedback, {"password": "<redacted>"}, response_payload, checks)

            if step.action == "get_user":
                request_payload = {"user_id": user["user_id"]}
                response = client.get(
                    f"{self.backend_url}/api/v1/user/{user['user_id']}",
                    headers={"X-Trace-Id": trace_id},
                    timeout=20,
                )
                latency_ms = int((time.perf_counter() - started) * 1000)
                response_payload = self._response_payload(response)
                verdict, checks, feedback = _check_expectation(response.status_code, json.dumps(response_payload), latency_ms, step.expect)
                return StepResult(case.id, step.id, step.action, verdict, trace_id, latency_ms, feedback, request_payload, response_payload, checks)

            latency_ms = int((time.perf_counter() - started) * 1000)
            return StepResult(case.id, step.id, step.action, "blocked", trace_id, latency_ms, f"Unsupported action: {step.action}", request_payload, response_payload)
        except Exception as exc:
            latency_ms = int((time.perf_counter() - started) * 1000)
            return StepResult(case.id, step.id, step.action, "error", trace_id, latency_ms, f"{type(exc).__name__}: {exc}", request_payload, response_payload)

    @staticmethod
    def _response_payload(response: httpx.Response) -> dict[str, Any]:
        base = {
            "status_code": response.status_code,
            "trace_id": response.headers.get("X-Trace-Id"),
            "response_time_ms": response.headers.get("X-Response-Time-Ms"),
        }
        try:
            body = response.json()
        except Exception:
            body = {"raw": response.text[:1000]}
        return {**base, "body": body}

    def run_case(self, case: EvalCase) -> CaseResult:
        with httpx.Client() as client:
            self.users = {}
            steps: list[StepResult] = []
            for label in ("primary", "secondary"):
                self.ensure_user(client, label, case.persona)
            for step in case.steps:
                result = self.run_step(client, case, step)
                steps.append(result)
                if result.verdict in {"blocked", "error"}:
                    break
            verdict = _case_verdict(steps)
            feedback = _case_feedback(steps)
            return CaseResult(case=case, verdict=verdict, feedback=feedback, steps=steps)


def _case_verdict(steps: list[StepResult]) -> Verdict:
    if any(step.verdict == "error" for step in steps):
        return "error"
    if any(step.verdict == "blocked" for step in steps):
        return "blocked"
    if any(step.verdict == "fail" for step in steps):
        return "fail"
    return "pass"


def _case_feedback(steps: list[StepResult]) -> str:
    first_bad = next((step for step in steps if step.verdict != "pass"), None)
    if first_bad is None:
        return "All steps passed for this memory evidence case."
    return f"{first_bad.step_id}: {first_bad.feedback}"


def _build_summary(case_results: list[CaseResult], cost: dict[str, Any]) -> dict[str, Any]:
    counts = {"pass": 0, "fail": 0, "blocked": 0, "error": 0}
    for result in case_results:
        counts[result.verdict] += 1
    step_results = [step for case in case_results for step in case.steps]
    chat_steps = [step for step in step_results if step.action == "chat"]
    reset_steps = [step for step in step_results if step.action == "reset_session"]
    isolation = next((case for case in case_results if case.case.id == "MR-04-cross-user-isolation"), None)
    delete_case = next((case for case in case_results if case.case.id == "MR-05-delete-data-memory"), None)
    pass_rate = counts["pass"] / max(len(case_results), 1)
    decision = "pass" if counts["fail"] == 0 and counts["error"] == 0 and counts["blocked"] == 0 else "needs_attention"
    if any(result.verdict in {"fail", "error"} and result.case.priority == "P0" for result in case_results):
        decision = "no_go_for_memory_claim"

    latencies = [step.latency_ms for step in chat_steps]
    return {
        **counts,
        "total_cases": len(case_results),
        "decision": decision,
        "metrics": {
            "case_pass_rate": round(pass_rate, 4),
            "chat_step_pass_rate": round(sum(1 for step in chat_steps if step.verdict == "pass") / max(len(chat_steps), 1), 4),
            "memory_recall_cases_passed": sum(1 for case in case_results if case.case.id.startswith("MR-0") and case.verdict == "pass"),
            "session_reset_steps_passed": sum(1 for step in reset_steps if step.verdict == "pass"),
            "cross_user_isolation_passed": bool(isolation and isolation.verdict == "pass"),
            "delete_data_verified": bool(delete_case and delete_case.verdict == "pass"),
            "chat_latency_p50_ms": _pct(latencies, 50),
            "chat_latency_p95_ms": _pct(latencies, 95),
            "llm_calls": cost["calls"],
            "llm_cost_usd": cost["cost_usd"],
        },
        "cost": cost,
    }


def run(args: argparse.Namespace) -> int:
    if args.suite == "english_error_span_delta":
        from .english_error_span_delta import DEFAULT_DATASET as ENGLISH_ERROR_SPAN_DATASET
        from .english_error_span_delta import run as run_english_error_span_delta

        if Path(args.dataset).resolve() == DEFAULT_DATASET.resolve():
            args.dataset = str(ENGLISH_ERROR_SPAN_DATASET)
        return run_english_error_span_delta(args)

    dataset = Path(args.dataset).resolve()
    dataset_text = dataset.read_text(encoding="utf-8")
    cases = _load_cases(dataset)
    run_id = args.run_id or f"memory_recall_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    docs_run_dir = Path(args.out).resolve() / run_id
    data_run_dir = Path(args.data_out).resolve() / run_id
    docs_run_dir.mkdir(parents=True, exist_ok=True)
    data_run_dir.mkdir(parents=True, exist_ok=True)
    started_at = _now_iso()
    screenshot_inventory = _copy_screenshots(Path(args.screenshots_dir).resolve() if args.screenshots_dir else None, docs_run_dir)
    _write_dataset_snapshot(dataset, data_run_dir)

    runner = MemoryRecallRunner(backend_url=args.backend, run_id=run_id, settle_seconds=args.settle_seconds)
    ready_payload: dict[str, Any]
    with httpx.Client() as client:
        try:
            ready_payload = runner.check_ready(client)
        except Exception as exc:
            ready_payload = {"http_status": None, "error": f"{type(exc).__name__}: {exc}"}

    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "ended_at": None,
        "backend_url": args.backend,
        "suite": "memory_recall",
        "dataset": str(dataset),
        "dataset_version": dataset.stem,
        "dataset_sha256": _sha256_text(dataset_text),
        "git_branch": _run_git(["rev-parse", "--abbrev-ref", "HEAD"]),
        "git_commit": _run_git(["rev-parse", "HEAD"]),
        "prompt_hash": _sha256_text(dataset_text + "|" + str((REPO_ROOT / "src/apps/backend/app/services/scaffolding_engine.py").read_text(encoding="utf-8", errors="ignore"))),
        "config_snapshot": {
            "backend_ready": ready_payload,
            "settle_seconds": args.settle_seconds,
            "screenshots_dir": args.screenshots_dir,
        },
        "data_run_dir": str(data_run_dir),
        "docs_run_dir": str(docs_run_dir),
        "trace_ids": [],
    }

    if ready_payload.get("http_status") != 200:
        ended_at = _now_iso()
        manifest["ended_at"] = ended_at
        blocked_summary = {
            "total_cases": len(cases),
            "pass": 0,
            "fail": 0,
            "blocked": len(cases),
            "error": 0,
            "decision": "blocked",
            "metrics": {},
            "blocker": "Backend /ready did not return HTTP 200.",
        }
        write_json(data_run_dir / "manifest.json", manifest)
        write_jsonl(data_run_dir / "results.jsonl", [])
        write_json(data_run_dir / "summary.json", blocked_summary)
        (docs_run_dir / "report.md").write_text(
            render_markdown_report(manifest=manifest, summary=blocked_summary, case_results=[], screenshot_inventory=screenshot_inventory),
            encoding="utf-8",
        )
        print(f"Evaluation blocked. Data: {data_run_dir} Docs: {docs_run_dir}")
        return 2

    case_results = [runner.run_case(case) for case in cases]
    ended_at = _now_iso()
    manifest["ended_at"] = ended_at
    manifest["trace_ids"] = [step.trace_id for case in case_results for step in case.steps]
    cost = _summarize_cost(_cost_rows_since(started_at))
    summary = _build_summary(case_results, cost)
    result_rows = [case.as_dict() for case in case_results]

    write_json(data_run_dir / "manifest.json", manifest)
    write_jsonl(data_run_dir / "results.jsonl", result_rows)
    write_json(data_run_dir / "summary.json", summary)
    (docs_run_dir / "report.md").write_text(
        render_markdown_report(
            manifest=manifest,
            summary=summary,
            case_results=result_rows,
            screenshot_inventory=screenshot_inventory,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"run_id": run_id, "data_run_dir": str(data_run_dir), "docs_run_dir": str(docs_run_dir), "summary": summary}, ensure_ascii=False, indent=2))
    return 0 if summary["decision"] == "pass" else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evaluate focused A20 backend flows.")
    parser.add_argument(
        "--suite",
        default="memory_recall",
        choices=["memory_recall", "english_error_span_delta"],
        help="Evaluation suite to run.",
    )
    parser.add_argument("--backend", default=os.getenv("EVAL_BACKEND_URL", "http://localhost:8000"))
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--data-out", default=str(DEFAULT_DATA_OUT), help="Machine-readable evaluation artifacts output directory.")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--settle-seconds", type=float, default=1.0, help="Wait after session reset/flush before recall probe.")
    parser.add_argument("--screenshots-dir", default="", help="Optional folder of UI screenshots to copy into the run evidence.")
    parser.add_argument("--sample-size", type=int, default=100, help="Number of dataset rows for dataset-backed suites.")
    parser.add_argument("--gold-delta", default="", help="Existing gold_delta.jsonl to evaluate directly without regenerating gold labels.")
    parser.add_argument("--gold-model", default="gemini-2.5-pro", help="Gemini model used to create gold labels.")
    parser.add_argument("--gold-timeout", type=float, default=90.0, help="Evaluation-only timeout for Gemini gold-label calls.")
    parser.add_argument("--gold-retries", type=int, default=3, help="Evaluation-only retry count for Gemini gold-label calls.")
    parser.add_argument("--gold-max-tokens", type=int, default=8192, help="Evaluation-only output budget for Gemini gold-label calls.")
    parser.add_argument("--timeout", type=float, default=90.0, help="Per-request timeout for live backend evaluation calls.")
    parser.add_argument("--requests-per-user", type=int, default=45, help="Rotate eval users before hitting chat rate limits.")
    parser.add_argument("--progress-every", type=int, default=1, help="Print and flush progress every N dataset rows.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
