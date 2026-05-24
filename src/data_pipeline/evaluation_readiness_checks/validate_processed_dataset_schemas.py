"""Validate every processed eval/seed dataset against its Pydantic schema.

Run this in CI before merging to guarantee that no malformed record can
leak into the evaluation, benchmark, or seed corpus.

    python -m data_pipeline validate
"""

from __future__ import annotations

import logging
from typing import Iterable

from pydantic import BaseModel, ValidationError

from ..shared_pipeline_support.json_dataset_file_io import load_json
from ..shared_pipeline_support.data_file_paths import (
    ERROR_BANK,
    INDUSTRY_CANONICAL,
    MEM0,
    IELTS,
    PEDAGOGICAL,
    MOOD,
    JFLEG_AUTO,
    WIKI_AUTO,
    LEARNER_PROFILES,
)
from ..shared_pipeline_support.processed_dataset_schemas import (
    ESLErrorInstance,
    IELTSWritingSample,
    IndustryVocabItem,
    LearnerProfile,
    Mem0Fact,
    MoodPatternSample,
    PedagogicalPrompt,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger("a20.validate")

def _check(items: Iterable[dict], schema: type[BaseModel], label: str) -> tuple[int, int]:
    ok = bad = 0
    for i, item in enumerate(items):
        try:
            schema.model_validate(item)
            ok += 1
        except ValidationError as e:
            bad += 1
            log.error("[%s][%d] invalid: %s", label, i, e.errors()[:1])
    return ok, bad


def _check_dedup(items: Iterable[dict], key: str, label: str) -> int:
    seen, dups = set(), 0
    for it in items:
        k = (it.get(key) or "").strip().lower()
        if not k:
            continue
        if k in seen:
            dups += 1
            log.warning("[%s] duplicate key %r", label, k)
        seen.add(k)
    return dups


def main() -> int:
    failures = 0

    # 1. V-English Error Bank
    bank = load_json(ERROR_BANK)
    ok, bad = _check(bank["errors"], ESLErrorInstance, "errors")
    failures += bad
    failures += _check_dedup(bank["errors"], "error_pattern", "errors")
    log.info("errors: %d valid, %d invalid (total %d)", ok, bad, len(bank["errors"]))

    # 2. Industry Context Library
    lib = load_json(INDUSTRY_CANONICAL)
    for ind, payload in lib["industries"].items():
        ok, bad = _check(payload["vocabulary"], IndustryVocabItem, f"industry/{ind}")
        failures += bad
        failures += _check_dedup(payload["vocabulary"], "term", f"industry/{ind}")
        log.info("industry %s: %d valid, %d invalid", ind, ok, bad)

    # 3. Mem0 Initial Facts
    mem0 = load_json(MEM0)
    for user_key, payload in mem0["users"].items():
        ok, bad = _check(payload["facts"], Mem0Fact, f"mem0/{user_key}")
        failures += bad
        log.info("mem0 %s: %d valid, %d invalid", user_key, ok, bad)

    # 4. IELTS
    if IELTS.exists():
        ielts = load_json(IELTS)
        ok, bad = _check(ielts["samples"], IELTSWritingSample, "ielts")
        failures += bad
        log.info("ielts: %d valid, %d invalid", ok, bad)

    # 5. Pedagogical
    if PEDAGOGICAL.exists():
        ped = load_json(PEDAGOGICAL)
        ok, bad = _check(ped["prompts"], PedagogicalPrompt, "pedagogical")
        failures += bad
        log.info("pedagogical: %d valid, %d invalid", ok, bad)

    # 6. Mood
    if MOOD.exists():
        mood = load_json(MOOD)
        ok, bad = _check(mood["samples"], MoodPatternSample, "mood")
        failures += bad
        log.info("mood: %d valid, %d invalid", ok, bad)

    # 7. Auto-extracted V-English errors (JFLEG rule-based)
    if JFLEG_AUTO.exists():
        data = load_json(JFLEG_AUTO)
        ok, bad = _check(data["errors"], ESLErrorInstance, "errors_auto_jfleg")
        failures += bad
        log.info("errors_auto_jfleg: %d valid, %d invalid (needs_review)", ok, bad)

    # 8. Auto-extracted industry vocab (Wikipedia rule-based)
    if WIKI_AUTO.exists():
        data = load_json(WIKI_AUTO)
        for ind, payload in data.get("industries", {}).items():
            # Drop non-schema _meta before validation
            cleaned = [{k: v for k, v in it.items() if k != "_meta"}
                       for it in payload.get("vocabulary", [])]
            ok, bad = _check(cleaned, IndustryVocabItem, f"industry_auto/{ind}")
            failures += bad
            log.info("industry_auto %s: %d valid, %d invalid", ind, ok, bad)

    # 9. Learner Profiles (synthetic seeds)
    if LEARNER_PROFILES.exists():
        data = load_json(LEARNER_PROFILES)
        ok, bad = _check(data["profiles"], LearnerProfile, "learner_profiles")
        failures += bad
        failures += _check_dedup(data["profiles"], "profile_id", "learner_profiles")
        log.info("learner_profiles: %d valid, %d invalid", ok, bad)

    if failures:
        log.error("validation FAILED with %d issue(s)", failures)
        return 1
    log.info("validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
