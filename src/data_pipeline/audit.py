"""Readiness audit for the A20 data layer.

The audit is intentionally local-only. It inspects ``data/raw`` and
``data/processed`` against the targets stated in ``PRD_v2.md`` and the scraping
planning docs, but it does not scrape, call APIs, or mutate data.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict

from .json_io import load_json
from .paths import (
    RAW,
    CURRICULUM,
    ERROR_BANK,
    IELTS,
    PEDAGOGICAL,
    MOOD,
    MEM0,
    INDUSTRY_CANONICAL,
)

CORE_INDUSTRIES = {"IT", "Marketing", "Sales", "Finance", "Education"}
DOC_TARGETS = {
    "common_errors": 500,
    "ielts_samples": 60,
    "pedagogical_prompts": 80,
    "mood_samples": 60,
    "mem0_facts_per_persona": 100,
}

WIKI_MARKUP_RE = re.compile(r"(<ref\b|\{\{|https?://|\[\[)", re.I)


@dataclass
class Check:
    name: str
    status: str
    detail: str


def ok(name: str, detail: str) -> Check:
    return Check(name, "pass", detail)


def warn(name: str, detail: str) -> Check:
    return Check(name, "warn", detail)


def fail(name: str, detail: str) -> Check:
    return Check(name, "fail", detail)


def audit() -> dict[str, Any]:
    checks: list[Check] = []

    raw_report = RAW / "scrape_report.json"
    extract_report = RAW / "extract_report.json"
    checks.append(ok("raw scrape report", "present") if raw_report.exists() else fail("raw scrape report", "missing"))
    checks.append(ok("raw extract report", "present") if extract_report.exists() else fail("raw extract report", "missing"))

    if raw_report.exists():
        report = load_json(raw_report)
        wiki = report.get("wikipedia", {})
        hf = report.get("huggingface", {}).get("jfleg", {})
        missing = sorted(CORE_INDUSTRIES - set(wiki))
        if missing:
            checks.append(fail("raw core industries", f"missing {missing}"))
        else:
            checks.append(ok("raw core industries", f"{len(CORE_INDUSTRIES)} core industries collected"))
        total_jfleg = sum(int(v.get("count", 0)) for v in hf.values() if isinstance(v, dict))
        checks.append(ok("raw JFLEG", f"{total_jfleg} records") if total_jfleg else fail("raw JFLEG", "no records"))

    error_bank = load_json(ERROR_BANK)
    n_errors = len(error_bank.get("errors", []))
    if n_errors >= DOC_TARGETS["common_errors"]:
        checks.append(ok("V-English Error Bank", f"{n_errors}/{DOC_TARGETS['common_errors']} errors"))
    else:
        checks.append(fail("V-English Error Bank", f"{n_errors}/{DOC_TARGETS['common_errors']} errors"))
    promoted = error_bank.get("metadata", {}).get("offline_promoted_from_jfleg", {})
    remaining_review = sum(
        1 for e in error_bank.get("errors", [])
        if "needs_teacher_review" in set(e.get("tags", []))
    )
    quality_meta = error_bank.get("metadata", {}).get("alpha_quality_review", {})
    if remaining_review:
        checks.append(warn(
            "teacher review",
            f"{remaining_review} promoted JFLEG items still carry needs_teacher_review",
        ))
    elif promoted.get("cumulative_count") and quality_meta.get("reviewed_count"):
        checks.append(ok(
            "teacher review",
            f"{quality_meta['reviewed_count']} promoted JFLEG items passed alpha quality gate",
        ))

    ielts = load_json(IELTS)
    n_ielts = len(ielts.get("samples", []))
    checks.append(ok("IELTS samples", f"{n_ielts}/60") if n_ielts >= 60 else fail("IELTS samples", f"{n_ielts}/60"))
    short_essays = [
        s.get("id", "<unknown>") for s in ielts.get("samples", [])
        if len(str(s.get("essay", "")).split()) < 250
    ]
    checks.append(
        ok("IELTS essay length", "all samples >=250 words")
        if not short_essays
        else fail("IELTS essay length", f"{len(short_essays)} samples below 250 words")
    )

    ped = load_json(PEDAGOGICAL)
    n_ped = len(ped.get("prompts", []))
    checks.append(ok("pedagogical prompts", f"{n_ped}/80") if n_ped >= 80 else fail("pedagogical prompts", f"{n_ped}/80"))

    mood = load_json(MOOD)
    n_mood = len(mood.get("samples", []))
    checks.append(ok("mood samples", f"{n_mood}/60") if n_mood >= 60 else fail("mood samples", f"{n_mood}/60"))

    mem0 = load_json(MEM0)
    fact_counts = {k: len(v.get("facts", [])) for k, v in mem0.get("users", {}).items()}
    low = {k: v for k, v in fact_counts.items() if v < DOC_TARGETS["mem0_facts_per_persona"]}
    checks.append(ok("Mem0 seed facts", str(fact_counts)) if not low else fail("Mem0 seed facts", f"below target: {low}"))
    checks.append(warn(
        "Mem0 stress scale",
        "PRD requires runtime benchmark at 1,000-2,000 facts/user; seed data is 100 facts/persona.",
    ))

    industry = load_json(INDUSTRY_CANONICAL)
    industries = industry.get("industries", {})
    missing_core = sorted(CORE_INDUSTRIES - set(industries))
    if missing_core:
        checks.append(fail("industry library", f"missing core industries {missing_core}"))
    else:
        counts = {k: len(v.get("vocabulary", [])) for k, v in industries.items()}
        checks.append(ok("industry library", str(counts)))
    missing_industry_fields = 0
    for payload in industries.values():
        for item in payload.get("vocabulary", []):
            if not item.get("definition_vi") or not item.get("example_sentence") or not item.get("usage_note"):
                missing_industry_fields += 1
    checks.append(
        ok("industry required fields", "definition_vi/example_sentence/usage_note present")
        if missing_industry_fields == 0
        else fail("industry required fields", f"{missing_industry_fields} items still incomplete")
    )
    remaining_markup = 0
    for payload in industries.values():
        for item in payload.get("vocabulary", []):
            if WIKI_MARKUP_RE.search(str(item.get("definition_en", ""))):
                remaining_markup += 1
    checks.append(ok("wiki markup cleanup", "no raw wiki markup detected") if remaining_markup == 0 else fail("wiki markup cleanup", f"{remaining_markup} items still noisy"))

    curriculum_levels = {p.parent.name for p in CURRICULUM.rglob("*.yaml")}
    if "A1" in curriculum_levels:
        checks.append(ok("A1 curriculum", "present"))
    else:
        checks.append(warn("A1 curriculum", "missing; PRD onboarding lists A1-C1 while skeleton starts at A2"))

    status = "pass"
    if any(c.status == "fail" for c in checks):
        status = "fail"
    elif any(c.status == "warn" for c in checks):
        status = "pass_with_warnings"

    return {
        "status": status,
        "checks": [asdict(c) for c in checks],
    }


def main(_args: argparse.Namespace | None = None) -> int:
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result["status"] == "fail" else 0


def add_arguments(_parser: argparse.ArgumentParser) -> None:
    return None
