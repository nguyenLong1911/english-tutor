# Data Catalog — A20 Agentic Language Tutor

Last updated: 2026-05-13

This catalog describes the local datasets used by the A20 Agentic Language Tutor alpha data layer. It is based on:

- `docs/project requirements/PRD_v2.md`
- `docs/data layer/scraping/data_planning.md`
- `docs/data layer/scraping/data_instruction.md`
- `src/data_pipeline/schemas.py`
- `data/raw/scrape_report.json`
- `data/raw/extract_report.json`
- `data/processed/offline_process_report.json`
- `data/processed/quality_process_report.json`

## Status Summary

Current data readiness: **pass with warnings**.

The processed datasets meet the alpha-size targets from the data planning docs. Schema validation passes for all processed records. The remaining warnings are product/data-readiness risks, not JSON/schema errors:

- PRD expects runtime Mem0 benchmarking at `1,000-2,000 facts/user`; current seed data contains `100 facts/persona`.
- PRD onboarding lists `A1-C1`, while the curriculum skeleton starts at `A2`.

Quality gate status:

- `465` promoted JFLEG records passed the alpha quality gate.
- `0` promoted common-error records remain marked `needs_teacher_review`.
- IELTS essays all meet the `>=250 words` minimum.
- Industry vocabulary has required `definition_vi`, `example_sentence`, and `usage_note` fields filled.
- Raw wiki markup was removed from processed vocabulary definitions.

## Pipeline Commands

Run from repo root:

```powershell
$env:PYTHONPATH='D:\porjects\A20-App-134\src'
py -m data_pipeline.cli process-existing
py -m data_pipeline.cli quality-process
py -m data_pipeline.cli validate
py -m data_pipeline.cli audit
```

Notes:

- `process-existing` is local-only: no scraping and no LLM/API calls.
- `quality-process` does not collect new raw data. By default it can perform one bounded aggregate LLM certification call without sending raw corpus rows. Use `--no-llm` to skip that certification.
- `validate` checks processed data against Pydantic schemas.
- `audit` checks PRD/data-doc readiness.

## Raw Data Inventory

| Raw dataset | Path | Source | Count | Purpose |
|---|---|---:|---:|---|
| JFLEG dev | `data/raw/huggingface/jfleg/jfleg_dev.jsonl` | JFLEG via local collected raw file | 754 | Raw learner sentence corrections for common-error extraction. |
| JFLEG test | `data/raw/huggingface/jfleg/jfleg_test.jsonl` | JFLEG via local collected raw file | 747 | Raw learner sentence corrections for common-error extraction. |
| Wikipedia IT glossary | `data/raw/wikipedia/glossaries/it.json` | Wikipedia glossary | 178 terms | Industry vocabulary seed. |
| Wikipedia Finance glossary | `data/raw/wikipedia/glossaries/finance.json` | Wikipedia glossary | 629 terms | Industry vocabulary seed. |
| Wikipedia Marketing glossary | `data/raw/wikipedia/glossaries/marketing.json` | Wikipedia pages | 26 terms | Industry vocabulary seed. |
| Wikipedia Sales glossary | `data/raw/wikipedia/glossaries/sales.json` | Wikipedia pages | 136 terms | Industry vocabulary seed. |
| Wikipedia Education glossary | `data/raw/wikipedia/glossaries/education.json` | Wikipedia glossary | 70 terms | Industry vocabulary seed. |
| Wikipedia Healthcare glossary | `data/raw/wikipedia/glossaries/healthcare.json` | Wikipedia glossary | 233 terms | Extra industry vocabulary seed. |
| Scrape report | `data/raw/scrape_report.json` | Local pipeline report | n/a | Provenance/count summary for raw collectors. |
| Extract report | `data/raw/extract_report.json` | Local pipeline report | n/a | Provenance/count summary for rule extractors. |

## Processed Dataset Inventory

