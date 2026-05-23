"""Embedding adapter for the static corpus (vocabulary / errors / prompts / ielts).

Design goals
------------
* **Provider-agnostic.** Pick the best available backend at runtime from
  ``Settings``: Vertex AI Express (v1 + API key), OpenAI, or a fastembed
  local model. Failure to import a backend must never crash the app — the
  caller decides whether to abort ingestion or fall back.
* **Batch-friendly.** Ingestion sends thousands of short strings; caller
  controls batch size. Each backend implements ``embed_batch`` so we can
  fan out a single HTTP call per batch when the provider supports it.
* **Rate-limit aware.** Vertex AI Express caps
  ``online_prediction_requests_per_base_model`` at a low per-minute bound
  (see docs/evaluation/mem0_benchmark.md). The adapter exposes
  ``min_interval_s`` so the CLI can pace itself; on 429 it sleeps and
  retries with exponential backoff rather than abandoning the run.

The adapter is **only** used by the corpus ingestion + retrieval path —
Mem0 has its own embedder wiring inside the Mem0 SDK, and the two must
stay independent so a breakage on one side doesn't take the other down.
"""
from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

logger = logging.getLogger(__name__)


class EmbeddingError(RuntimeError):
    """Non-retriable embedding failure (bad model, bad key, malformed input)."""


class EmbeddingRateLimited(RuntimeError):
    """Provider returned 429 / RESOURCE_EXHAUSTED. Caller should back off."""


@dataclass
class EmbedderInfo:
    provider: str
    model: str
    dim: int
    # Conservative pacing hint for batch loops. ``0.0`` = no throttle.
    min_interval_s: float = 0.0


