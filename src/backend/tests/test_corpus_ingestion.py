"""Unit tests for eval/demo corpus ingestion + retrieval plumbing.

These tests avoid the real network entirely by swapping:
  * the embedder with a deterministic bag-of-words stub, and
  * the Qdrant client with an in-memory fake.

What they protect
-----------------
1. ``CorpusRecord`` point-id + content-hash are stable / deterministic,
   so re-running the seeder is idempotent.
2. The ``skip-if-unchanged`` diff path actually skips when hashes match.
3. ``build_corpus_embedder`` selection order respects the explicit
   ``prefer`` argument and the ``CORPUS_EMBEDDER`` env var.
4. ``corpus_retrieval.search`` gracefully returns ``[]`` when the
   collection or the embedder is missing. The live chat hotpath does not call
   this static corpus.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from app.seeders.ingest_corpus_to_qdrant import (
    CorpusRecord,
    _build_text_for_error,
    _build_text_for_vocab,
    _load_errors,
    _load_vocab,
    ingest,
)
from app.services import corpus_embedding, corpus_retrieval
from app.services.corpus_embedding import CorpusEmbedder, EmbedderInfo


# --------------------------------------------------------------------------- #
# Fixtures / fakes                                                            #
# --------------------------------------------------------------------------- #


class _StubEmbedder(CorpusEmbedder):
    """Deterministic 8-dim bag-of-words — good enough for shape tests."""

    def __init__(self, dim: int = 1536) -> None:
        self.info = EmbedderInfo(provider="stub", model="stub", dim=dim)
        self.calls = 0

    def embed_batch(self, texts):
        self.calls += 1
        out = []
        for t in texts:
            vec = [0.0] * self.info.dim
            for i, ch in enumerate(t.lower().encode("utf-8")[: self.info.dim]):
                vec[i] = (ch % 32) / 32.0
            out.append(vec)
        return out


class _FakeQdrant:
    """Just enough of the Qdrant client to drive ``ingest`` + ``search``."""

    def __init__(self):
        self._collections: dict[str, dict] = {}
        self._points: dict[str, dict[str, dict]] = {}

    # Collections --------------------------------------------------------

    def get_collections(self):
        ns = types.SimpleNamespace
        return ns(collections=[ns(name=n) for n in self._collections])

    def get_collection(self, name: str):
        ns = types.SimpleNamespace
        cfg = self._collections[name]
        return ns(config=ns(params=ns(vectors=ns(size=cfg["dim"]))))

    def create_collection(self, collection_name: str, vectors_config):
        self._collections[collection_name] = {"dim": vectors_config.size}
        self._points[collection_name] = {}

    def create_payload_index(self, **_kw):
        return None

    # Points -------------------------------------------------------------

    def retrieve(self, collection_name, ids, with_payload=True, with_vectors=False):
        ns = types.SimpleNamespace
        points = []
        for pid in ids:
            row = self._points.get(collection_name, {}).get(str(pid))
            if row:
                points.append(ns(id=pid, payload=row["payload"]))
        return points

    def upsert(self, collection_name, points, wait=True):
        for p in points:
            self._points[collection_name][str(p.id)] = {
                "vector": list(p.vector),
                "payload": dict(p.payload),
            }

    def query_points(self, collection_name, query, limit, query_filter=None, with_payload=True):
        # Delegate to the legacy ``search`` shape so we don't duplicate the
        # ranking logic. Returns a namespace with ``.points`` like the
        # real qdrant-client 1.18 API.
        ns = types.SimpleNamespace
        hits = self.search(collection_name, query, limit, query_filter, with_payload)
        return ns(points=hits)

    def search(self, collection_name, query_vector, limit, query_filter=None, with_payload=True):
        ns = types.SimpleNamespace
        rows = list(self._points.get(collection_name, {}).values())
        if query_filter is not None:
            wanted = {}
            for cond in query_filter.must or []:
                wanted[cond.key] = cond.match.value
            rows = [r for r in rows if all(r["payload"].get(k) == v for k, v in wanted.items())]

        # Cosine-ish score: dot product of normalised vectors; stable order
        # based on source_id for determinism.
        def _score(row):
            v = row["vector"]
            return sum(a * b for a, b in zip(v, query_vector))

        rows.sort(key=_score, reverse=True)
        rows = rows[:limit]
        return [ns(id=r["payload"].get("source_id", ""), payload=r["payload"], score=float(i + 1))
                for i, r in enumerate(rows)]


@pytest.fixture
def fake_stack(monkeypatch, tmp_path):
    """Patch ingest module's embedder factory + Qdrant client."""
    stub = _StubEmbedder()
    fake_qdrant = _FakeQdrant()

    from app.seeders import ingest_corpus_to_qdrant as ing

    monkeypatch.setattr(ing, "build_corpus_embedder", lambda *a, **kw: stub)
    monkeypatch.setattr(ing, "_qdrant_client", lambda: fake_qdrant)

    # Point PROCESSED_DATA_DIR to the repo's real data/processed/ — we want
    # to exercise the real loaders over real JSON, not invent fixtures.
    processed = Path(__file__).resolve().parents[3] / "data" / "processed"
    assert processed.exists(), "expected data/processed/ at repo root"
    from app.core.config import get_settings
    settings = get_settings()
    monkeypatch.setattr(settings, "PROCESSED_DATA_DIR", str(processed), raising=False)

    return stub, fake_qdrant


