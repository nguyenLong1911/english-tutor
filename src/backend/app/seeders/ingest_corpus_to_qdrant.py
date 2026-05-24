"""Ingest the curated eval/demo content corpus into Qdrant as dense vectors.

Scope
-----
The JSON corpus under ``data/processed/`` is now treated as static
evaluation/benchmark/seed data. This script embeds the same corpus into Qdrant
for manual retrieval experiments, demos, and regression checks. It is not part
of the live chat hotpath; the tutor runtime relies on LLM orchestration plus
user-generated profile/progress/Mem0 facts.

Kinds handled (83 records total at the time of writing):

* ``vocab``  — ``industry_vocab/industry_context_library.json`` (33 items)
* ``error``  — ``common_errors/v_english_error_bank.json`` (36 items)
* ``prompt`` — ``pedagogical_prompts/pedagogical_prompts.json`` (8 items)
* ``ielts``  — ``ielts_writing/ielts_writing_task2.json`` (6 items)

Design
------
* Single Qdrant collection ``corpus`` (1536-dim Cosine), ``kind`` payload
  discriminator. Reusing one collection keeps the retrieval API trivial
  and the dim identical to ``tutor_memory`` so embedder swaps don't force
  a reindex.
* **Deterministic point IDs** (UUIDv5 over ``(kind, source_id)``) so the
  script is idempotent: re-running after a partial failure overwrites,
  never duplicates.
* **Resumable.** Before embedding we diff the processed payload against
  the existing Qdrant points and skip those whose ``content_hash``
  already matches — relevant when the previous run tripped a Vertex 429
  halfway through.

Run (inside backend container)::

    docker compose exec backend python -m app.seeders.ingest_corpus_to_qdrant
    docker compose exec backend python -m app.seeders.ingest_corpus_to_qdrant --kinds vocab,error
    docker compose exec backend python -m app.seeders.ingest_corpus_to_qdrant --limit 20  # demo run
    docker compose exec backend python -m app.seeders.ingest_corpus_to_qdrant --force     # ignore content_hash cache

The text-to-embed builder for each kind lives in ``_build_text_for_*`` —
tweak those when you change how the corpus should be semantically indexed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from ..core.config import get_settings
from ..services.corpus_embedding import (
    EmbeddingError,
    EmbeddingRateLimited,
    build_corpus_embedder,
)

logger = logging.getLogger(__name__)

QDRANT_COLLECTION = "corpus"
NAMESPACE = uuid.UUID("a20a20a0-c0c0-4b1b-9d9d-c0c0c0c0c0c0")
ALL_KINDS = ("vocab", "error", "prompt", "ielts")


# --------------------------------------------------------------------------- #
# Record model                                                                #
# --------------------------------------------------------------------------- #


@dataclass
class CorpusRecord:
    kind: str
    source_id: str           # stable upstream id (used to build deterministic point id)
    text: str                # text we actually embed
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def point_id(self) -> str:
        return str(uuid.uuid5(NAMESPACE, f"{self.kind}::{self.source_id}"))

    @property
    def content_hash(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Per-kind loaders — each returns [CorpusRecord, …]                           #
# --------------------------------------------------------------------------- #


def _read_json(path: Path) -> Any:
    if not path.exists():
        logger.warning("Missing corpus file: %s", path)
        return None
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _build_text_for_vocab(item: dict, industry: str) -> str:
    parts = [
        f"[VOCAB] {item.get('term','').strip()}",
        f"definition_en: {item.get('definition_en','').strip()}",
        f"definition_vi: {item.get('definition_vi','').strip()}",
        f"example: {item.get('example_sentence','').strip()}",
        f"industry: {industry}",
        f"cefr: {item.get('cefr_level','B2').strip()}",
    ]
    related = item.get("related_terms") or []
    if related:
        parts.append("related: " + ", ".join(str(t) for t in related))
    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip() not in ("", "None"))


def _load_vocab(data_dir: Path) -> list[CorpusRecord]:
    data = _read_json(data_dir / "industry_vocab" / "industry_context_library.json")
    out: list[CorpusRecord] = []
    if not isinstance(data, dict):
        return out
    for industry_key, block in (data.get("industries") or {}).items():
        for item in (block or {}).get("vocabulary") or []:
            term = (item.get("term") or "").strip()
            if not term:
                continue
            source_id = f"{industry_key.lower()}::{term.lower()}"
            text = _build_text_for_vocab(item, industry_key)
            out.append(
                CorpusRecord(
                    kind="vocab",
                    source_id=source_id,
                    text=text,
                    payload={
                        "kind": "vocab",
                        "term": term,
                        "industry": industry_key,
                        "cefr_level": item.get("cefr_level") or "B2",
                        "definition_vi": item.get("definition_vi") or "",
                        "definition_en": item.get("definition_en") or "",
                        "example": item.get("example_sentence") or "",
                        "tags": item.get("tags") or [],
                    },
                )
            )
    return out


def _build_text_for_error(item: dict) -> str:
    parts = [
        f"[ERROR] {item.get('error_pattern','').strip()}",
        f"category: {item.get('category','').strip()}",
        f"incorrect: {item.get('incorrect_example','').strip()}",
        f"correct: {item.get('correct_example','').strip()}",
        f"explanation_vi: {item.get('explanation_vi','').strip()}",
    ]
    if item.get("explanation_en"):
        parts.append(f"explanation_en: {item['explanation_en'].strip()}")
    return "\n".join(p for p in parts if p.split(": ", 1)[-1].strip() not in ("", "None"))


def _load_errors(data_dir: Path) -> list[CorpusRecord]:
    data = _read_json(data_dir / "common_errors" / "v_english_error_bank.json")
    out: list[CorpusRecord] = []
    if not isinstance(data, dict):
        return out
    for item in data.get("errors") or []:
        eid = (item.get("id") or "").strip()
        if not eid:
            continue
        out.append(
            CorpusRecord(
                kind="error",
                source_id=eid,
                text=_build_text_for_error(item),
                payload={
                    "kind": "error",
                    "error_id": eid,
                    "category": item.get("category") or "",
                    "error_pattern": item.get("error_pattern") or "",
                    "incorrect_example": item.get("incorrect_example") or "",
                    "correct_example": item.get("correct_example") or "",
                    "explanation_vi": item.get("explanation_vi") or "",
                    "cefr_level": item.get("cefr_level") or "B1",
                    "tags": item.get("tags") or [],
                    "importance_score": item.get("importance_score") or 0.5,
                },
            )
        )
    return out


def _build_text_for_prompt(item: dict) -> str:
    parts = [
        f"[PROMPT] {item.get('learner_situation','').strip()}",
        "scaffolding_steps:",
        *[f"  - {s}" for s in (item.get('scaffolding_steps') or []) if s],
        "socratic_questions:",
        *[f"  - {q}" for q in (item.get('socratic_questions') or []) if q],
        f"expected_outcome: {item.get('expected_outcome','').strip()}",
        f"target_skill: {item.get('target_skill','').strip()}",
        f"cefr: {item.get('cefr_level','B1').strip()}",
    ]
    return "\n".join(parts)


def _load_prompts(data_dir: Path) -> list[CorpusRecord]:
    data = _read_json(data_dir / "pedagogical_prompts" / "pedagogical_prompts.json")
    out: list[CorpusRecord] = []
    if not isinstance(data, dict):
        return out
    for item in data.get("prompts") or []:
        pid = (item.get("id") or "").strip()
        if not pid:
            continue
        out.append(
            CorpusRecord(
                kind="prompt",
                source_id=pid,
                text=_build_text_for_prompt(item),
                payload={
                    "kind": "prompt",
                    "prompt_id": pid,
                    "target_skill": item.get("target_skill") or "",
                    "cefr_level": item.get("cefr_level") or "B1",
                    "learner_situation": item.get("learner_situation") or "",
                    "scaffolding_steps": item.get("scaffolding_steps") or [],
                    "socratic_questions": item.get("socratic_questions") or [],
                    "expected_outcome": item.get("expected_outcome") or "",
                    "tags": item.get("tags") or [],
                },
            )
        )
    return out


def _build_text_for_ielts(item: dict) -> str:
    return "\n".join(
        [
            f"[IELTS] prompt: {item.get('prompt','').strip()}",
            f"band: {item.get('band','')}",
            f"topic: {item.get('topic','').strip()}",
            f"essay: {item.get('essay','').strip()}",
            f"examiner_feedback: {item.get('examiner_feedback','').strip()}",
        ]
    )


def _load_ielts(data_dir: Path) -> list[CorpusRecord]:
    data = _read_json(data_dir / "ielts_writing" / "ielts_writing_task2.json")
    out: list[CorpusRecord] = []
    if not isinstance(data, dict):
        return out
    for item in data.get("samples") or []:
        sid = (item.get("id") or "").strip()
        if not sid:
            continue
        out.append(
            CorpusRecord(
                kind="ielts",
                source_id=sid,
                text=_build_text_for_ielts(item),
                payload={
                    "kind": "ielts",
                    "sample_id": sid,
                    "prompt": item.get("prompt") or "",
                    "band": item.get("band") or 0,
                    "topic": item.get("topic") or "",
                    "essay": item.get("essay") or "",
                    "examiner_feedback": item.get("examiner_feedback") or "",
                    "cefr_level": item.get("cefr_level") or "B2",
                },
            )
        )
    return out


_LOADERS = {
    "vocab": _load_vocab,
    "error": _load_errors,
    "prompt": _load_prompts,
    "ielts": _load_ielts,
}


# --------------------------------------------------------------------------- #
# Qdrant helpers                                                              #
# --------------------------------------------------------------------------- #


def _qdrant_client():
    from qdrant_client import QdrantClient  # type: ignore
    s = get_settings()
    return QdrantClient(url=s.QDRANT_URL, check_compatibility=False)


def _ensure_collection(client, dim: int) -> None:
    from qdrant_client.http import models as qm  # type: ignore

    existing = {c.name for c in client.get_collections().collections}
    if QDRANT_COLLECTION in existing:
        info = client.get_collection(QDRANT_COLLECTION)
        current_dim = info.config.params.vectors.size  # type: ignore[attr-defined]
        if current_dim != dim:
            raise EmbeddingError(
                f"Qdrant '{QDRANT_COLLECTION}' is dim={current_dim} but embedder "
                f"produces dim={dim}. Recreate collection (see runbook)."
            )
        return

    client.create_collection(
        collection_name=QDRANT_COLLECTION,
        vectors_config=qm.VectorParams(size=dim, distance=qm.Distance.COSINE),
    )
    # Payload indexes for the query patterns we care about. Keyword index
    # on ``kind`` + ``cefr_level`` + ``industry`` (the most common filters
    # from the retrieval service).
    for field_name in ("kind", "cefr_level", "industry", "target_skill", "category"):
        try:
            client.create_payload_index(
                collection_name=QDRANT_COLLECTION,
                field_name=field_name,
                field_schema=qm.PayloadSchemaType.KEYWORD,
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("payload index for %s skipped: %s", field_name, exc)
    logger.info("created Qdrant collection %s (dim=%s)", QDRANT_COLLECTION, dim)


def _fetch_existing_hashes(client, point_ids: list[str]) -> dict[str, str]:
    if not point_ids:
        return {}
    points = client.retrieve(
        collection_name=QDRANT_COLLECTION,
        ids=point_ids,
        with_payload=True,
        with_vectors=False,
    )
    return {
        str(p.id): (p.payload or {}).get("content_hash", "")
        for p in points
    }


# --------------------------------------------------------------------------- #
# Main ingestion loop                                                         #
# --------------------------------------------------------------------------- #


def ingest(
    kinds: Iterable[str] = ALL_KINDS,
    limit: int | None = None,
    force: bool = False,
    batch_size: int = 8,
    embedder_prefer: str | None = None,
) -> dict[str, Any]:
    s = get_settings()
    data_dir = Path(s.PROCESSED_DATA_DIR)
    if not data_dir.exists():
        raise EmbeddingError(f"PROCESSED_DATA_DIR not found: {data_dir}")

    # 1) Load records from JSON.
    records: list[CorpusRecord] = []
    for kind in kinds:
        if kind not in _LOADERS:
            raise EmbeddingError(f"unknown kind: {kind}")
        records.extend(_LOADERS[kind](data_dir))
    if limit is not None:
        records = records[:limit]
    if not records:
        return {"total": 0, "embedded": 0, "skipped": 0, "errors": 0}

    # 2) Prepare embedder + Qdrant.
    embedder = build_corpus_embedder(s, prefer=embedder_prefer)
    client = _qdrant_client()
    _ensure_collection(client, embedder.info.dim)

    # 3) Skip-if-unchanged diff (unless --force).
    existing = {} if force else _fetch_existing_hashes(
        client, [r.point_id for r in records]
    )
    to_ingest: list[CorpusRecord] = [
        r for r in records if existing.get(r.point_id) != r.content_hash
    ]
    skipped = len(records) - len(to_ingest)
    if skipped:
        logger.info("skip-if-unchanged: %s/%s records already current", skipped, len(records))

    # 4) Embed + upsert in batches.
    from qdrant_client.http import models as qm  # type: ignore

    embedded = 0
    errors = 0
    for start in range(0, len(to_ingest), batch_size):
        batch = to_ingest[start : start + batch_size]
        texts = [r.text for r in batch]
        attempt = 0
        while True:
            try:
                vectors = embedder.embed_batch(texts)
                break
            except EmbeddingRateLimited as exc:
                attempt += 1
                if attempt > 5:
                    logger.error("giving up on batch after 5 rate-limit retries: %s", exc)
                    errors += len(batch)
                    vectors = None
                    break
                sleep_s = min(60, 2 ** attempt) * 5  # 10,20,40,60,60 s
                logger.warning("rate limited (%s). sleeping %ss then retrying", exc, sleep_s)
                time.sleep(sleep_s)
            except EmbeddingError as exc:
                logger.error("embed failed (non-retriable): %s", exc)
                errors += len(batch)
                vectors = None
                break
        if vectors is None:
            continue

        points = [
            qm.PointStruct(
                id=r.point_id,
                vector=v,
                payload={
                    **r.payload,
                    "source_id": r.source_id,
                    "content_hash": r.content_hash,
                    "text": r.text,  # retrieval surfaces this back up
                },
            )
            for r, v in zip(batch, vectors)
        ]
        client.upsert(collection_name=QDRANT_COLLECTION, points=points, wait=True)
        embedded += len(points)
        logger.info(
            "upserted batch %s/%s (+%s points, %s total)",
            start // batch_size + 1,
            -(-len(to_ingest) // batch_size),
            len(points),
            embedded,
        )

    return {
        "total_records": len(records),
        "embedded": embedded,
        "skipped_unchanged": skipped,
        "errors": errors,
        "embedder": {
            "provider": embedder.info.provider,
            "model": embedder.info.model,
            "dim": embedder.info.dim,
        },
    }


# --------------------------------------------------------------------------- #
# CLI                                                                         #
# --------------------------------------------------------------------------- #


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kinds", default=",".join(ALL_KINDS),
                        help=f"comma-separated subset of {ALL_KINDS}")
    parser.add_argument("--limit", type=int, default=None,
                        help="embed at most N records (for smoke tests)")
    parser.add_argument("--force", action="store_true",
                        help="ignore content-hash cache, re-embed everything")
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--embedder", default=None,
                        choices=["openai", "vertex", "fastembed"],
                        help="override CORPUS_EMBEDDER selection")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    kinds = [k.strip() for k in args.kinds.split(",") if k.strip()]

    try:
        summary = ingest(
            kinds=kinds,
            limit=args.limit,
            force=args.force,
            batch_size=args.batch_size,
            embedder_prefer=args.embedder,
        )
    except EmbeddingError as exc:
        print(f"INGEST FAILED: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0 if summary.get("errors", 0) == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
