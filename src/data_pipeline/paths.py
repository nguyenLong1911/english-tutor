"""Canonical filesystem paths for the A20 data pipeline."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
CURRICULUM = DATA / "curriculum_skeleton"

RAW_WIKIPEDIA_GLOSSARIES = RAW / "wikipedia" / "glossaries"
RAW_HUGGINGFACE = RAW / "huggingface"
RAW_JFLEG = RAW_HUGGINGFACE / "jfleg"
RAW_IELTS = RAW / "ielts"

COMMON_ERRORS_DIR = PROCESSED / "common_errors"
INDUSTRY_VOCAB_DIR = PROCESSED / "industry_vocab"
IELTS_DIR = PROCESSED / "ielts_writing"
PEDAGOGICAL_DIR = PROCESSED / "pedagogical_prompts"
MOOD_DIR = PROCESSED / "mood_pattern"
MEM0_DIR = PROCESSED / "mem0_facts"
SYNTHETIC_PROFILES_DIR = PROCESSED / "synthetic_profiles"

ERROR_BANK = COMMON_ERRORS_DIR / "v_english_error_bank.json"
JFLEG_AUTO = COMMON_ERRORS_DIR / "jfleg_auto_extracted.json"
INDUSTRY_CANONICAL = INDUSTRY_VOCAB_DIR / "industry_context_library.json"
WIKI_AUTO = INDUSTRY_VOCAB_DIR / "wiki_auto_extracted.json"
IELTS = IELTS_DIR / "ielts_writing_task2.json"
PEDAGOGICAL = PEDAGOGICAL_DIR / "pedagogical_prompts.json"
MOOD = MOOD_DIR / "mood_pattern_samples.json"
MEM0 = MEM0_DIR / "mem0_initial_facts.json"
LEARNER_PROFILES = SYNTHETIC_PROFILES_DIR / "learner_profiles.json"

OFFLINE_PROCESS_REPORT = PROCESSED / "offline_process_report.json"
QUALITY_PROCESS_REPORT = PROCESSED / "quality_process_report.json"
SCRAPE_QUEUE = PROCESSED / "_scrape_queue.json"
JFLEG_CHECKPOINT = PROCESSED / "_ckpt_jfleg.json"

GENERATED_DATASETS = {
    "errors": ERROR_BANK,
    "industry_vocab": INDUSTRY_CANONICAL,
    "mem0": MEM0,
    "ielts": IELTS,
    "pedagogical": PEDAGOGICAL,
    "mood": MOOD,
}
