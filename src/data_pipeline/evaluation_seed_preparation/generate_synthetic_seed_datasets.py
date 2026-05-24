"""Generate synthetic static evaluation/seed datasets.

Use this only for the static datasets listed in ``data_planning.md``. Runtime
learner memory still comes from production user events, not from this module.

The generation flow is seed -> expand -> judge -> decontaminate, with Pydantic
schemas and PII scrubbing before persistence.

Datasets produced
-----------------
1. V-English Error Bank  (data/processed/common_errors/v_english_error_bank.json)
2. Industry Context Library (data/processed/industry_vocab/industry_context_library.json)
3. Mem0 Initial Facts (data/processed/mem0_facts/mem0_initial_facts.json)
4. IELTS Writing Task 2 samples (data/processed/ielts_writing/ielts_writing_task2.json)
5. Pedagogical Prompts (data/processed/pedagogical_prompts/pedagogical_prompts.json)
6. Mood & Pattern samples (data/processed/mood_pattern/mood_pattern_samples.json)

Usage
-----
    python -m data_pipeline generate --task all
    python -m data_pipeline generate --task errors --count 500
    python -m data_pipeline generate --task ielts --count 60
    python -m data_pipeline generate --task pedagogical --count 80
    python -m data_pipeline generate --task mood --count 60

Dependencies: pydantic>=2, python-dotenv, tqdm, and a configured Gemini/Groq
provider for LLM-backed generation.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from typing import Callable, Sequence

from tqdm import tqdm

from ..shared_pipeline_support.load_pipeline_environment import load_pipeline_env  # noqa: E402
from ..shared_pipeline_support.json_dataset_file_io import load_json, save_json  # noqa: E402
from ..shared_pipeline_support.structured_llm_client import StructuredLLM  # noqa: E402
from ..shared_pipeline_support.data_file_paths import GENERATED_DATASETS as PATHS  # noqa: E402
from .scrub_pii import PIISentinel  # noqa: E402
from ..shared_pipeline_support.retry_and_circuit_breaker import RetryConfig  # noqa: E402
from ..shared_pipeline_support.processed_dataset_schemas import (  # noqa: E402
    IELTSDatasetBatch,
    IndustryVocabBatch,
    Mem0FactsBatch,
    MoodPatternBatch,
    PedagogicalPromptBatch,
    SyntheticErrorBatch,
    utcnow_iso,
)
from .synthetic_generation_workflow import SyntheticPipeline  # noqa: E402

load_pipeline_env()
logging.basicConfig(
    level=os.getenv("A20_LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("a20.generate_data")


def short_id() -> str:
    return uuid.uuid4().hex[:6].upper()


# ---------------------------------------------------------------------------
# Shared LLM + sentinel
# ---------------------------------------------------------------------------

def make_llm() -> StructuredLLM:
    """Build the structured LLM client for synthetic data preparation."""
    os.environ["A20_LLM_PROVIDER"] = "vertex"
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
    if not os.getenv("GOOGLE_API_KEY"):
        log.error("GOOGLE_API_KEY is required for Vertex AI synthetic data preparation.")
        sys.exit(1)
    try:
        return StructuredLLM(
            model=os.getenv("A20_GEN_MODEL"),
            temperature=float(os.getenv("A20_GEN_TEMPERATURE", "0.4")),
            retry_config=RetryConfig(max_retries=5, base_delay=1.0, max_delay=60.0),
            provider="vertex",
        )
    except RuntimeError as exc:
        log.error("%s", exc)
        sys.exit(1)


SENTINEL = PIISentinel()


# ---------------------------------------------------------------------------
# Task 1: V-English Error Bank
# ---------------------------------------------------------------------------

ERROR_CATEGORIES = [
    "prepositions", "articles", "tense_and_aspect", "subject_verb_agreement",
    "copula_be_omission", "copula_be_redundancy", "adverb_misplacement",
    "word_order", "collocations", "countable_uncountable", "conditionals",
    "reported_speech", "passive_voice", "modal_verbs", "phrasal_verbs",
    "false_friends", "sentence_structure", "l1_interference_structure",
]

ERROR_RUBRIC = (
    "1) Linguistic accuracy: incorrect/correct examples are minimally different "
    "and the correction is unambiguous. 2) Pedagogical value: the explanation "
    "exposes the L1 transfer or rule misapplication. 3) Diversity: the "
    "error_pattern is novel relative to seeds. Reject toxic, biased, or "
    "irrelevant content."
)

ERROR_SYSTEM = (
    "You are an expert computational linguist for Vietnamese-English ESL. "
    "Generate JSON conforming exactly to the SyntheticErrorBatch schema. "
    "Each error must reflect realistic L1 Vietnamese transfer phenomena."
)


def run_errors(count: int) -> None:
    bank = load_json(PATHS["errors"])
    existing: list[dict] = bank["errors"]
    seen = {(e.get("error_pattern") or "").strip().lower() for e in existing}
    needed = max(0, count - len(existing))
    if needed == 0:
        log.info("errors: already at target (%d)", len(existing))
        return

    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=SyntheticErrorBatch,
        extract_items=lambda batch: batch.errors,
    )

    seeds: list[dict] = [
        {"error_pattern": e["error_pattern"], "category": e.get("category")}
        for e in existing[:50]
    ]

    def builder(sampled: list[dict]) -> str:
        seed_lines = "\n".join(f"- {s['error_pattern']} ({s.get('category')})" for s in sampled)
        category = sampled[0]["category"] if sampled else "tense_and_aspect"
        return (
            f"Generate 5 NEW Vietnamese-learner ESL error instances. Mix categories but "
            f"include at least 2 in '{category}'. Avoid repeating these seeds:\n{seed_lines}\n"
            "Set realistic CEFR (A1–C2), confidence_score (0.0–1.0), importance_score, "
            "frequency, and id of the form ERR-<CAT4>-<HEX6>."
        )

    pbar = tqdm(total=needed, desc="errors")
    accepted = pipeline.run(
        system_prompt=ERROR_SYSTEM,
        user_prompt_builder=builder,
        seeds=seeds,
        rubric=ERROR_RUBRIC,
        target_count=needed,
        seen_keys=seen,
        key_fn=lambda e: e.error_pattern,
        seeds_per_call=5,
    )
    for item in accepted:
        d = item.model_dump()
        d["id"] = f"ERR-{d['category'][:4].upper()}-{short_id()}"
        existing.append(d)
        pbar.update(1)
    pbar.close()

    bank["errors"] = existing
    bank["metadata"]["total_errors"] = len(existing)
    save_json(PATHS["errors"], bank)


# ---------------------------------------------------------------------------
# Task 2: Industry Vocabulary
# ---------------------------------------------------------------------------

INDUSTRY_RUBRIC = (
    "1) Term is genuinely industry-specific (not generic English). "
    "2) Definitions in EN and VI agree. 3) Example sentence is natural and "
    "professional. 4) Register and CEFR level fit. Reject filler/marketing fluff."
)

INDUSTRY_SYSTEM = (
    "You are a business-English curriculum designer creating vocabulary "
    "entries for Vietnamese professionals. Output strictly conforms to "
    "IndustryVocabBatch."
)


def run_industry(count_per_industry: int, only_industry: str | None) -> None:
    library = load_json(PATHS["industry_vocab"])
    industries = [only_industry] if only_industry else list(library["industries"].keys())
    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=IndustryVocabBatch,
        extract_items=lambda b: b.vocabulary,
    )

    for ind in industries:
        if ind not in library["industries"]:
            log.warning("unknown industry %s", ind)
            continue
        existing = library["industries"][ind]["vocabulary"]
        seen = {v["term"].strip().lower() for v in existing}
        needed = max(0, count_per_industry - len(existing))
        if needed == 0:
            log.info("industry %s already at target (%d)", ind, len(existing))
            continue

        seeds = [{"term": v["term"]} for v in existing[:30]]

        def builder(sampled: list[dict], ind=ind) -> str:
            seed_str = ", ".join(s["term"] for s in sampled) or "(no seeds yet)"
            return (
                f"Generate 5 NEW vocabulary entries for the '{ind}' industry "
                "for Vietnamese professionals. Avoid repeating: " + seed_str
            )

        accepted = pipeline.run(
            system_prompt=INDUSTRY_SYSTEM,
            user_prompt_builder=builder,
            seeds=seeds,
            rubric=INDUSTRY_RUBRIC,
            target_count=needed,
            seen_keys=seen,
            key_fn=lambda v: v.term,
            seeds_per_call=5,
        )
        existing.extend(item.model_dump() for item in accepted)
        log.info("industry %s now %d entries", ind, len(existing))

    save_json(PATHS["industry_vocab"], library)


# ---------------------------------------------------------------------------
# Task 3: Mem0 Initial Facts
# ---------------------------------------------------------------------------

PERSONA_PROFILES = {
    "first_timer": ("user_001", "Marketing Executive", "B1",
                    "Professional email writing and presentations"),
    "speed_runner": ("user_002", "Software Engineer", "B2",
                     "IELTS 7.0 in 3 months"),
    "qa_destroyer": ("user_003", "Senior Finance Analyst", "C1",
                     "Executive C-suite presentation English"),
}

MEM0_RUBRIC = (
    "Each fact is a long-term, action-oriented memory string with no PII. "
    "Tie at least one fact_type to L1 transfer evidence. Reject vague or "
    "session-scoped chatter."
)

MEM0_SYSTEM = (
    "You produce Mem0-compatible long-term memory facts for an ESL tutor. "
    "Strictly output JSON for Mem0FactsBatch. PII (names, emails, phone) MUST "
    "be omitted; refer to the learner generically."
)


def run_mem0(count_per_persona: int, only_persona: str | None) -> None:
    mem0 = load_json(PATHS["mem0"])
    personas = [only_persona] if only_persona else list(PERSONA_PROFILES.keys())
    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=Mem0FactsBatch,
        extract_items=lambda b: b.facts,
    )

    for persona in personas:
        if persona not in PERSONA_PROFILES:
            continue
        user_id, occupation, level, goal = PERSONA_PROFILES[persona]
        user_key = f"{user_id}_{persona}"
        if user_key not in mem0["users"]:
            log.warning("persona key %s missing in seed file", user_key)
            continue
        existing = mem0["users"][user_key]["facts"]
        seen = {f["content"].strip().lower()[:80] for f in existing}
        needed = max(0, count_per_persona - len(existing))
        if needed == 0:
            log.info("mem0 %s already at target (%d)", persona, len(existing))
            continue

        seeds = [{"content": f["content"][:120]} for f in existing[:10]]

        def builder(sampled: list[dict], persona=persona, user_id=user_id,
                    occupation=occupation, level=level, goal=goal) -> str:
            seed_str = "\n".join(f"- {s['content']}" for s in sampled) or "(none)"
            return (
                f"Persona={persona}, occupation={occupation}, level={level}, goal='{goal}'. "
                f"Generate 5 NEW Mem0 facts for user_id='{user_id}'. "
                f"Vary fact_type across error_pattern/preference/progress/context/goal/mood_pattern. "
                f"Existing facts (avoid duplicates):\n{seed_str}\n"
                "Use ISO-8601 created_at timestamps in 2025."
            )

        accepted = pipeline.run(
            system_prompt=MEM0_SYSTEM,
            user_prompt_builder=builder,
            seeds=seeds,
            rubric=MEM0_RUBRIC,
            target_count=needed,
            seen_keys=seen,
            key_fn=lambda f: f.content,
            seeds_per_call=5,
        )
        for item in accepted:
            d = item.model_dump()
            d["content"] = SENTINEL.scrub(d["content"])
            d["evidence"] = SENTINEL.scrub(d.get("evidence", ""))
            d["fact_id"] = f"F-{user_id[-3:]}-{short_id()}"
            existing.append(d)
        log.info("mem0 %s now %d facts", persona, len(existing))

    save_json(PATHS["mem0"], mem0)


# ---------------------------------------------------------------------------
# Task 4: IELTS Writing Task 2
# ---------------------------------------------------------------------------

IELTS_RUBRIC = (
    "1) Prompt is a realistic IELTS Task 2 question (opinion / discussion / "
    "two-part). 2) Essay length is band-appropriate (≥250 words for ≥6.0). "
    "3) Examiner feedback explicitly references all four criteria (TR, CC, LR, "
    "GRA). 4) common_errors map to error_pattern keys in the V-English Error "
    "Bank. Reject AI-tell phrases ('As an AI…') and generic platitudes."
)

IELTS_SYSTEM = (
    "You are an experienced IELTS examiner. Produce JSON conforming to "
    "IELTSDatasetBatch with realistic essays at varying band scores."
)

IELTS_TOPICS = [
    "education and technology", "environment and sustainability",
    "globalisation and culture", "work-life balance",
    "urbanisation", "media and society", "health and lifestyle",
    "government policy and economy",
]


def run_ielts(count: int) -> None:
    data = load_json(PATHS["ielts"])
    samples = data["samples"]
    seen = {s["prompt"].strip().lower() for s in samples}
    needed = max(0, count - len(samples))
    if needed == 0:
        log.info("ielts already at target (%d)", len(samples))
        return

    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=IELTSDatasetBatch,
        extract_items=lambda b: b.samples,
    )

    seeds = [{"topic": t} for t in IELTS_TOPICS]

    def builder(sampled: list[dict]) -> str:
        topic = sampled[0]["topic"] if sampled else "education"
        return (
            f"Generate 2 IELTS Writing Task 2 samples on the topic '{topic}'. "
            "Vary band scores between 5.5 and 8.5. Each sample includes: prompt, "
            "essay (≥250 words), examiner_feedback that names TR/CC/LR/GRA, and "
            "a list of common_errors (Vietnamese-learner patterns)."
        )

    accepted = pipeline.run(
        system_prompt=IELTS_SYSTEM,
        user_prompt_builder=builder,
        seeds=seeds,
        rubric=IELTS_RUBRIC,
        target_count=needed,
        seen_keys=seen,
        key_fn=lambda s: s.prompt,
        seeds_per_call=1,
    )
    for item in accepted:
        d = item.model_dump()
        d["essay"] = SENTINEL.scrub(d["essay"])
        d["examiner_feedback"] = SENTINEL.scrub(d["examiner_feedback"])
        if not d.get("id"):
            d["id"] = f"IELTS-{short_id()}"
        samples.append(d)

    data["samples"] = samples
    data["metadata"]["total_samples"] = len(samples)
    save_json(PATHS["ielts"], data)


# ---------------------------------------------------------------------------
# Task 5: Pedagogical Prompts (Scaffolding)
# ---------------------------------------------------------------------------

PED_RUBRIC = (
    "1) scaffolding_steps follow Krashen's i+1 (each step adds exactly one "
    "challenge). 2) socratic_questions provoke retrieval, not recall. "
    "3) affective_filter_strategy explicitly addresses anxiety. "
    "4) target_skill matches the situation. Reject prescriptive 'tell-don't-show' "
    "prompts."
)

PED_SYSTEM = (
    "You are a CELTA-certified ESL pedagogue specialised in scaffolding. "
    "Output JSON for PedagogicalPromptBatch only."
)


def run_pedagogical(count: int) -> None:
    data = load_json(PATHS["pedagogical"])
    prompts = data["prompts"]
    seen = {p["learner_situation"].strip().lower()[:120] for p in prompts}
    needed = max(0, count - len(prompts))
    if needed == 0:
        log.info("pedagogical already at target (%d)", len(prompts))
        return

    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=PedagogicalPromptBatch,
        extract_items=lambda b: b.prompts,
    )

    seed_situations = [
        {"learner_situation": "Learner freezes when asked to speak about work in English (Bệnh Nghẽn 🔴)."},
        {"learner_situation": "Learner forgets the past simple form of irregular verbs (Bệnh Quên 🟡)."},
        {"learner_situation": "Learner overuses 'although... but...' double conjunctions."},
        {"learner_situation": "Learner cannot select between 'a/an/the' under time pressure."},
        {"learner_situation": "Learner mixes simple past and present perfect when narrating."},
    ]

    def builder(sampled: list[dict]) -> str:
        seed_str = "\n".join(f"- {s['learner_situation']}" for s in sampled)
        return (
            "Generate 5 NEW scaffolding prompt entries for these situations:\n"
            f"{seed_str}\n"
            "Each entry must include ≥3 scaffolding_steps (i+1) and ≥2 socratic_questions."
        )

    accepted = pipeline.run(
        system_prompt=PED_SYSTEM,
        user_prompt_builder=builder,
        seeds=seed_situations,
        rubric=PED_RUBRIC,
        target_count=needed,
        seen_keys=seen,
        key_fn=lambda p: p.learner_situation,
        seeds_per_call=3,
    )
    for item in accepted:
        d = item.model_dump()
        if not d.get("id"):
            d["id"] = f"PED-{short_id()}"
        prompts.append(d)

    data["prompts"] = prompts
    data["metadata"]["total_prompts"] = len(prompts)
    save_json(PATHS["pedagogical"], data)


# ---------------------------------------------------------------------------
# Task 6: Mood & Pattern
# ---------------------------------------------------------------------------

MOOD_RUBRIC = (
    "1) energy_level matches contextual_signals. 2) recommended_pace and "
    "recommended_modality follow A20's pacing rules: exhausted→slow/review, "
    "low→slow/drill, neutral→moderate/new_material, energized→fast/free_practice, "
    "peak→fast/new_material. 3) sample_dialogue_turn is plausible Vietnamese-"
    "learner English."
)

MOOD_SYSTEM = (
    "You generate synthetic Mood & Pattern samples used to validate the "
    "5-tier energy-aware pacing engine. Output JSON for MoodPatternBatch only."
)


def run_mood(count: int) -> None:
    data = load_json(PATHS["mood"])
    samples = data["samples"]
    seen = {s["sample_dialogue_turn"].strip().lower()[:120] for s in samples}
    needed = max(0, count - len(samples))
    if needed == 0:
        log.info("mood already at target (%d)", len(samples))
        return

    llm = make_llm()
    pipeline = SyntheticPipeline(
        llm=llm,
        item_schema=MoodPatternBatch,
        extract_items=lambda b: b.samples,
    )

    seeds = [
        {"persona": "first_timer", "energy": "low"},
        {"persona": "first_timer", "energy": "neutral"},
        {"persona": "speed_runner", "energy": "energized"},
        {"persona": "speed_runner", "energy": "exhausted"},
        {"persona": "qa_destroyer", "energy": "peak"},
    ]

    def builder(sampled: list[dict]) -> str:
        seed_str = ", ".join(f"{s['persona']}/{s['energy']}" for s in sampled)
        return (
            "Generate 5 NEW Mood & Pattern samples covering these "
            f"persona/energy combinations: {seed_str}. "
            "Use ISO-8601 timestamps. contextual_signals must include at least "
            "two indirect cues (e.g. response latency, message length, time-of-day)."
        )

    accepted = pipeline.run(
        system_prompt=MOOD_SYSTEM,
        user_prompt_builder=builder,
        seeds=seeds,
        rubric=MOOD_RUBRIC,
        target_count=needed,
        seen_keys=seen,
        key_fn=lambda s: s.sample_dialogue_turn,
        seeds_per_call=3,
    )
    for item in accepted:
        d = item.model_dump()
        d["sample_dialogue_turn"] = SENTINEL.scrub(d["sample_dialogue_turn"])
        if not d.get("id"):
            d["id"] = f"MOOD-{short_id()}"
        if not d.get("timestamp"):
            d["timestamp"] = utcnow_iso()
        samples.append(d)

    data["samples"] = samples
    data["metadata"]["total_samples"] = len(samples)
    save_json(PATHS["mood"], data)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

TASKS: dict[str, Callable[[argparse.Namespace], None]] = {
    "errors": lambda a: run_errors(a.count or 500),
    "industry_vocab": lambda a: run_industry(a.count or 50, a.industry),
    "mem0_facts": lambda a: run_mem0(a.count or 100, a.persona),
    "ielts": lambda a: run_ielts(a.count or 60),
    "pedagogical": lambda a: run_pedagogical(a.count or 80),
    "mood": lambda a: run_mood(a.count or 60),
}


INDUSTRY_CHOICES = ["IT", "Marketing", "Sales", "Finance", "Education", "Healthcare"]
PERSONA_CHOICES = ["first_timer", "speed_runner", "qa_destroyer"]


def add_arguments(parser: argparse.ArgumentParser) -> None:
    """Register synthetic-generate arguments on ``parser``.

    Shared by the standalone CLI (``main`` below) and the unified
    ``a20-pipeline generate`` subcommand in :mod:`data_pipeline.command_line_interface`.
    """
    parser.add_argument(
        "--task",
        choices=["all", *TASKS.keys()],
        required=True,
    )
    parser.add_argument("--count", type=int, default=None)
    parser.add_argument("--industry", choices=INDUSTRY_CHOICES, default=None)
    parser.add_argument("--persona", choices=PERSONA_CHOICES, default=None)


def run(args: argparse.Namespace) -> int:
    tasks = list(TASKS.keys()) if args.task == "all" else [args.task]
    for name in tasks:
        log.info("=== task: %s ===", name)
        TASKS[name](args)
    log.info("done.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="A20 data generator")
    add_arguments(parser)
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