| Dataset | Path | Count | Primary schema | Status | Main consumers |
|---|---|---:|---|---|---|
| V-English Error Bank | `data/processed/common_errors/v_english_error_bank.json` | 501 errors | `ESLErrorInstance` | Ready for alpha | Scaffolding engine, Error DNA, review/practice generation |
| JFLEG auto-extracted sidecar | `data/processed/common_errors/jfleg_auto_extracted.json` | 991 candidates | `ESLErrorInstance` | Valid, sidecar only | Future review/promote pool |
| Industry Context Library | `data/processed/industry_vocab/industry_context_library.json` | 527 terms | `IndustryVocabItem` | Ready for alpha | Context Injection, industry-specific practice |
| Wikipedia auto-extracted sidecar | `data/processed/industry_vocab/wiki_auto_extracted.json` | 494 terms | `IndustryVocabItem` | Valid, sidecar only | Future enrichment/promote pool |
| IELTS Writing Task 2 | `data/processed/ielts_writing/ielts_writing_task2.json` | 60 samples | `IELTSWritingSample` | Ready for alpha | Writing practice, examiner-style feedback examples |
| Pedagogical Prompts | `data/processed/pedagogical_prompts/pedagogical_prompts.json` | 80 prompts | `PedagogicalPrompt` | Ready for alpha | Scaffolding prompt selection |
| Mood Pattern Samples | `data/processed/mood_pattern/mood_pattern_samples.json` | 60 samples | `MoodPatternSample` | Ready for alpha | Mood-adaptive session logic |
| Mem0 Initial Facts | `data/processed/mem0_facts/mem0_initial_facts.json` | 300 facts | `Mem0Fact` | Ready as seed data | Mem0 bootstrap, memory retrieval tests |
| Learner Profiles | `data/processed/synthetic_profiles/learner_profiles.json` | 12 profiles | `LearnerProfile` | Ready as synthetic seeds | Future synthetic generation |
| Offline process report | `data/processed/offline_process_report.json` | n/a | report object | Informational | Data pipeline audit trail |
| Quality process report | `data/processed/quality_process_report.json` | n/a | report object | Informational | Quality gate and certification audit trail |

## Dataset Details

### V-English Error Bank

Path: `data/processed/common_errors/v_english_error_bank.json`

Purpose:

- Stores common English errors made by Vietnamese learners.
- Supports scaffolding hints, Error DNA aggregation, and targeted review.

Record schema:

- `id`
- `category`
- `error_pattern`
- `incorrect_example`
- `correct_example`
- `explanation_vi`
- `explanation_en`
- `scaffolding_hint`
- `importance_score`
- `frequency`
- `cefr_level`
- `confidence_score`
- `tags`

Current state:

- `501` records.
- `465` promoted records from JFLEG have passed the alpha quality gate.
- `0` records remain marked `needs_teacher_review`.

Important caveat:

- JFLEG is a general ESL correction corpus, not Vietnamese-only. Promoted records are rule-filtered and quality-gated for alpha, but a teacher review remains recommended before production use.

### JFLEG Auto-Extracted Sidecar

Path: `data/processed/common_errors/jfleg_auto_extracted.json`

Purpose:

- Holds raw rule-based candidates extracted from JFLEG.
- Keeps unpromoted candidates separate from the canonical error bank.

Current state:

- `991` valid candidates.
- Marked as sidecar/review pool, not the primary curated bank.

Usage:

- Use `process-existing` to promote rule-filtered candidates into the canonical bank.
- Keep this file available for future manual or LLM-assisted review.

### Industry Context Library

Path: `data/processed/industry_vocab/industry_context_library.json`

Purpose:

- Provides industry-specific vocabulary and examples for Context Injection.
- Supports PRD requirement that practice content should connect to the learner's job context.

Current counts:

- IT: `108`
- Marketing: `33`
- Sales: `106`
- Finance: `105`
- Education: `75`
- Healthcare: `100`

Record schema:

- `term`
- `definition_en`
- `definition_vi`
- `example_sentence`
- `industry`
- `register`
- `cefr_level`
- `usage_note`
- `related_terms`

Current state:

- Required fields are present.
- Raw Wikipedia markup has been cleaned.
- Healthcare is included as an extra industry even though some PRD/data-planning sections emphasize five alpha core industries.

### Wikipedia Auto-Extracted Sidecar

Path: `data/processed/industry_vocab/wiki_auto_extracted.json`

Purpose:

- Sidecar pool of cleaned Wikipedia-derived vocabulary.
- Useful for future enrichment or controlled promotion into the canonical library.

Current state:

- `494` valid records.
- Cleaned and schema-valid.

### IELTS Writing Task 2

Path: `data/processed/ielts_writing/ielts_writing_task2.json`

Purpose:

- Provides IELTS-style prompts, essays, and examiner feedback.
- Supports writing practice and feedback calibration.

Record schema:

- `id`
- `prompt`
- `band`
- `essay`
- `examiner_feedback`
- `common_errors`
- `cefr_level`
- `topic`

Current state:

- `60` samples.
- Every essay has at least `250` words.
- Examiner feedback references IELTS criteria: TR, CC, LR, GRA.

### Pedagogical Prompts

