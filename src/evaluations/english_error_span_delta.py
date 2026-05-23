from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import time
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
import requests

from .reporters import write_json, write_jsonl


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = REPO_ROOT / "data" / "raw" / "huggingface" / "reddit_multigec" / "reddit_multi_gec_english.csv"
DEFAULT_OUT = REPO_ROOT / "docs" / "evaluation" / "runs"
DEFAULT_DATA_OUT = REPO_ROOT / "data" / "evaluation" / "runs"
DEFAULT_PASSWORD = "Eval-Pass-2026!"
SYSTEM_PROMPT_TEMPLATE = """Return only a JSON array of incorrect spans from the learner sentence. No explanation, no corrected sentence.

Rules:
- Each array item must be copied verbatim from the learner sentence.
- Include only the text that is wrong, not the corrected replacement.
- If there are no errors, return [].

Learner sentence:
{text}
"""


class EvalBlocked(RuntimeError):
    pass


def load_eval_env() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    load_dotenv(REPO_ROOT / "src" / ".env", override=False)


@dataclass(frozen=True)
class EnglishErrorRow:
    index: int
    text: str
    correction: str


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_first_rows(csv_path: Path, sample_size: int) -> list[EnglishErrorRow]:
    rows: list[EnglishErrorRow] = []
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"language", "text", "correction"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"{csv_path} is missing columns: {sorted(missing)}")
        for dataset_index, row in enumerate(reader):
            if str(row.get("language") or "").strip().lower() != "english":
                continue
            text = str(row.get("text") or "").strip()
            correction = str(row.get("correction") or "").strip()
            if not text or not correction or text == correction:
                continue
            rows.append(EnglishErrorRow(index=dataset_index, text=text, correction=correction))
            if len(rows) >= sample_size:
                break
    return rows


def write_dataset_snapshot(rows: list[EnglishErrorRow], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset_index", "language", "text", "correction"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "dataset_index": row.index,
                    "language": "english",
                    "text": row.text,
                    "correction": row.correction,
                }
            )


def extract_json_array(text: str) -> list[str] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^`{1,3}(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*`{1,3}$", "", cleaned)

    candidates = [cleaned]
    start = cleaned.find("[")
    end = cleaned.rfind("]")
    object_start = cleaned.find("{")
    if start != -1 and end > start and (object_start == -1 or start < object_start):
        candidates.append(cleaned[start : end + 1])

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, list) and all(isinstance(item, str) for item in parsed):
            return [item.strip() for item in parsed if item.strip()]
    return None


def normalize_span(value: str) -> str:
    lowered = str(value or "").lower().replace("’", "'").replace("`", "'")
    lowered = re.sub(r"[^a-z0-9']+", " ", lowered)
    return re.sub(r"\s+", " ", lowered).strip()


def _tokens(value: str) -> set[str]:
    normalized = normalize_span(value)
    return set(normalized.split()) if normalized else set()


def spans_match(gold: str, observed: str) -> bool:
    gold_norm = normalize_span(gold)
    observed_norm = normalize_span(observed)
    if not gold_norm or not observed_norm:
        return False
    if gold_norm in observed_norm or observed_norm in gold_norm:
        return True

    gold_tokens = _tokens(gold_norm)
    observed_tokens = _tokens(observed_norm)
    if not gold_tokens or not observed_tokens:
        return False
    overlap = len(gold_tokens & observed_tokens)
    return overlap / max(len(gold_tokens), len(observed_tokens)) >= 0.5


def score_spans(gold_spans: list[str], system_spans: list[str]) -> dict[str, Any]:
    matched_gold: set[int] = set()
    matched_system: set[int] = set()
    for gold_index, gold in enumerate(gold_spans):
        for system_index, observed in enumerate(system_spans):
            if system_index in matched_system:
                continue
            if spans_match(gold, observed):
                matched_gold.add(gold_index)
                matched_system.add(system_index)
                break

    matched = len(matched_gold)
    precision = matched / len(system_spans) if system_spans else (1.0 if not gold_spans else 0.0)
    recall = matched / len(gold_spans) if gold_spans else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    return {
        "matched_spans": matched,
        "gold_spans": len(gold_spans),
        "system_spans": len(system_spans),
        "span_precision": precision,
        "span_recall": recall,
        "span_f1": f1,
        "sentence_full_match": bool(gold_spans) and matched == len(gold_spans) and len(system_spans) == matched,
        "missed_spans": [span for index, span in enumerate(gold_spans) if index not in matched_gold],
        "false_positive_spans": [span for index, span in enumerate(system_spans) if index not in matched_system],
    }


