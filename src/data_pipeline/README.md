# `src/data_pipeline`

This package prepares **static evaluation, benchmark, and demo seed data** for
Agentic Language Tutor.

It intentionally does **not** own production learner memory. Per
[`PRD_v2.md`](../../docs/project%20requirements/PRD_v2.md) and
[`data_planning.md`](../../docs/data%20layer/scraping/data_planning.md),
runtime personalization comes from real user profile/session/error/mood/SM-2
data. The files here only prepare the static datasets used to test, benchmark,
regress, and demo that runtime system.

## Read The Code In This Order

```text
data_pipeline/
  command_line_interface.py
    The only entry point. Maps CLI commands to the phase files below.

  reference_data_collection/
    Optional, small reference collection into data/raw/.
    Use this only when a dataset needs public reference material with provenance.

    sources/
      wikipedia.py       -> industry glossary references
      huggingface.py     -> JFLEG rows for error-bank extraction
      ielts_public.py    -> opt-in, robots-aware IELTS page references

    robots_aware_scraper.py
      Shared helper for respectful web collection.

  evaluation_seed_preparation/
    Builds processed static datasets under data/processed/.

    raw_to_processed_extractors/
      jfleg_to_errors.py           -> Common Errors / Error Bank candidates
      wiki_to_industry_vocab.py    -> Industry Context Library candidates

    generate_synthetic_seed_datasets.py
      LLM generation for static seed/eval datasets when local seeds are not
      enough.

    process_existing_seed_data.py
      Local-only cleanup and deterministic expansion. No scraping, no LLM.

    run_alpha_quality_gate.py
      Final review pass over processed datasets, with optional aggregate LLM
      certification.

    scrub_pii.py
      PII scrubber before anything becomes seed/eval data.

    synthetic_generation_workflow.py
      Shared seed -> expand -> judge -> decontaminate workflow.

  evaluation_readiness_checks/
    Confirms processed datasets are usable for alpha evaluation.

    validate_processed_dataset_schemas.py
      Pydantic validation for every processed JSON dataset.

    audit_prd_eval_corpus_readiness.py
      PRD/data-planning readiness checks and warnings.

  shared_pipeline_support/
    Cross-cutting support code. Nothing here is a product feature or data phase.

    data_file_paths.py
      Canonical data/raw and data/processed paths.

    processed_dataset_schemas.py
      Pydantic contracts for Common Errors, Industry Vocab, IELTS,
      Pedagogical Prompts, Mood Patterns, Mem0 Initial Facts, and learner
      profiles.

    json_dataset_file_io.py
      UTF-8 JSON/JSONL helpers.

    load_pipeline_environment.py
      Loads `.env` files for LLM-backed commands.

    structured_llm_client.py
      Structured-output Gemini/Groq client used by synthetic generation and
      aggregate quality certification.

    retry_and_circuit_breaker.py
      Retry/backoff policy for external calls.

    llm_call_observability.py
      JSONL tracing for LLM latency, token usage, and estimated cost.
```

## CLI

```bash
python -m data_pipeline info
python -m data_pipeline scrape --sources wikipedia huggingface
python -m data_pipeline extract
python -m data_pipeline process-existing
python -m data_pipeline quality-process --no-llm
python -m data_pipeline validate
python -m data_pipeline audit
```

Use the local-only path when you do not want network or LLM calls:

```bash
python -m data_pipeline process-existing
python -m data_pipeline quality-process --no-llm
python -m data_pipeline validate
python -m data_pipeline audit
```

## Dataset Mapping

| `data_planning.md` output | Code that prepares/checks it |
|---|---|
| V-English Error Bank | `raw_to_processed_extractors/jfleg_to_errors.py`, `generate_synthetic_seed_datasets.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |
| Industry Context Library | `sources/wikipedia.py`, `raw_to_processed_extractors/wiki_to_industry_vocab.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |
| IELTS Writing Samples | `generate_synthetic_seed_datasets.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |
| Pedagogical Prompt Samples | `generate_synthetic_seed_datasets.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |
| Mood Pattern Samples | `generate_synthetic_seed_datasets.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |
| Mem0 Initial Facts | `generate_synthetic_seed_datasets.py`, `process_existing_seed_data.py`, `run_alpha_quality_gate.py` |

## What This Package Does Not Do

It does not run the production tutor, write live learner memories, schedule
SM-2 reviews, aggregate real Error DNA, or power runtime Context Injection.
Those belong to backend runtime services. This package only creates and checks
static data used to evaluate those systems.