Path: `data/processed/pedagogical_prompts/pedagogical_prompts.json`

Purpose:

- Provides scaffolding scripts for "Bệnh Nghẽn", "Bệnh Quên", and error-aware tutoring.

Record schema:

- `id`
- `learner_situation`
- `scaffolding_steps`
- `socratic_questions`
- `expected_outcome`
- `target_skill`
- `cefr_level`
- `affective_filter_strategy`
- `tags`

Current state:

- `80` prompts.
- Schema-valid and marked through quality process.

### Mood Pattern Samples

Path: `data/processed/mood_pattern/mood_pattern_samples.json`

Purpose:

- Validates the five-tier mood/energy pacing logic described in PRD creative feature "Mood-Adaptive Session".

Record schema:

- `id`
- `user_persona`
- `energy_level`
- `self_reported_mood`
- `contextual_signals`
- `recommended_pace`
- `recommended_modality`
- `sample_dialogue_turn`
- `timestamp`

Current state:

- `60` samples across `exhausted`, `low`, `neutral`, `energized`, and `peak`.

### Mem0 Initial Facts

Path: `data/processed/mem0_facts/mem0_initial_facts.json`

Purpose:

- Seeds long-term memory for three alpha personas.
- Supports memory retrieval, Error DNA aggregation, and personalization tests.

Record schema:

- `fact_id`
- `user_id`
- `persona`
- `fact_type`
- `content`
- `importance_score`
- `created_at`
- `tags`
- `evidence`

Current state:

- `100` facts for `user_001_first_timer`.
- `100` facts for `user_002_speed_runner`.
- `100` facts for `user_003_qa_destroyer`.

Important caveat:

- PRD target mentions `1,000-2,000 facts/user` for stress/retrieval scale. This dataset is a seed corpus, not a full stress-test corpus.

### Learner Profiles

Path: `data/processed/synthetic_profiles/learner_profiles.json`

Purpose:

- Provides persona x CEFR x L1-transfer seeds for future synthetic dialogue/error generation.

Record schema:

- `profile_id`
- `persona`
- `cefr_level`
- `occupation`
- `l1_transfer_focus`
- `register_preference`
- `mood`
- `scenario`
- `target_skill`
- `notes`

Current state:

- `12` profiles.
- Used as seeds, not directly ingested as user-facing content.

## Curriculum Skeleton

Path: `data/curriculum_skeleton`

Purpose:

- Provides topic skeletons by CEFR level and skill area.
- Supports lesson/practice routing and future curriculum authoring.

Current state:

- Levels present: `A2`, `B1`, `B2`, `C1`, `C2`.
- PRD onboarding lists `A1-C1`; `A1` curriculum is currently missing.

## Quality And Validation

Validation command:

```powershell
$env:PYTHONPATH='D:\porjects\A20-App-134\src'
py -m data_pipeline.cli validate
```

Current validation result:

- All processed dataset records pass Pydantic schema validation.

Readiness command:

```powershell
$env:PYTHONPATH='D:\porjects\A20-App-134\src'
py -m data_pipeline.cli audit
```

Current audit result:

- `pass_with_warnings`

Warnings:

- Mem0 has seed-scale data, not the full `1,000-2,000 facts/user` runtime stress target.
- A1 curriculum is missing while PRD onboarding includes A1.

Quality certification:

- `data/processed/quality_process_report.json` includes an aggregate quality certification.
- Latest recorded certification: `ready_for_alpha: true`, `overall_score: 0.95`.

## Data Usage Map

| Product feature | Data used |
|---|---|
| Scaffolding Engine | V-English Error Bank, Pedagogical Prompts |
| Error DNA | V-English Error Bank, Mem0 `error_pattern` facts |
| Context Injection | Industry Context Library, user-pasted context at runtime |
| Mood-Adaptive Session | Mood Pattern Samples, Mem0 `mood_pattern` facts |
| Morning Brief / SM-2 | Mem0 facts, review schedules, vocabulary/error records |
| Progress Dashboard | Mem0 facts, Error DNA aggregates, review history |
| Admin cost/quality review | Observability logs, quality/audit reports |

## Open Items

1. Add A1 curriculum topics or remove A1 from onboarding for alpha.
2. Run Mem0 retrieval/load benchmark at `1,000-2,000 facts/user`.
3. Decide whether Healthcare is in alpha scope or remains an extra library.
4. Before production, run teacher review on promoted JFLEG-derived errors even though they passed alpha quality gates.
5. Keep this catalog updated whenever `process-existing`, `quality-process`, or synthetic generation changes processed counts.
