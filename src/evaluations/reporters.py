from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def render_markdown_report(
    *,
    manifest: dict[str, Any],
    summary: dict[str, Any],
    case_results: list[dict[str, Any]],
    screenshot_inventory: list[str],
) -> str:
    lines: list[str] = []
    lines.append("# Memory Recall Evaluation Report\n\n")
    lines.append("## Scope\n\n")
    lines.append(
        "This run evaluates only the learner-error memory flow: capture a learner mistake, "
        "retrieve it in a later context, use it in chatbot feedback, verify isolation, and verify deletion evidence.\n\n"
    )

    lines.append("## Run Metadata\n\n")
    lines.append("| Field | Value |\n|---|---|\n")
    for key in ("run_id", "started_at", "ended_at", "backend_url", "suite", "dataset_version", "git_branch", "git_commit"):
        lines.append(f"| {key} | {manifest.get(key, '')} |\n")
    lines.append("\n")

    lines.append("## Metrics\n\n")
    lines.append("| Metric | Value |\n|---|---:|\n")
    for key, value in summary.get("metrics", {}).items():
        lines.append(f"| {key} | {value} |\n")
    lines.append("\n")

    lines.append("## Gate\n\n")
    lines.append(f"- Decision: **{summary.get('decision', 'unknown')}**\n")
    lines.append(f"- Pass: **{summary.get('pass', 0)}**\n")
    lines.append(f"- Fail: **{summary.get('fail', 0)}**\n")
    lines.append(f"- Blocked: **{summary.get('blocked', 0)}**\n")
    lines.append(f"- Error: **{summary.get('error', 0)}**\n\n")

    lines.append("## Test Questions\n\n")
    lines.append("| Case | Step | Action | Prompt |\n|---|---|---|---|\n")
    for case in case_results:
        for step in case["steps"]:
            prompt = str(step.get("request", {}).get("message") or "").replace("\n", " ")
            lines.append(f"| {case['id']} | {step['step_id']} | {step['action']} | {prompt[:140]} |\n")
    lines.append("\n")

    lines.append("## Results And Feedback\n\n")
    lines.append("| Case | Priority | Verdict | Feedback |\n|---|---|---|---|\n")
    for case in case_results:
        feedback = str(case.get("feedback") or "").replace("\n", " ")
        lines.append(f"| {case['id']} | {case['priority']} | {case['verdict']} | {feedback} |\n")
    lines.append("\n")

    lines.append("## Evidence Checklist\n\n")
    lines.append("- Report: `report.md`\n")
    lines.append("- Structured test results: `results.jsonl`\n")
    lines.append("- Machine-readable metrics/gate: `summary.json`\n")
    lines.append("- Test questions and expected checks: `dataset_snapshot.jsonl`\n")
    lines.append("- Run metadata: `manifest.json`\n")
    lines.append("- Manual/UI screenshots: `screenshots/` or paths listed below\n\n")

    lines.append("## Screenshot Inventory\n\n")
    if screenshot_inventory:
        for item in screenshot_inventory:
            lines.append(f"- `{item}`\n")
    else:
        lines.append("- No screenshot files were supplied. Add UI screenshots to this run folder or pass `--screenshots-dir`.\n")
    lines.append("\n")

    lines.append("## Required Screenshots For This Flow\n\n")
    lines.append("- Learner sends an incorrect English sentence.\n")
    lines.append("- Chatbot gives correction/hint and records the error.\n")
    lines.append("- A new session asks what mistakes the learner makes.\n")
    lines.append("- Chatbot recalls the previous error in the response.\n")
    lines.append("- A different user does not see the original user's error.\n")
    lines.append("- Delete-data action completes for the eval user.\n")
    return "".join(lines)
