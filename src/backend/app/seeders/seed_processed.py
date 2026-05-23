"""Seed all runtime stores from ``data/processed/``.

This is the single entry point that integrates the curated artefacts produced
by ``src/data_pipeline`` (Sprint 1) into the live application:

* Postgres ``vocabulary``           ← ``industry_vocab/industry_context_library.json``
                                       (+ optional ``wiki_auto_extracted.json``
                                       entries that already have ``definition_vi``)
* Postgres ``error_bank``           ← ``common_errors/v_english_error_bank.json``
                                       (+ optional ``jfleg_auto_extracted.json``
                                       once human-reviewed)
* Postgres ``pedagogical_prompt``   ← ``pedagogical_prompts/pedagogical_prompts.json``
* Postgres ``ielts_writing_sample`` ← ``ielts_writing/ielts_writing_task2.json``
* Qdrant via Mem0                   ← ``mem0_facts/mem0_initial_facts.json``
                                       (test-persona seed; skipped when Mem0 is
                                       running on the in-memory stub, i.e. no
                                       embedding API key configured).

The script is **idempotent**: each table uses ``ON CONFLICT … DO UPDATE`` keyed
on the stable upstream ID (or ``(word, pos)`` for vocabulary), and Mem0 facts
are tagged with ``seed=true`` + ``fact_id`` so repeat runs do not duplicate.

Usage (inside the backend container)::

    docker compose exec backend python -m app.seeders.seed_processed
    docker compose exec backend python -m app.seeders.seed_processed --only vocabulary,error_bank
    docker compose exec backend python -m app.seeders.seed_processed --include-auto-extracted
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.mem0_client import get_memory
from app.models.error_bank import ErrorBank
from app.models.ielts_writing_sample import IELTSWritingSample
from app.models.pedagogical_prompt import PedagogicalPrompt
from app.models.vocabulary import Vocabulary

logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #

VALID_CEFR = {"A1", "A2", "B1", "B2", "C1", "C2"}
VALID_FREQ = {"high", "medium", "low"}


def _load_json(path: Path) -> Any:
    if not path.exists():
        logger.warning("Missing processed-data file: %s", path)
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _normalize_cefr(value: str | None, default: str = "B1") -> str:
    if not value:
        return default
    v = value.strip().upper()
    return v if v in VALID_CEFR else default


def _upsert(db, model, rows: list[dict], pk_cols: list[str]) -> int:
    """Bulk upsert ``rows`` into ``model``. Returns affected row count.

    Uses Postgres ``ON CONFLICT (pk_cols) DO UPDATE`` to make the seeder
    idempotent. ``rows`` may be empty (no-op).
    """
    if not rows:
        return 0
    stmt = pg_insert(model).values(rows)
    update_cols = {
        col.name: stmt.excluded[col.name]
        for col in model.__table__.columns
        if col.name not in pk_cols
    }
    stmt = stmt.on_conflict_do_update(index_elements=pk_cols, set_=update_cols)
    db.execute(stmt)
    return len(rows)


# --------------------------------------------------------------------------- #
# Per-dataset loaders                                                         #
# --------------------------------------------------------------------------- #

def seed_vocabulary(db, data_dir: Path, include_auto: bool = False) -> int:
    """Replace the legacy CSV seeder. Pulls curated industry vocabulary."""
    curated = _load_json(data_dir / "industry_vocab" / "industry_context_library.json")
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()

    if curated and isinstance(curated, dict):
        for industry_key, industry_block in (curated.get("industries") or {}).items():
            for item in (industry_block or {}).get("vocabulary") or []:
                word = (item.get("term") or "").strip()
                if not word:
                    continue
                pos = "noun"  # industry library has no explicit POS → default noun phrase
                key = (word.lower(), pos)
                if key in seen:
                    continue
                seen.add(key)
                rows.append(
                    {
                        "word": word,
                        "pos": pos,
                        "cefr_level": _normalize_cefr(item.get("cefr_level"), "B2"),
                        "definition_vi": (item.get("definition_vi") or item.get("definition_en") or "").strip(),
                        "example": (item.get("example_sentence") or "").strip(),
                        "industry_tags": [industry_key.lower()],
                        "confusion_with": [t for t in (item.get("related_terms") or []) if t][:5] or None,
                        "frequency_rank": None,
                    }
                )

    if include_auto:
        auto = _load_json(data_dir / "industry_vocab" / "wiki_auto_extracted.json")
        if auto and isinstance(auto, dict):
            for industry_key, industry_block in (auto.get("industries") or {}).items():
                for item in (industry_block or {}).get("vocabulary") or []:
                    word = (item.get("term") or "").strip()
                    definition_vi = (item.get("definition_vi") or "").strip()
                    # Skip records that still need translation – they would
                    # ship empty Vietnamese definitions to the learner.
                    if not word or not definition_vi:
                        continue
                    pos = "noun"
                    key = (word.lower(), pos)
                    if key in seen:
                        continue
                    seen.add(key)
                    rows.append(
                        {
                            "word": word,
                            "pos": pos,
                            "cefr_level": _normalize_cefr(item.get("cefr_level"), "B2"),
                            "definition_vi": definition_vi,
                            "example": (item.get("example_sentence") or "").strip(),
                            "industry_tags": [industry_key.lower()],
                            "confusion_with": None,
                            "frequency_rank": None,
                        }
                    )

    return _upsert(db, Vocabulary, rows, pk_cols=["word", "pos"])


def seed_error_bank(db, data_dir: Path, include_auto: bool = False) -> int:
    curated = _load_json(data_dir / "common_errors" / "v_english_error_bank.json")
    rows: list[dict] = []

    def _row_from(item: dict, source: str) -> dict | None:
        eid = (item.get("id") or "").strip()
        if not eid:
            return None
        return {
            "error_id": eid,
            "category": (item.get("category") or "uncategorized").strip(),
            "error_pattern": (item.get("error_pattern") or "").strip(),
            "incorrect_example": (item.get("incorrect_example") or "").strip(),
            "correct_example": (item.get("correct_example") or "").strip(),
            "explanation_vi": (item.get("explanation_vi") or "").strip(),
            "explanation_en": (item.get("explanation_en") or "").strip() or None,
            "scaffolding_hint": (item.get("scaffolding_hint") or "").strip() or None,
            "importance_score": float(item.get("importance_score") or 0.5),
            "frequency": (item.get("frequency") or "medium").strip().lower()
            if (item.get("frequency") or "medium").strip().lower() in VALID_FREQ
            else "medium",
            "cefr_level": _normalize_cefr(item.get("cefr_level"), "B1"),
            "tags": [t for t in (item.get("tags") or []) if t][:16],
            "confidence_score": (
                float(item["confidence_score"]) if item.get("confidence_score") is not None else None
            ),
            "source": source,
        }

    if curated and isinstance(curated, dict):
        for item in curated.get("errors") or []:
            row = _row_from(item, "curated")
            if row:
                rows.append(row)

    if include_auto:
        auto = _load_json(data_dir / "common_errors" / "jfleg_auto_extracted.json")
        if auto:
            items: Iterable[dict]
            if isinstance(auto, dict):
                items = auto.get("errors") or []
            else:
                items = auto
            for item in items:
                row = _row_from(item, "jfleg_auto")
                if row:
                    rows.append(row)

    return _upsert(db, ErrorBank, rows, pk_cols=["error_id"])


def seed_pedagogical_prompts(db, data_dir: Path) -> int:
    data = _load_json(data_dir / "pedagogical_prompts" / "pedagogical_prompts.json")
    rows: list[dict] = []
    if data and isinstance(data, dict):
        for item in data.get("prompts") or []:
            pid = (item.get("id") or "").strip()
            if not pid:
                continue
            rows.append(
                {
                    "prompt_id": pid,
                    "learner_situation": (item.get("learner_situation") or "").strip(),
                    "scaffolding_steps": [s for s in (item.get("scaffolding_steps") or []) if s],
                    "socratic_questions": [s for s in (item.get("socratic_questions") or []) if s],
                    "expected_outcome": (item.get("expected_outcome") or "").strip() or None,
                    "target_skill": (item.get("target_skill") or "grammar").strip().lower(),
                    "cefr_level": _normalize_cefr(item.get("cefr_level"), "B1"),
                    "affective_filter_strategy": (item.get("affective_filter_strategy") or "").strip() or None,
                    "tags": [t for t in (item.get("tags") or []) if t][:16],
                }
            )
    return _upsert(db, PedagogicalPrompt, rows, pk_cols=["prompt_id"])


def seed_ielts_samples(db, data_dir: Path) -> int:
    data = _load_json(data_dir / "ielts_writing" / "ielts_writing_task2.json")
    rows: list[dict] = []
    if data and isinstance(data, dict):
        for item in data.get("samples") or []:
            sid = (item.get("id") or "").strip()
            if not sid:
                continue
            rows.append(
                {
                    "sample_id": sid,
                    "prompt": (item.get("prompt") or "").strip(),
                    "band": float(item.get("band") or 0.0),
                    "essay": (item.get("essay") or "").strip(),
                    "examiner_feedback": (item.get("examiner_feedback") or "").strip() or None,
                    "common_errors": [s for s in (item.get("common_errors") or []) if s],
                    "cefr_level": _normalize_cefr(item.get("cefr_level"), "B1"),
                    "topic": (item.get("topic") or "general").strip()[:128],
                }
            )
    return _upsert(db, IELTSWritingSample, rows, pk_cols=["sample_id"])


def seed_mem0_facts(data_dir: Path) -> tuple[int, int, str]:
    """Push test-persona seed facts into Qdrant via Mem0.

    Returns ``(attempted, written, backend)`` where ``backend`` is either
    ``mem0`` (real Qdrant) or ``stub`` (in-process fallback — facts still
    land in the stub, but are not durable across restarts).
    """
    data = _load_json(data_dir / "mem0_facts" / "mem0_initial_facts.json")
    if not data or not isinstance(data, dict):
        return 0, 0, "noop"

    memory = get_memory()
    memory.warmup()
    backend = "stub" if memory.using_stub else "mem0"

    attempted = 0
    written = 0
    for persona_key, persona_block in (data.get("users") or {}).items():
        for fact in (persona_block or {}).get("facts") or []:
            content = (fact.get("content") or "").strip()
            user_id = (fact.get("user_id") or persona_key).strip()
            if not content or not user_id:
                continue
            attempted += 1
            metadata = {
                "fact_id": fact.get("fact_id"),
                "fact_type": fact.get("fact_type"),
                "persona": fact.get("persona"),
                "importance_score": fact.get("importance_score"),
                "tags": fact.get("tags") or [],
                "seed": True,
            }
            try:
                memory.add_memory(user_id=user_id, content=content, metadata=metadata)
                written += 1
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Mem0 seed failed for %s: %s", fact.get("fact_id"), exc)
    return attempted, written, backend


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #

ALL_TARGETS = ("vocabulary", "error_bank", "pedagogical_prompt", "ielts_writing_sample", "mem0_facts")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        default="",
        help=f"Comma-separated subset of targets to run. Default: all ({','.join(ALL_TARGETS)}).",
    )
    parser.add_argument(
        "--include-auto-extracted",
        action="store_true",
        help="Also ingest jfleg_auto_extracted.json + wiki_auto_extracted.json. "
        "Off by default because those files are flagged needs_review / needs_translation.",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    data_dir = Path(settings.PROCESSED_DATA_DIR)
    if not data_dir.exists():
        print(f"PROCESSED_DATA_DIR not found: {data_dir}", file=sys.stderr)
        return 2

    selected = {t.strip() for t in args.only.split(",") if t.strip()} or set(ALL_TARGETS)
    unknown = selected - set(ALL_TARGETS)
    if unknown:
        print(f"Unknown targets: {sorted(unknown)}", file=sys.stderr)
        return 2

    summary: dict[str, str] = {}
    db = SessionLocal()
    try:
        if "vocabulary" in selected:
            n = seed_vocabulary(db, data_dir, include_auto=args.include_auto_extracted)
            summary["vocabulary"] = f"{n} rows"
        if "error_bank" in selected:
            n = seed_error_bank(db, data_dir, include_auto=args.include_auto_extracted)
            summary["error_bank"] = f"{n} rows"
        if "pedagogical_prompt" in selected:
            n = seed_pedagogical_prompts(db, data_dir)
            summary["pedagogical_prompt"] = f"{n} rows"
        if "ielts_writing_sample" in selected:
            n = seed_ielts_samples(db, data_dir)
            summary["ielts_writing_sample"] = f"{n} rows"
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    if "mem0_facts" in selected:
        attempted, written, backend = seed_mem0_facts(data_dir)
        summary["mem0_facts"] = f"{written}/{attempted} via {backend}"

    print("[seed_processed] done:")
    for key in ALL_TARGETS:
        if key in summary:
            print(f"  - {key}: {summary[key]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