class CorpusEmbedder(ABC):
    info: EmbedderInfo

    @abstractmethod
    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Return one vector per input string, in order."""


# --------------------------------------------------------------------------- #
# Vertex AI Express (REST /v1/publishers/google/models/{id}:predict)          #
# --------------------------------------------------------------------------- #


class VertexCorpusEmbedder(CorpusEmbedder):
    """Vertex AI Express embedder using the ``AQ.…`` API key.

    Avoids the ``google-genai`` SDK deliberately: the SDK defaults to
    ``v1beta1`` under Vertex routing which rejects API-key auth (see
    ``app/core/mem0_client.py::_patch_mem0_gemini_clients`` for the
    companion Mem0 fix). Hitting ``v1`` REST directly keeps us pinned
    to the working endpoint.
    """

    def __init__(
        self,
        api_key: str,
        project: str,
        location: str = "us-central1",
        model: str = "gemini-embedding-001",
        output_dim: int = 1536,
    ) -> None:
        if not api_key or not project:
            raise EmbeddingError("VertexCorpusEmbedder requires api_key and project")
        self._api_key = api_key
        self._project = project
        # "global" is a valid GOOGLE_CLOUD_LOCATION but has no
        # ``{loc}-aiplatform.googleapis.com`` host; collapse to
        # us-central1 which is the implicit Express target.
        self._location = location if location and location != "global" else "us-central1"
        self._model = model
        self._output_dim = output_dim
        self.info = EmbedderInfo(
            provider="vertex",
            model=model,
            dim=output_dim,
            # Vertex Express caps embeddings at a few RPM; 12 s/item keeps
            # single-replica ingestion under the per-minute quota with
            # headroom for retry budget.
            min_interval_s=float(os.getenv("CORPUS_VERTEX_MIN_INTERVAL_S", "12.0")),
        )
        self._host = f"https://{self._location}-aiplatform.googleapis.com"
        self._path = (
            f"v1/projects/{self._project}/locations/{self._location}"
            f"/publishers/google/models/{self._model}:predict"
        )

    def _post(self, text: str) -> list[float]:
        import httpx  # local import to keep module cheap to load

        payload: dict = {
            "instances": [{"content": text, "task_type": "RETRIEVAL_DOCUMENT"}],
        }
        if self._model.startswith("gemini-embedding"):
            payload["parameters"] = {"outputDimensionality": self._output_dim}

        url = f"{self._host}/{self._path}"
        with httpx.Client(timeout=30) as http:
            resp = http.post(url, params={"key": self._api_key}, json=payload)

        if resp.status_code == 429:
            raise EmbeddingRateLimited(resp.text[:200])
        if resp.status_code != 200:
            raise EmbeddingError(f"Vertex embed HTTP {resp.status_code}: {resp.text[:200]}")

        preds = resp.json().get("predictions") or []
        if not preds:
            raise EmbeddingError("Vertex embed returned no predictions")
        emb = preds[0].get("embeddings") or preds[0].get("embedding") or {}
        values = emb.get("values")
        if not values:
            raise EmbeddingError("Vertex embed response missing values")
        return list(values)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for text in texts:
            out.append(self._post(text))
            if self.info.min_interval_s > 0:
                time.sleep(self.info.min_interval_s)
        return out


# --------------------------------------------------------------------------- #
# OpenAI ``text-embedding-3-*``                                               #
# --------------------------------------------------------------------------- #


class OpenAICorpusEmbedder(CorpusEmbedder):
    """OpenAI embedder. Batch-native; generous quota at alpha scale."""

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        output_dim: int = 1536,
    ) -> None:
        if not api_key:
            raise EmbeddingError("OpenAICorpusEmbedder requires api_key")
        try:
            from openai import OpenAI  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise EmbeddingError(f"openai package not installed: {exc}") from exc
        self._client = OpenAI(api_key=api_key)
        self._model = model
        self._output_dim = output_dim
        self.info = EmbedderInfo(provider="openai", model=model, dim=output_dim, min_interval_s=0.0)

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            resp = self._client.embeddings.create(
                model=self._model,
                input=list(texts),
                dimensions=self._output_dim,
            )
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            if "rate" in msg.lower() or "429" in msg:
                raise EmbeddingRateLimited(msg) from exc
            raise EmbeddingError(msg) from exc
        return [d.embedding for d in resp.data]


# --------------------------------------------------------------------------- #
# Local fastembed fallback (no key, no network)                               #
# --------------------------------------------------------------------------- #


class FastembedCorpusEmbedder(CorpusEmbedder):
    """Local sentence-transformers via fastembed.

    Default model ``BAAI/bge-small-en-v1.5`` is 384-dim. We right-pad to
    ``output_dim`` (typically 1536) so a single Qdrant collection can
    accept vectors from any backend without reindexing — retrieval
    quality on zero-padded dims is preserved under cosine distance
    because the extra dims contribute zero to the dot product.
    """

    def __init__(
        self,
        model: str = "BAAI/bge-small-en-v1.5",
        output_dim: int = 1536,
    ) -> None:
        try:
            from fastembed import TextEmbedding  # type: ignore
        except Exception as exc:  # pragma: no cover - optional dep
            raise EmbeddingError(f"fastembed not installed: {exc}") from exc
        self._model_name = model
        self._output_dim = output_dim
        self._client = TextEmbedding(model_name=model)
        # Probe native dim so we know how much padding to apply.
        probe = next(iter(self._client.embed(["probe"])))
        self._native_dim = len(probe)
        self.info = EmbedderInfo(
            provider="fastembed",
            model=model,
            dim=output_dim,
            min_interval_s=0.0,
        )

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        raw = list(self._client.embed(list(texts)))
        pad = self._output_dim - self._native_dim
        if pad < 0:
            return [list(v[: self._output_dim]) for v in raw]
        if pad == 0:
            return [list(v) for v in raw]
        return [list(v) + [0.0] * pad for v in raw]


# --------------------------------------------------------------------------- #
# Factory                                                                     #
# --------------------------------------------------------------------------- #


def build_corpus_embedder(
    settings=None,
    *,
    prefer: str | None = None,
) -> CorpusEmbedder:
    """Return the best available ``CorpusEmbedder``.

    Selection order:
    1. Explicit ``prefer`` argument (``vertex`` / ``openai`` / ``fastembed``).
    2. ``CORPUS_EMBEDDER`` env var (same values).
    3. Auto: ``openai`` if ``OPENAI_API_KEY`` set, else ``vertex`` if
       Vertex Express creds present, else ``fastembed`` if importable,
       else raise.

    The ``output_dim`` is pinned to 1536 to match the Qdrant ``corpus``
    collection. Override via ``CORPUS_EMBEDDING_DIM`` if you recreate the
    collection at a different dim.
    """
    from ..core.config import get_settings as _get_settings

    s = settings or _get_settings()
    dim = int(os.getenv("CORPUS_EMBEDDING_DIM", "1536"))
    explicit = (prefer or os.getenv("CORPUS_EMBEDDER") or "").lower().strip() or None

    def _try_openai() -> CorpusEmbedder | None:
        if not s.OPENAI_API_KEY:
            return None
        return OpenAICorpusEmbedder(
            api_key=s.OPENAI_API_KEY,
            model=s.OPENAI_EMBEDDING_MODEL,
            output_dim=dim,
        )

    def _try_vertex() -> CorpusEmbedder | None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "")
        if not (s.GOOGLE_API_KEY and project):
            return None
        return VertexCorpusEmbedder(
            api_key=s.GOOGLE_API_KEY,
            project=project,
            location=os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1"),
            model="gemini-embedding-001",
            output_dim=dim,
        )

    def _try_fastembed() -> CorpusEmbedder | None:
        try:
            return FastembedCorpusEmbedder(output_dim=dim)
        except EmbeddingError:
            return None

    if explicit == "openai":
        emb = _try_openai()
    elif explicit == "vertex":
        emb = _try_vertex()
    elif explicit == "fastembed":
        emb = _try_fastembed()
    else:
        emb = _try_openai() or _try_vertex() or _try_fastembed()

    if emb is None:
        raise EmbeddingError(
            "No corpus embedder available: set OPENAI_API_KEY, or Vertex "
            "(GOOGLE_API_KEY + GOOGLE_CLOUD_PROJECT), or install fastembed."
        )
    logger.info(
        "corpus embedder selected: provider=%s model=%s dim=%s min_interval_s=%s",
        emb.info.provider,
        emb.info.model,
        emb.info.dim,
        emb.info.min_interval_s,
    )
    return emb
