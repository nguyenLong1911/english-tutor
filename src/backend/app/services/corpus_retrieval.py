"""Retrieval layer over the static ``corpus`` Qdrant collection.

Semantic search over vocabulary, common errors, pedagogical prompts, and
IELTS samples — ingested by ``app.seeders.ingest_corpus_to_qdrant``.

The LangGraph chat pipeline uses this as a *supplement* to Mem0: Mem0
stores the user's personal facts (what they struggle with, what they've
studied), while corpus retrieval surfaces the *content* that can answer
their current turn (vocab definitions, error patterns to flag, scaffolds
to imitate).

Design notes
------------
* **Kind-scoped searches.** Callers typically want one kind per turn
  (e.g. only vocab for a QUICK_QA intent), so the default ``search`` API
  accepts a ``kind`` filter. ``search_many`` runs one query across a
  list of kinds and returns a ``{kind: [hits]}`` mapping — one Qdrant
  round-trip per kind; Qdrant doesn't natively support grouping by a
  payload field on dense search.
* **Graceful degradation.** If the ``corpus`` collection doesn't exist
  yet (ingestion not run) or the embedder can't be built, ``search``
  returns ``[]`` with a warning — the caller (chat pipeline) keeps
  working using Mem0 + SQL fallbacks.
* The embedder is lazily built and cached per-process so retrieval
  doesn't pay the ``genai.Client`` / ``OpenAI`` init cost on every turn.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Iterable

from ..core.config import get_settings
from .corpus_embedding import (
    CorpusEmbedder,
    EmbeddingError,
    build_corpus_embedder,
)

logger = logging.getLogger(__name__)

_QDRANT_CORPUS = "corpus"

_embedder_lock = threading.Lock()
_embedder: CorpusEmbedder | None = None
_embedder_failed = False


def _get_embedder() -> CorpusEmbedder | None:
    global _embedder, _embedder_failed
    if _embedder is not None:
        return _embedder
    if _embedder_failed:
        return None
    with _embedder_lock:
        if _embedder is not None:
            return _embedder
        if _embedder_failed:
            return None
        try:
            _embedder = build_corpus_embedder()
            return _embedder
        except EmbeddingError as exc:
            logger.warning("corpus retrieval disabled: %s", exc)
            _embedder_failed = True
            return None


def _qdrant_client():
    try:
        from qdrant_client import QdrantClient  # type: ignore
    except Exception as exc:  # pragma: no cover - optional dep
        logger.warning("qdrant_client not installed: %s", exc)
        return None
    s = get_settings()
    return QdrantClient(url=s.QDRANT_URL, check_compatibility=False)


def _collection_exists(client) -> bool:
    try:
        names = {c.name for c in client.get_collections().collections}
        return _QDRANT_CORPUS in names
    except Exception as exc:  # pragma: no cover - network/infra error
        logger.warning("corpus collection probe failed: %s", exc)
        return False


def _filter_for(kind: str | None, extra: dict[str, Any] | None):
    from qdrant_client.http import models as qm  # type: ignore

    must = []
    if kind:
        must.append(qm.FieldCondition(key="kind", match=qm.MatchValue(value=kind)))
    for key, value in (extra or {}).items():
        if value is None:
            continue
        must.append(qm.FieldCondition(key=key, match=qm.MatchValue(value=value)))
    return qm.Filter(must=must) if must else None


def _hit_to_dict(hit) -> dict[str, Any]:
    payload = hit.payload or {}
    # Never hand back the raw vector or the content_hash — the chat
    # pipeline only cares about the human-readable payload + score.
    out = {k: v for k, v in payload.items() if k not in ("content_hash",)}
    out["score"] = float(hit.score)
    return out


def _qdrant_search(client, vector, limit, query_filter):
    """Shim for Qdrant client ``search`` (1.11–1.17) vs ``query_points`` (1.18+).

    Returns a list of hit objects with ``.payload`` and ``.score``.
    """
    # qdrant-client ≥1.18 exposes ``query_points``; older releases only
    # have ``search``. Try the new API first and fall back.
    if hasattr(client, "query_points"):
        res = client.query_points(
            collection_name=_QDRANT_CORPUS,
            query=vector,
            limit=limit,
            query_filter=query_filter,
            with_payload=True,
        )
        # query_points returns QueryResponse(points=[...]).
        return getattr(res, "points", res)
    return client.search(
        collection_name=_QDRANT_CORPUS,
        query_vector=vector,
        limit=limit,
        query_filter=query_filter,
        with_payload=True,
    )


def search(
    query: str,
    kind: str | None = None,
    top_k: int = 5,
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Return the top-K corpus records for ``query``.

    ``filters`` is an optional ``payload_field → exact_value`` mapping
    (e.g. ``{"cefr_level": "B1", "industry": "IT"}``). Returns ``[]``
    silently when the embedder or collection isn't available so callers
    can safely wrap this in a best-effort block.
    """
    if not query or not query.strip():
        return []
    embedder = _get_embedder()
    if embedder is None:
        return []
    client = _qdrant_client()
    if client is None:
        return []
    if not _collection_exists(client):
        logger.debug("corpus collection missing — ingest_corpus_to_qdrant has not run")
        return []
    try:
        vector = embedder.embed_batch([query.strip()])[0]
    except EmbeddingError as exc:
        logger.warning("corpus retrieval embed failed: %s", exc)
        return []
    try:
        hits = _qdrant_search(client, vector, top_k, _filter_for(kind, filters))
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("qdrant search failed: %s", exc)
        return []
    return [_hit_to_dict(h) for h in hits]


def search_many(
    query: str,
    kinds: Iterable[str],
    top_k_per_kind: int = 3,
    filters: dict[str, Any] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    """Convenience wrapper for pipelines that want ``{kind: [...]}``.

    Runs one Qdrant round-trip per kind (cheap — all in-process after the
    single embedding call would be even cheaper, but Qdrant's Python SDK
    doesn't expose `group_by` for dense search in 1.11).
    """
    embedder = _get_embedder()
    client = _qdrant_client()
    if embedder is None or client is None or not _collection_exists(client):
        return {k: [] for k in kinds}
    try:
        vector = embedder.embed_batch([query.strip()])[0]
    except EmbeddingError as exc:
        logger.warning("corpus retrieval embed failed: %s", exc)
        return {k: [] for k in kinds}
    out: dict[str, list[dict[str, Any]]] = {}
    for kind in kinds:
        try:
            hits = _qdrant_search(client, vector, top_k_per_kind, _filter_for(kind, filters))
            out[kind] = [_hit_to_dict(h) for h in hits]
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("qdrant search(kind=%s) failed: %s", kind, exc)
            out[kind] = []
    return out


def is_enabled() -> bool:
    """Feature flag. Off by default until operators run ingestion + opt in.

    Env: ``CORPUS_RETRIEVAL_ENABLED=true``.
    """
    return os.getenv("CORPUS_RETRIEVAL_ENABLED", "").lower() == "true"
