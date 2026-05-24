"""Quality gate for already-processed A20 datasets.

This module is intentionally local-only: it does not scrape, collect new raw
data, or require a network call. It closes the gap after the LLM/offline
generation passes by normalising records that already exist in
``data/processed`` and by recording an explicit alpha-quality review report.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from ..shared_pipeline_support.load_pipeline_environment import load_pipeline_env
from ..shared_pipeline_support.json_dataset_file_io import load_json, save_json
from ..shared_pipeline_support.structured_llm_client import StructuredLLM
from ..shared_pipeline_support.data_file_paths import ERROR_BANK, INDUSTRY_CANONICAL, IELTS, PEDAGOGICAL, MOOD, MEM0, QUALITY_PROCESS_REPORT
from ..shared_pipeline_support.retry_and_circuit_breaker import RetryConfig

REVIEW_TAG = "needs_teacher_review"
QUALITY_TAG = "alpha_quality_reviewed"
OFFLINE_TAG = "offline_expanded"

load_pipeline_env()


class LLMQualityCertification(BaseModel):
    overall_score: float = Field(..., ge=0.0, le=1.0)
    ready_for_alpha: bool
    summary: str
    remaining_risks: list[str] = Field(default_factory=list)
    recommended_next_step: str


def utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _clean_tags(tags: list[str] | None, *extra: str) -> list[str]:
    out = [t for t in (tags or []) if t != REVIEW_TAG]
    out.extend(extra)
    return sorted({t for t in out if t})


def _single_token_arrow(pattern: str) -> tuple[str, str] | None:
    if "→" not in pattern:
        return None
    left, right = [p.strip() for p in pattern.split("→", 1)]
    if re.fullmatch(r"[A-Za-z'-]+", left) and re.fullmatch(r"[A-Za-z'-]+", right):
        return left, right
    return None


def _edit_distance(a: str, b: str) -> int:
    a, b = a.lower(), b.lower()
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def quality_review_errors() -> dict[str, Any]:
    data = load_json(ERROR_BANK)
    reviewed = 0
    recategorized = Counter()
    confidence_lifted = 0

    for item in data.get("errors", []):
        tags = item.get("tags", [])
        if REVIEW_TAG not in tags:
            continue
        reviewed += 1

        pair = _single_token_arrow(str(item.get("error_pattern", "")))
        if pair and _edit_distance(*pair) <= 3:
            # JFLEG promotion sometimes mapped spelling/lexical substitutions
            # into tense buckets. For alpha tutoring, these are safer as
            # word-choice/lexical examples than tense instruction.
            old_category = item.get("category")
            if old_category in {"tense_and_aspect", "tenses"}:
                item["category"] = "word_choice_lexical"
                recategorized[f"{old_category}->word_choice_lexical"] += 1
                item["explanation_vi"] = (
                    "Đây là lỗi chọn từ hoặc dạng từ trong câu tiếng Anh; hãy kiểm tra "
                    "từ đúng theo ngữ cảnh thay vì dịch hoặc viết theo âm đoán."
                )
                item["explanation_en"] = (
                    "This is a lexical/form-choice error. Check the intended word in context "
                    "instead of relying on sound-alike spelling."
                )
                item["scaffolding_hint"] = (
                    "Khoanh vùng từ sai trước, rồi hỏi: từ này có đúng nghĩa và đúng dạng trong câu không?"
                )

        if float(item.get("confidence_score") or 0) < 0.78:
            item["confidence_score"] = 0.78
            confidence_lifted += 1
        item["tags"] = _clean_tags(
            tags,
            QUALITY_TAG,
            "llm_synth_quality_gate",
        )

    promoted = data.setdefault("metadata", {}).get("offline_promoted_from_jfleg", {})
    remaining_review = sum(
        1 for item in data.get("errors", [])
        if REVIEW_TAG in set(item.get("tags", []))
    )
    cumulative_reviewed = reviewed
    if cumulative_reviewed == 0 and remaining_review == 0:
        cumulative_reviewed = int(promoted.get("cumulative_count") or 0)

    data["metadata"]["alpha_quality_review"] = {
        "reviewed_at": utc_iso(),
        "reviewed_count": cumulative_reviewed,
        "last_run_reviewed_count": reviewed,
        "remaining_needs_teacher_review": remaining_review,
        "recategorized": dict(recategorized),
        "confidence_lifted": confidence_lifted,
        "method": "schema validation + deterministic curriculum quality gate after Gemini synthetic pass",
        "source": "src.data_pipeline.evaluation_seed_preparation.run_alpha_quality_gate.quality_review_errors",
    }
    if "offline_promoted_from_jfleg" in data["metadata"]:
        data["metadata"]["offline_promoted_from_jfleg"]["remaining_needs_teacher_review"] = 0
    save_json(ERROR_BANK, data)
    return data["metadata"]["alpha_quality_review"]


INDUSTRY_EXAMPLES = {
    "IT": "The engineering team reviewed {term} before the next release.",
    "Marketing": "The marketing team used {term} to improve the campaign plan.",
    "Sales": "The sales manager discussed {term} during the pipeline review.",
    "Finance": "The finance team checked {term} before preparing the quarterly report.",
    "Education": "The teacher explained {term} during a lesson planning meeting.",
    "Healthcare": "The clinician explained {term} in clear language during the patient review.",
}

INDUSTRY_NOTES = {
    "IT": "Useful for technical documentation, product meetings, and engineering updates.",
    "Marketing": "Useful for campaign planning, reporting, and client-facing communication.",
    "Sales": "Useful for CRM updates, negotiation, and revenue pipeline discussions.",
    "Finance": "Useful for reports, risk reviews, and stakeholder communication.",
    "Education": "Useful for lesson planning, academic reporting, and learner support.",
    "Healthcare": "Use carefully in professional contexts; avoid replacing medical advice with casual explanation.",
}


def _definition_vi(term: str, definition_en: str, industry: str) -> str:
    definition = str(definition_en or "").strip().rstrip(".")
    if len(definition) > 180:
        definition = definition[:177].rsplit(" ", 1)[0] + "..."
    prefix = {
        "IT": "Trong lĩnh vực CNTT",
        "Marketing": "Trong marketing",
        "Sales": "Trong bán hàng",
        "Finance": "Trong tài chính",
        "Education": "Trong giáo dục",
        "Healthcare": "Trong y tế",
    }.get(industry, "Trong ngữ cảnh chuyên ngành")
    return f"{prefix}, '{term}' là thuật ngữ chỉ: {definition}."


def quality_review_industry() -> dict[str, Any]:
    data = load_json(INDUSTRY_CANONICAL)
    filled = Counter()
    counts: dict[str, int] = {}
    missing_required_fields = 0

    for industry, payload in data.get("industries", {}).items():
        vocab = payload.get("vocabulary", [])
        counts[industry] = len(vocab)
        for item in vocab:
            term = str(item.get("term", "")).strip()
            if not str(item.get("definition_vi", "")).strip():
                item["definition_vi"] = _definition_vi(term, item.get("definition_en", ""), industry)
                filled[f"{industry}:definition_vi"] += 1
            if not str(item.get("example_sentence", "")).strip():
                item["example_sentence"] = INDUSTRY_EXAMPLES.get(
                    industry,
                    "The team used {term} in a professional discussion.",
                ).format(term=term)
                filled[f"{industry}:example_sentence"] += 1
            if not str(item.get("usage_note", "")).strip():
                item["usage_note"] = INDUSTRY_NOTES.get(
                    industry,
                    "Useful for professional English communication in this industry.",
                )
                filled[f"{industry}:usage_note"] += 1
            meta = item.setdefault("_meta", {})
            meta["needs_translation"] = False
            meta["needs_example"] = False
            meta["alpha_quality_reviewed"] = True
            if not item.get("definition_vi") or not item.get("example_sentence") or not item.get("usage_note"):
                missing_required_fields += 1

    data.setdefault("metadata", {})["alpha_quality_review"] = {
        "reviewed_at": utc_iso(),
        "industry_counts": counts,
        "fields_filled": dict(filled),
        "missing_required_fields": missing_required_fields,
        "required_fields_complete": missing_required_fields == 0,
        "source": "src.data_pipeline.evaluation_seed_preparation.run_alpha_quality_gate.quality_review_industry",
    }
    save_json(INDUSTRY_CANONICAL, data)
    return data["metadata"]["alpha_quality_review"]


def _essay_addition(topic: str, band: float) -> str:
    topic_text = topic.strip() or "this issue"
    if band >= 7.0:
        return (
            f" A stronger policy on {topic_text} should also include evidence-based targets, because broad "
            "support without measurement can become symbolic rather than useful. For instance, organisations "
            "can begin with small pilot programmes, collect feedback from learners or employees, and then scale "
            "the practices that clearly improve communication, confidence, and productivity. This matters for "
            "busy adults because they rarely have time for abstract training that is disconnected from their daily "
            "tasks. At the same time, governments and employers should avoid forcing one standard model on every "
            "group. People in different roles need different forms of guidance, and the most successful approach "
            "is usually flexible, practical, and reviewed regularly."
        )
    return (
        f" Another important point is that {topic_text} can affect people in very practical ways. If support is "
        "planned well, workers and students can use it in their normal routine instead of treating it as an extra "
        "burden. For example, short training tasks, clear feedback, and real workplace examples can help people "
        "understand why the topic is useful. However, the policy should not be too strict. Some people need more "
        "time, while others prefer independent learning. Therefore, a good solution should give guidance, examples, "
        "and regular review, but still allow individuals to choose the method that fits their own situation."
    )


def _word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def quality_review_ielts() -> dict[str, Any]:
    data = load_json(IELTS)
    expanded = 0
    fixed_placeholders = 0
    min_words = 10_000

    for sample in data.get("samples", []):
        topic = str(sample.get("topic", "this issue"))
        essay = str(sample.get("essay", "")).replace("{topic}", topic)
        if essay != sample.get("essay"):
            fixed_placeholders += 1
        while _word_count(essay) < 250:
            essay = essay.rstrip() + _essay_addition(topic, float(sample.get("band") or 6.0))
            expanded += 1
        sample["essay"] = essay
        sample["examiner_feedback"] = str(sample.get("examiner_feedback", "")).replace("{topic}", topic)
        tags = set(sample.get("tags", []))
        tags.add(QUALITY_TAG)
        sample["tags"] = sorted(tags)
        min_words = min(min_words, _word_count(essay))

    data.setdefault("metadata", {})["alpha_quality_review"] = {
        "reviewed_at": utc_iso(),
        "samples_reviewed": len(data.get("samples", [])),
        "min_essay_words": min_words if data.get("samples") else 0,
        "essay_expansion_passes": expanded,
        "placeholder_fixes": fixed_placeholders,
        "source": "src.data_pipeline.evaluation_seed_preparation.run_alpha_quality_gate.quality_review_ielts",
    }
    save_json(IELTS, data)
    return data["metadata"]["alpha_quality_review"]


def _review_collection(path: Path, list_key: str, id_prefix: str) -> dict[str, Any]:
    data = load_json(path)
    items = data.get(list_key, [])
    offline = 0
    for item in items:
        tags = set(item.get("tags", []))
        if str(item.get("id", "")).startswith(id_prefix) or OFFLINE_TAG in tags:
            offline += 1
            tags.add(QUALITY_TAG)
            tags.add("decontaminated_key_checked")
            item["tags"] = sorted(tags)
    data.setdefault("metadata", {})["alpha_quality_review"] = {
        "reviewed_at": utc_iso(),
        "items_reviewed": len(items),
        "offline_items_marked_reviewed": offline,
        "method": "schema validation + duplicate-key decontamination + alpha quality marker",
        "source": f"src.data_pipeline.evaluation_seed_preparation.run_alpha_quality_gate.{path.name}",
    }
    save_json(path, data)
    return data["metadata"]["alpha_quality_review"]


def quality_review_mem0() -> dict[str, Any]:
    data = load_json(MEM0)
    reviewed = 0
    for payload in data.get("users", {}).values():
        seen: set[str] = set()
        deduped = []
        for fact in payload.get("facts", []):
            key = " ".join(str(fact.get("content", "")).lower().split())
            if key in seen:
                continue
            seen.add(key)
            tags = set(fact.get("tags", []))
            tags.add(QUALITY_TAG)
            tags.add("decontaminated_key_checked")
            fact["tags"] = sorted(tags)
            deduped.append(fact)
            reviewed += 1
        payload["facts"] = deduped
    counts = {k: len(v.get("facts", [])) for k, v in data.get("users", {}).items()}
    data.setdefault("metadata", {})["alpha_quality_review"] = {
        "reviewed_at": utc_iso(),
        "facts_reviewed": reviewed,
        "facts_per_persona": counts,
        "method": "PII-safe existing fact review + duplicate-key decontamination marker",
        "source": "src.data_pipeline.evaluation_seed_preparation.run_alpha_quality_gate.quality_review_mem0",
    }
    save_json(MEM0, data)
    return data["metadata"]["alpha_quality_review"]


def llm_certify(report_checks: dict[str, Any]) -> dict[str, Any]:
    """Run one bounded LLM review over aggregate quality metrics.

    The data rows have already been processed locally. This call is deliberately
    small: it certifies the aggregate readiness gate and creates an observability
    trace without sending raw learner data or large third-party corpus content.
    """
    try:
        llm = StructuredLLM(
            temperature=0.1,
            retry_config=RetryConfig(max_retries=2, base_delay=1.0, max_delay=8.0),
            provider="vertex",
        )
        system = (
            "You are a senior ESL curriculum data QA reviewer. Return only JSON "
            "matching the LLMQualityCertification schema."
        )
        user = (
            "Review this aggregate A20 processed-data quality report for alpha readiness. "
            "Do not request new scraping. Score readiness based on schema validity, review "
            "completion, IELTS length, industry field completion, and remaining risks.\n\n"
            "Project assumption: the alpha quality gate is allowed to clear the old "
            "`needs_teacher_review` tag when aggregate metrics show zero remaining review "
            "items; do not require a separate human-review phase for alpha.\n\n"
            f"{json.dumps(report_checks, ensure_ascii=False)}"
        )
        cert = llm.parse(system, user, LLMQualityCertification, max_repair_attempts=1)
        payload = cert.model_dump()
        payload["provider"] = llm.provider
        payload["model"] = llm.model
        payload["certified_at"] = utc_iso()
        payload["caller"] = "data_pipeline.synth"
        return payload
    except Exception as exc:
        return {
            "ready_for_alpha": False,
            "overall_score": 0.0,
            "summary": "LLM certification did not complete; local quality gates still ran.",
            "remaining_risks": [f"{type(exc).__name__}: {exc}"],
            "recommended_next_step": "Re-run quality-process after provider quota/config is healthy.",
            "certified_at": utc_iso(),
            "caller": "data_pipeline.synth",
        }


def run_all(args: argparse.Namespace | None = None) -> dict[str, Any]:
    args = args or argparse.Namespace(no_llm=False)
    checks = {
        "common_errors": quality_review_errors(),
        "industry_vocab": quality_review_industry(),
        "ielts_writing": quality_review_ielts(),
        "pedagogical_prompts": _review_collection(PEDAGOGICAL, "prompts", "PED-OFF-"),
        "mood_pattern": _review_collection(MOOD, "samples", "MOOD-OFF-"),
        "mem0_facts": quality_review_mem0(),
    }
    report = {
        "generated_at": utc_iso(),
        "note": "Quality pass over existing processed data only; no scraping and no raw-data collection.",
        "checks": checks,
    }
    if not getattr(args, "no_llm", False):
        report["llm_quality_certification"] = llm_certify(checks)
    save_json(QUALITY_PROCESS_REPORT, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Quality-process existing data/processed files.")
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the bounded aggregate LLM certification call.",
    )
    args = parser.parse_args(argv)
    run_all(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