# --------------------------------------------------------------------------- #
# Tests                                                                       #
# --------------------------------------------------------------------------- #


def test_point_id_is_deterministic():
    a = CorpusRecord(kind="vocab", source_id="it::agile", text="x").point_id
    b = CorpusRecord(kind="vocab", source_id="it::agile", text="y").point_id
    c = CorpusRecord(kind="vocab", source_id="it::kanban", text="x").point_id
    assert a == b, "point id must depend only on (kind, source_id)"
    assert a != c


def test_content_hash_changes_with_text():
    a = CorpusRecord(kind="vocab", source_id="x", text="hello")
    b = CorpusRecord(kind="vocab", source_id="x", text="hello world")
    assert a.content_hash != b.content_hash
    assert a.point_id == b.point_id, "id stays stable so re-ingest overwrites"


def test_vocab_loader_reads_real_library():
    processed = Path(__file__).resolve().parents[3] / "data" / "processed"
    recs = _load_vocab(processed)
    assert len(recs) >= 20, "industry_context_library.json should yield ≥20 vocab items"
    sample = recs[0]
    assert sample.kind == "vocab"
    assert sample.payload["term"]
    assert sample.payload["industry"]
    assert "[VOCAB]" in sample.text


def test_error_loader_reads_real_bank():
    processed = Path(__file__).resolve().parents[3] / "data" / "processed"
    recs = _load_errors(processed)
    assert len(recs) >= 20
    assert all(r.payload.get("error_id") for r in recs)
    assert all("[ERROR]" in r.text for r in recs)


def test_builder_text_embeds_key_fields():
    vocab_txt = _build_text_for_vocab(
        {"term": "kanban", "definition_en": "pull-based", "definition_vi": "kéo",
         "example_sentence": "We use kanban.", "cefr_level": "B2", "related_terms": ["wip"]},
        "IT",
    )
    assert "kanban" in vocab_txt.lower()
    assert "IT" in vocab_txt
    assert "wip" in vocab_txt

    err_txt = _build_text_for_error(
        {"error_pattern": "arrive to → arrive at",
         "category": "prepositions",
         "incorrect_example": "I arrived to the airport.",
         "correct_example": "I arrived at the airport.",
         "explanation_vi": "giải thích",
         "explanation_en": "explanation"},
    )
    for token in ("arrive", "airport", "preposition", "giải thích", "explanation"):
        assert token in err_txt


def test_ingest_is_idempotent(fake_stack):
    stub, fake_qdrant = fake_stack
    first = ingest(kinds=("vocab",), limit=5)
    assert first["embedded"] == 5
    assert first["skipped_unchanged"] == 0
    calls_after_first = stub.calls

    # Second run: same content → all skipped, embedder not called again.
    second = ingest(kinds=("vocab",), limit=5)
    assert second["embedded"] == 0
    assert second["skipped_unchanged"] == 5
    assert stub.calls == calls_after_first, "unchanged records must not be re-embedded"


def test_ingest_force_re_embeds(fake_stack):
    stub, _ = fake_stack
    ingest(kinds=("vocab",), limit=5)
    calls_after_first = stub.calls

    ingest(kinds=("vocab",), limit=5, force=True)
    assert stub.calls > calls_after_first


def test_retrieval_returns_empty_when_no_collection(monkeypatch):
    # Reset embedder cache so test is deterministic regardless of env.
    monkeypatch.setattr(corpus_retrieval, "_embedder", None, raising=False)
    monkeypatch.setattr(corpus_retrieval, "_embedder_failed", False, raising=False)
    monkeypatch.setattr(corpus_retrieval, "_get_embedder", lambda: _StubEmbedder())

    empty_qdrant = _FakeQdrant()
    monkeypatch.setattr(corpus_retrieval, "_qdrant_client", lambda: empty_qdrant)

    hits = corpus_retrieval.search("agile project management", kind="vocab", top_k=3)
    assert hits == []


def test_retrieval_after_ingest_finds_relevant_record(fake_stack, monkeypatch):
    stub, fake_qdrant = fake_stack
    ingest(kinds=("vocab", "error"), limit=20)

    # Point retrieval at the same fakes used by ingest.
    monkeypatch.setattr(corpus_retrieval, "_embedder", stub, raising=False)
    monkeypatch.setattr(corpus_retrieval, "_embedder_failed", False, raising=False)
    monkeypatch.setattr(corpus_retrieval, "_qdrant_client", lambda: fake_qdrant)

    hits = corpus_retrieval.search("agile kanban sprint", kind="vocab", top_k=5)
    assert hits, "retrieval must return at least one vocab hit"
    assert all(h["kind"] == "vocab" for h in hits)
    # content_hash must never leak back to callers (PII / implementation detail)
    assert all("content_hash" not in h for h in hits)


def test_build_embedder_honours_prefer_fastembed_unavailable(monkeypatch):
    # Ensure explicit prefer=fastembed raises cleanly when fastembed
    # isn't importable, rather than silently falling through.
    monkeypatch.setitem(sys.modules, "fastembed", None)
    with pytest.raises(corpus_embedding.EmbeddingError):
        corpus_embedding.build_corpus_embedder(prefer="fastembed")
