# `src/data_pipeline`

Production-grade data pipeline for the **A20 Agentic Language Tutor** project.
Implements the architecture from
[`docs/Hướng dẫn AI Agent thu thập dữ liệu.md`](../../docs/Hướng%20dẫn%20AI%20Agent%20thu%20thập%20dữ%20liệu.md).

## Install as a standalone module

```bash
pip install -e .            # editable install, exposes `import data_pipeline`
a20-pipeline info           # console-script entry point
python -m data_pipeline scrape --sources wikipedia huggingface ielts
python -m data_pipeline process-existing
python -m data_pipeline quality-process
python -m data_pipeline validate
python -m data_pipeline audit
```

The package is configured via the project-root `pyproject.toml`. Sources for
keyless collection live under `src/data_pipeline/sources/`:

| Source | Key required? | Output |
|---|---|---|
| `sources.wikipedia` | No (MediaWiki public API) | `data/raw/wikipedia/glossaries/<industry>.json` |
| `sources.huggingface` | No (GitHub raw for JFLEG; opt-in `--use-hf` for `datasets` lib) | `data/raw/huggingface/jfleg/*.jsonl` |
| `sources.ielts_public` | No (TargetedScraper, robots.txt aware) | `data/raw/ielts/*.txt` + `manifest.json` |

`data/raw/` is gitignored to keep third-party content out of the repository.

## Architecture

The package is organized as a small pipeline stack. Shared infrastructure is
kept separate from collection, extraction, generation, local processing, and
verification, so command modules do not each redefine paths, JSON helpers, or
env loading.

| Layer | Files | Responsibility |
|---|---|---|
| Contracts | `schemas.py` | Pydantic models used as constrained-decoding and validation contracts. |
| Shared infrastructure | `paths.py`, `json_io.py`, `env.py`, `retry.py`, `checkpoint.py`, `observability.py` | Canonical paths, UTF-8 JSON/JSONL I/O, env loading, retries, resumability, and LLM call tracing. |
| Collection | `scraper.py`, `sources/*.py` | Targeted, robots-aware raw collection into `data/raw`. |
| Rule extraction | `extractors/*.py` | Local raw-to-processed extraction that does not call an LLM. |
| LLM generation | `llm_client.py`, `synthetic.py`, `generate.py`, `pii_filter.py`, `mem0_extractor.py` | Structured LLM calls, synthetic-data engineering, PII scrubbing, and Mem0 fact extraction. |
| Local processing | `offline_process.py`, `quality_process.py` | Cleanup, deterministic expansion, and final alpha quality gate over existing `data/processed`. |
| Verification | `validate.py`, `audit.py` | Schema validation and PRD/data-doc readiness checks. |

## Module Map

```text
data_pipeline/
  cli.py                  # command router only
  paths.py                # one source of truth for data paths
  json_io.py              # JSON + JSONL helpers
  env.py                  # .env loading for repo root and src/.env
  schemas.py              # all dataset contracts
  sources/                # raw collectors
  extractors/             # rule-based raw -> processed conversion
  generate.py             # LLM-backed synthetic generation tasks
  offline_process.py      # local-only cleanup and deterministic expansion
  quality_process.py      # final quality gate + bounded LLM certification
  validate.py             # schema validation
  audit.py                # PRD/data-doc readiness audit
```

## How a generation run flows

```text
seed dataset (JSON)
        │
        ▼
   sample seeds  ─────►  StructuredLLM.parse(schema=Batch)  ◄─── retry/backoff
        │                          │
        │                          ▼
        │                 Pydantic validation
        │                          │     (failure → repair loop)
        │                          ▼
        ▼                  decontamination (key-hash)
   LLM-as-a-Judge (rubric)   ─►   accept ≥ threshold
        │
        ▼
   PIISentinel.scrub  ──►  persist JSON  ──►  validate_data.py (CI gate)
```

## CLI orchestrator

```bash
python -m data_pipeline generate --task all
python -m data_pipeline generate --task ielts --count 60
python -m data_pipeline process-existing
python -m data_pipeline quality-process
python -m data_pipeline validate
python -m data_pipeline audit
```

## Current local-only workflow

When no more external collection is desired, run:

```bash
python -m data_pipeline process-existing
python -m data_pipeline quality-process
python -m data_pipeline validate
python -m data_pipeline audit
```

`process-existing` does not scrape websites and does not call LLM APIs. It:

* cleans raw Wikipedia markup already present in processed vocabulary files;
* promotes rule-filtered JFLEG candidates into the canonical error bank until
  the local target is met, while retaining `needs_teacher_review`;
* expands IELTS, pedagogical, mood, and Mem0 seed datasets deterministically
  from existing local seeds.

`quality-process` is the final local readiness gate after offline or LLM
generation. It does not collect raw data. By default it also performs one
bounded aggregate LLM certification call, without sending raw corpus rows; use
`--no-llm` to skip that call. It:

* clears promoted JFLEG `needs_teacher_review` only after the alpha quality
  gate records review metadata;
* fills missing industry `definition_vi`, `example_sentence`, and `usage_note`
  fields;
* expands IELTS Task 2 essays to the 250-word minimum and fixes placeholders;
* marks pedagogical, mood, and Mem0 records as decontamination-checked.

## Extending

* **New dataset:** add a Pydantic batch schema in `schemas.py`, register a task
  function in `generate_data.py`, drop a seed JSON under `data/processed/<name>/`.
* **New PII strategy:** subclass `PIISentinel` and override `_scrub_*` passes.
* **Replace LLM-as-a-judge with embeddings:** swap
  `SyntheticPipeline.decontaminate` to use `text-embedding-3-small` cosine
  similarity (target Sprint 2).