def _filter_gold_spans(raw_spans: list[str], source_text: str) -> list[str]:
    source_norm = normalize_span(source_text)
    filtered: list[str] = []
    seen: set[str] = set()
    for span in raw_spans:
        normalized = normalize_span(span)
        if not normalized or normalized in seen:
            continue
        if normalized not in source_norm and not any(spans_match(span, token) for token in re.findall(r"[A-Za-z']+|\d+(?:[.,]\d+)?|[^\w\s]", source_text)):
            continue
        seen.add(normalized)
        filtered.append(span.strip())
    return filtered


def _gold_prompt(row: EnglishErrorRow) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You create gold labels for grammar correction evaluation. "
                "Compare an original learner sentence against its corrected version. "
                "Return ONLY a JSON array of incorrect spans copied verbatim from the original sentence. "
                "Do not include corrected replacements. Ignore pure insertions where no original span exists."
            ),
        },
        {
            "role": "user",
            "content": f"Original learner sentence:\n{row.text}\n\nCorrected sentence:\n{row.correction}",
        },
    ]


class EvalGeminiGoldClient:
    """Evaluation-only Gemini client with longer timeout/retry settings.

    This intentionally does not use app.utils.llm.GeminiLLMClient so production
    chat timeouts and fallback behavior remain unchanged.
    """

    def __init__(self, *, model: str, timeout: float, retries: int) -> None:
        self.model = model
        self.timeout = timeout
        self.retries = max(1, retries)
        self.api_key = self._pick_key()
        self.last_model: str | None = None
        self.last_usage: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    @staticmethod
    def _pick_key() -> str:
        google_key = (os.getenv("GOOGLE_API_KEY") or "").strip()
        gemini_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if google_key.startswith("AQ."):
            return google_key
        return gemini_key or google_key

    def _use_vertex(self) -> bool:
        return self.api_key.startswith("AQ.") or os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes", "on"}

    def _vertex_host(self) -> str:
        location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip() or "us-central1"
        if location == "global":
            return "https://aiplatform.googleapis.com"
        return f"https://{location}-aiplatform.googleapis.com"

    def _vertex_model_path(self) -> str:
        project = (os.getenv("GOOGLE_CLOUD_PROJECT") or "").strip()
        location = (os.getenv("GOOGLE_CLOUD_LOCATION") or "us-central1").strip() or "us-central1"
        if project:
            return f"projects/{project}/locations/{location}/publishers/google/models/{self.model}"
        return f"publishers/google/models/{self.model}"

    @staticmethod
    def _payload(messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> dict[str, Any]:
        system_parts: list[str] = []
        contents: list[dict[str, Any]] = []
        for message in messages:
            role = str(message.get("role") or "user").lower()
            content = str(message.get("content") or "")
            if not content:
                continue
            if role == "system":
                system_parts.append(content)
            else:
                contents.append({"role": "user" if role != "assistant" else "model", "parts": [{"text": content}]})

        payload: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_parts:
            payload["systemInstruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    @staticmethod
    def _text_from_response(body: dict[str, Any]) -> str:
        candidates = body.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no candidates: {str(body)[:500]}")
        parts = ((candidates[0].get("content") or {}).get("parts") or [])
        text = "".join(str(part.get("text") or "") for part in parts).strip()
        if not text:
            finish_reason = candidates[0].get("finishReason") or "UNKNOWN"
            raise RuntimeError(f"Gemini returned empty text (finish_reason={finish_reason})")
        return text

    def _request_once(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        if not self.api_key:
            raise RuntimeError("GOOGLE_API_KEY or GEMINI_API_KEY is required for gold delta generation")

        payload = self._payload(messages, temperature=temperature, max_tokens=max_tokens)
        if self._use_vertex():
            url = f"{self._vertex_host()}/v1/{self._vertex_model_path()}:generateContent"
        else:
            model = self.model if self.model.startswith("models/") else f"models/{self.model}"
            url = f"https://generativelanguage.googleapis.com/v1beta/{model}:generateContent"

        response = requests.post(url, params={"key": self.api_key}, json=payload, timeout=self.timeout)
        response.raise_for_status()
        body = response.json()
        usage = body.get("usageMetadata") or {}
        self.last_usage = {
            "prompt_tokens": int(usage.get("promptTokenCount", 0) or 0),
            "completion_tokens": int(usage.get("candidatesTokenCount", 0) or 0),
        }
        self.last_model = body.get("modelVersion") or self.model
        return self._text_from_response(body)

    async def generate(self, messages: list[dict[str, str]], *, temperature: float, max_tokens: int) -> str:
        last_error: Exception | None = None
        for attempt in range(self.retries):
            try:
                return await asyncio.to_thread(
                    self._request_once,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except Exception as exc:  # noqa: BLE001 - row-level eval retry
                last_error = exc
                if attempt + 1 >= self.retries:
                    break
                await asyncio.sleep(min(10.0, 2.0**attempt))
        raise RuntimeError(f"Eval Gemini request failed after {self.retries} attempts: {last_error}") from last_error


def _append_jsonl(path: Path, row: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            raw = line.strip()
            if not raw:
                continue
            rows.append(json.loads(raw))
    return rows


def _dedupe_rows_by_dataset_index(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_index: dict[int, dict[str, Any]] = {}
    for row in rows:
        if "dataset_index" not in row:
            continue
        dataset_index = int(row["dataset_index"])
        existing = by_index.get(dataset_index)
        if existing is None:
            by_index[dataset_index] = row
            continue
        current_ok = str(row.get("gold_status") or row.get("status") or "") == "ok"
        existing_ok = str(existing.get("gold_status") or existing.get("status") or "") == "ok"
        current_spans = len(row.get("gold_spans") or [])
        existing_spans = len(existing.get("gold_spans") or [])
        if (current_ok, current_spans) >= (existing_ok, existing_spans):
            by_index[dataset_index] = row
    return [by_index[index] for index in sorted(by_index)]


def load_gold_delta_rows(path: Path, sample_size: int = 0) -> list[dict[str, Any]]:
    rows = _dedupe_rows_by_dataset_index(_load_jsonl(path))
    usable: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("text") or "").strip()
        correction = str(row.get("correction") or "").strip()
        gold_spans = row.get("gold_spans")
        if not text or not isinstance(gold_spans, list):
            continue
        usable.append(
            {
                "dataset_index": int(row["dataset_index"]),
                "text": text,
                "correction": correction,
                "gold_spans": [str(span) for span in gold_spans if str(span).strip()],
                "raw_gold_response": row.get("raw_gold_response"),
                "gold_status": str(row.get("gold_status") or "ok"),
                "gold_error": row.get("gold_error"),
                "gold_latency_ms": int(row.get("gold_latency_ms") or 0),
            }
        )
        if sample_size > 0 and len(usable) >= sample_size:
            break
    return usable


def write_gold_dataset_snapshot(rows: list[dict[str, Any]], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["dataset_index", "language", "text", "correction"])
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "dataset_index": row["dataset_index"],
                    "language": "english",
                    "text": row["text"],
                    "correction": row.get("correction") or "",
                }
            )


async def build_gold_deltas(
    rows: list[EnglishErrorRow],
    *,
    model: str,
    output_path: Path | None = None,
    progress_every: int = 1,
    request_timeout: float = 90.0,
    retries: int = 3,
    max_tokens: int = 8192,
) -> list[dict[str, Any]]:
    load_eval_env()
    client = EvalGeminiGoldClient(model=model, timeout=request_timeout, retries=retries)
    gold_rows = _dedupe_rows_by_dataset_index(_load_jsonl(output_path)) if output_path is not None else []
    completed_indexes = {int(item["dataset_index"]) for item in gold_rows if "dataset_index" in item}
    for position, row in enumerate(rows, start=1):
        if row.index in completed_indexes:
            if progress_every > 0 and position % progress_every == 0:
                print(json.dumps({"stage": "gold_delta", "progress": position, "total": len(rows), "status": "cached"}, ensure_ascii=False), flush=True)
            continue
        started_at = time.perf_counter()
        status = "ok"
        raw = ""
        spans: list[str] = []
        error = None
        try:
            raw = await client.generate(_gold_prompt(row), temperature=0.0, max_tokens=max_tokens)
            parsed = extract_json_array(raw)
            if parsed is None:
                status = "parse_error"
                error = "Gemini did not return a JSON array of strings."
            else:
                spans = _filter_gold_spans(parsed, row.text)
        except Exception as exc:  # noqa: BLE001 - eval should capture row-level errors
            status = "error"
            error = f"{type(exc).__name__}: {exc}"
        gold_row = {
            "dataset_index": row.index,
            "text": row.text,
            "correction": row.correction,
            "gold_spans": spans,
            "raw_gold_response": raw,
            "gold_status": status,
            "gold_error": error,
            "gold_latency_ms": int((time.perf_counter() - started_at) * 1000),
        }
        gold_rows.append(gold_row)
        if output_path is not None:
            _append_jsonl(output_path, gold_row)
        if progress_every > 0 and (position % progress_every == 0 or position == len(rows)):
            print(
                json.dumps(
                    {
                        "stage": "gold_delta",
                        "progress": position,
                        "total": len(rows),
                        "dataset_index": row.index,
                        "status": status,
                        "spans": len(spans),
                    },
                    ensure_ascii=False,
                ),
                flush=True,
            )
    return gold_rows


def ensure_eval_user(client: httpx.Client, backend_url: str, run_id: str) -> dict[str, str]:
    email = f"eval-span-{run_id.lower()}-{uuid.uuid4().hex[:8]}@a20.test"
    response = client.post(
        f"{backend_url}/api/v1/auth/register",
        json={
            "email": email,
            "password": DEFAULT_PASSWORD,
            "cefr_level": "B1",
            "industry": "general",
            "learning_goals": ["english error span evaluation"],
        },
        timeout=30,
    )
    if response.status_code not in {200, 201}:
        raise RuntimeError(f"Could not create eval user: HTTP {response.status_code} {response.text[:300]}")
    return {"user_id": str(response.json()["user_id"]), "email": email}


def preflight_live_eval_provider(client: httpx.Client, backend_url: str, run_id: str) -> dict[str, Any]:
    user = ensure_eval_user(client, backend_url, f"{run_id}-preflight")
    response = client.post(
        f"{backend_url}/api/v1/chat",
        json={
            "user_id": user["user_id"],
            "type": "EVAL_ERROR_SPANS",
            "message": SYSTEM_PROMPT_TEMPLATE.format(text="She go to school yesterday."),
        },
        headers={"X-Trace-Id": f"{run_id}.preflight_live_llm"},
        timeout=30,
    )
    if response.status_code != 200:
        raise EvalBlocked(f"Live LLM preflight failed: HTTP {response.status_code} {response.text[:300]}")
    payload = response.json()
    parsed = extract_json_array(str(payload.get("response") or ""))
    if parsed is None:
        raise EvalBlocked("Live LLM preflight failed: response was not a JSON array.")
    return {"status": "ok", "response": payload, "parsed_spans": parsed}


def run_system_eval(
    gold_rows: list[dict[str, Any]],
    *,
    backend_url: str,
    run_id: str,
    timeout: float,
    requests_per_user: int,
    output_path: Path | None = None,
    progress_every: int = 1,
) -> list[dict[str, Any]]:
    results = _dedupe_rows_by_dataset_index(_load_jsonl(output_path)) if output_path is not None else []
    completed_indexes = {int(item["dataset_index"]) for item in results if "dataset_index" in item}
    with httpx.Client() as client:
        ready = client.get(f"{backend_url}/ready", timeout=15)
        if ready.status_code != 200:
            raise RuntimeError(f"Backend is not ready: HTTP {ready.status_code} {ready.text[:300]}")
        preflight_live_eval_provider(client, backend_url, run_id)
        user = ensure_eval_user(client, backend_url, run_id)
        requests_for_user = 0

        for position, item in enumerate(gold_rows, start=1):
            if int(item["dataset_index"]) in completed_indexes:
                if progress_every > 0 and position % progress_every == 0:
                    print(json.dumps({"stage": "system_eval", "progress": position, "total": len(gold_rows), "status": "cached"}, ensure_ascii=False), flush=True)
                continue
            if requests_per_user > 0 and requests_for_user >= requests_per_user:
                user = ensure_eval_user(client, backend_url, run_id)
                requests_for_user = 0

            text = str(item["text"])
            message = SYSTEM_PROMPT_TEMPLATE.format(text=text)
            started_at = time.perf_counter()
            status = "ok"
            response_text = ""
            system_spans: list[str] = []
            response_payload: dict[str, Any] = {}
            error = None
            try:
                response = client.post(
                    f"{backend_url}/api/v1/chat",
                    json={"user_id": user["user_id"], "type": "EVAL_ERROR_SPANS", "message": message},
                    headers={"X-Trace-Id": f"{run_id}.{item['dataset_index']}"},
                    timeout=timeout,
                )
                requests_for_user += 1
                if response.status_code != 200:
                    if response.status_code == 503 and "live LLM provider" in response.text:
                        raise EvalBlocked(f"Live LLM became unavailable during evaluation: {response.text[:300]}")
                    status = f"http_{response.status_code}"
                    response_payload = {"raw": response.text[:1000]}
                    error = response.text[:300]
                else:
                    response_payload = response.json()
                    response_text = str(response_payload.get("response") or "")
                    parsed = extract_json_array(response_text)
                    if parsed is None:
                        status = "parse_error"
                        error = "System response was not a JSON array of strings."
                    else:
                        system_spans = parsed
            except EvalBlocked:
                raise
            except Exception as exc:  # noqa: BLE001 - eval should keep going
                status = f"exception:{type(exc).__name__}"
                error = str(exc)

            latency_ms = int((time.perf_counter() - started_at) * 1000)
            score = score_spans(list(item.get("gold_spans") or []), system_spans)
            result_row = {
                "dataset_index": item["dataset_index"],
                "status": status,
                "latency_ms": latency_ms,
                "text": text,
                "correction": item["correction"],
                "gold_status": item["gold_status"],
                "gold_spans": item["gold_spans"],
                "system_spans": system_spans,
                "response": response_payload,
                "response_text": response_text,
                "error": error,
                "score": score,
            }
            results.append(result_row)
            if output_path is not None:
                _append_jsonl(output_path, result_row)
            if progress_every > 0 and (position % progress_every == 0 or position == len(gold_rows)):
                print(
                    json.dumps(
                        {
                            "stage": "system_eval",
                            "progress": position,
                            "total": len(gold_rows),
                            "dataset_index": item["dataset_index"],
                            "status": status,
                            "gold_spans": len(item.get("gold_spans") or []),
                            "system_spans": len(system_spans),
                        },
                        ensure_ascii=False,
                    ),
                    flush=True,
                )
    return results


def _pct(values: list[int], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(p / 100.0 * (len(ordered) - 1)))))
    return float(ordered[idx])


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    gold_usable_rows = [row for row in results if row["gold_status"] == "ok"]
    ok_rows = [row for row in results if row["status"] == "ok" and row["gold_status"] == "ok"]
    scored_rows = [row for row in gold_usable_rows if int(row["score"]["gold_spans"]) > 0]
    total_gold = sum(int(row["score"]["gold_spans"]) for row in gold_usable_rows)
    total_system = sum(int(row["score"]["system_spans"]) for row in gold_usable_rows)
    total_matched = sum(int(row["score"]["matched_spans"]) for row in gold_usable_rows)
    precision = total_matched / total_system if total_system else (1.0 if total_gold == 0 else 0.0)
    recall = total_matched / total_gold if total_gold else 1.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    latencies = [int(row["latency_ms"]) for row in results if row["status"] == "ok"]
    missed_counter = Counter(
        normalize_span(span) or span
        for row in gold_usable_rows
        for span in row["score"].get("missed_spans", [])
    )
    mean_sentence_recall = sum(float(row["score"]["span_recall"]) for row in scored_rows) / len(scored_rows) if scored_rows else 0.0
    mean_sentence_precision = sum(float(row["score"]["span_precision"]) for row in scored_rows) / len(scored_rows) if scored_rows else 0.0
    mean_sentence_f1 = sum(float(row["score"]["span_f1"]) for row in scored_rows) / len(scored_rows) if scored_rows else 0.0
    return {
        "total_cases": len(results),
        "ok_cases": len(ok_rows),
        "failed_requests": sum(1 for row in results if row["status"] != "ok"),
        "gold_failed": sum(1 for row in results if row["gold_status"] != "ok"),
        "format_compliance_rate": round(len(ok_rows) / len(gold_usable_rows), 4) if gold_usable_rows else 0.0,
        "span_precision": round(precision, 4),
        "span_recall": round(recall, 4),
        "span_f1": round(f1, 4),
        "average_error_detection_rate_per_sentence": round(mean_sentence_recall, 4),
        "mean_sentence_span_recall": round(mean_sentence_recall, 4),
        "mean_sentence_span_precision": round(mean_sentence_precision, 4),
        "mean_sentence_span_f1": round(mean_sentence_f1, 4),
        "matched_spans": total_matched,
        "gold_spans": total_gold,
        "system_spans": total_system,
        "sentence_full_match_rate": round(
            sum(1 for row in ok_rows if row["score"].get("sentence_full_match")) / len(ok_rows),
            4,
        )
        if ok_rows
        else 0.0,
        "latency_ms": {"p50": _pct(latencies, 50), "p95": _pct(latencies, 95)},
        "top_missed_spans": [{"span": span, "count": count} for span, count in missed_counter.most_common(20)],
    }


def render_report(manifest: dict[str, Any], summary: dict[str, Any], results: list[dict[str, Any]]) -> str:
    lines = [
        "# English Error Span Delta Evaluation\n\n",
        "## Scope\n\n",
        "This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.\n\n",
        "## Run Metadata\n\n",
        "| Field | Value |\n|---|---|\n",
    ]
    for key in ("run_id", "started_at", "ended_at", "backend_url", "suite", "dataset", "sample_size", "gold_model"):
        lines.append(f"| {key} | {manifest.get(key, '')} |\n")
    lines.extend(["\n## Metrics\n\n", "| Metric | Value |\n|---|---:|\n"])
    for key, value in summary.items():
        if key == "top_missed_spans":
            continue
        lines.append(f"| {key} | {value} |\n")
    lines.append("\n## Top Missed Spans\n\n")
    if summary.get("top_missed_spans"):
        lines.append("| Span | Count |\n|---|---:|\n")
        for item in summary["top_missed_spans"]:
            lines.append(f"| {item['span']} | {item['count']} |\n")
    else:
        lines.append("No missed spans.\n")
    lines.append("\n## Sample Results\n\n")
    lines.append("| Dataset index | Status | Gold spans | System spans | Recall | Precision |\n|---|---|---|---|---:|---:|\n")
    for row in results[:50]:
        score = row.get("score") or {}
        lines.append(
            "| {idx} | {status} | {gold} | {system} | {recall:.2f} | {precision:.2f} |\n".format(
                idx=row.get("dataset_index"),
                status=row.get("status"),
                gold=json.dumps(row.get("gold_spans") or [], ensure_ascii=False)[:120],
                system=json.dumps(row.get("system_spans") or [], ensure_ascii=False)[:120],
                recall=float(score.get("span_recall") or 0.0),
                precision=float(score.get("span_precision") or 0.0),
            )
        )
    return "".join(lines)


async def run_async(args: argparse.Namespace) -> int:
    dataset = Path(args.dataset).resolve()
    gold_delta_source = Path(args.gold_delta).resolve() if getattr(args, "gold_delta", "") else None
    run_id = args.run_id or f"english_error_span_delta_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    docs_run_dir = Path(args.out).resolve() / run_id
    data_run_dir = Path(args.data_out).resolve() / run_id
    docs_run_dir.mkdir(parents=True, exist_ok=True)
    data_run_dir.mkdir(parents=True, exist_ok=True)
    started_at = now_iso()

    gold_path = data_run_dir / "gold_delta.jsonl"
    results_path = data_run_dir / "results.jsonl"
    if gold_delta_source is not None:
        gold_rows = load_gold_delta_rows(gold_delta_source, args.sample_size)
        if not gold_rows:
            raise RuntimeError(f"No usable gold delta rows found in {gold_delta_source}")
        dataset_text = gold_delta_source.read_text(encoding="utf-8")
        write_gold_dataset_snapshot(gold_rows, data_run_dir / "dataset_snapshot.csv")
        if gold_delta_source.resolve() != gold_path.resolve():
            write_jsonl(gold_path, gold_rows)
    else:
        rows = load_first_rows(dataset, args.sample_size)
        if not rows:
            raise RuntimeError(f"No usable English rows found in {dataset}")
        dataset_text = "\n".join(f"{row.index},{row.text},{row.correction}" for row in rows)
        write_dataset_snapshot(rows, data_run_dir / "dataset_snapshot.csv")
        gold_rows = await build_gold_deltas(
            rows,
            model=args.gold_model,
            output_path=gold_path,
            progress_every=args.progress_every,
            request_timeout=args.gold_timeout,
            retries=args.gold_retries,
            max_tokens=args.gold_max_tokens,
        )

    manifest_base = {
        "run_id": run_id,
        "started_at": started_at,
        "backend_url": args.backend.rstrip("/"),
        "suite": "english_error_span_delta",
        "dataset": str(dataset),
        "gold_delta": str(gold_delta_source) if gold_delta_source is not None else str(gold_path),
        "dataset_sha256": sha256_text(dataset_text),
        "sample_size": len(gold_rows),
        "gold_model": args.gold_model,
        "system_output_format": "json_array_of_incorrect_spans",
        "data_run_dir": str(data_run_dir),
        "docs_run_dir": str(docs_run_dir),
        "requires_live_provider": ["gemini", "groq"],
    }

    try:
        results = run_system_eval(
            gold_rows,
            backend_url=args.backend.rstrip("/"),
            run_id=run_id,
            timeout=args.timeout,
            requests_per_user=args.requests_per_user,
            output_path=results_path,
            progress_every=args.progress_every,
        )
    except EvalBlocked as exc:
        ended_at = now_iso()
        manifest = {**manifest_base, "ended_at": ended_at, "blocked_reason": str(exc)}
        summary = {
            "total_cases": len(gold_rows),
            "ok_cases": 0,
            "failed_requests": 0,
            "gold_failed": sum(1 for row in gold_rows if row["gold_status"] != "ok"),
            "decision": "blocked",
            "blocker": str(exc),
        }
        write_json(data_run_dir / "manifest.json", manifest)
        write_json(data_run_dir / "summary.json", summary)
        write_jsonl(results_path, [])
        (docs_run_dir / "report.md").write_text(render_report(manifest, summary, []), encoding="utf-8")
        print(
            json.dumps(
                {"run_id": run_id, "data_run_dir": str(data_run_dir), "docs_run_dir": str(docs_run_dir), "summary": summary},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 2

    ended_at = now_iso()
    summary = build_summary(results)
    manifest = {
        **manifest_base,
        "ended_at": ended_at,
    }

    write_json(data_run_dir / "manifest.json", manifest)
    write_json(data_run_dir / "summary.json", summary)
    (docs_run_dir / "report.md").write_text(render_report(manifest, summary, results), encoding="utf-8")
    print(
        json.dumps(
            {"run_id": run_id, "data_run_dir": str(data_run_dir), "docs_run_dir": str(docs_run_dir), "summary": summary},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if summary["failed_requests"] == 0 and summary["gold_failed"] == 0 else 1


def run(args: argparse.Namespace) -> int:
    return asyncio.run(run_async(args))
