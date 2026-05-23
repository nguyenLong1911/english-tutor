"""Mem0 wrapper for user-scoped semantic memory.

Mem0 is loaded lazily so the API can boot even when the qdrant container or
OpenAI key is unavailable in dev. Calls then fall back to a no-op in-memory
stub which is good enough for Sprint 1 mock flows.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Optional

from .config import get_settings

logger = logging.getLogger(__name__)
_SLOW_MEM0_OPERATION_MS = int(os.getenv("SLOW_MEM0_OPERATION_MS", "400"))


class MemoryTemporarilyUnavailable(RuntimeError):
    """Raised when the real Mem0 provider is temporarily unavailable."""


def _is_transient_mem0_error(exc: Exception) -> bool:
    text = repr(exc).lower()
    return any(
        marker in text
        for marker in (
            "429",
            "resource_exhausted",
            "quota",
            "rate limit",
            "ratelimit",
            "temporarily unavailable",
            "deadline exceeded",
            "timeout",
            "503",
        )
    )


def _prefer_vertex_google() -> bool:
    settings = get_settings()
    env_flag = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").strip().lower() in {"1", "true", "yes", "on"}
    return env_flag or bool(settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.startswith("AQ."))


def _patch_mem0_gemini_clients() -> None:
    """Force Mem0's Gemini clients onto Vertex AI ``v1`` by default.

    Mem0's Gemini wrappers instantiate ``genai.Client(api_key=...)`` without
    explicitly setting ``vertexai=True``. With a Vertex Express ``AQ.…`` key
    that can silently route embedding calls to the legacy Gemini Developer
    API instead of Vertex's publisher-model endpoint, which returns
    ``API_KEY_SERVICE_BLOCKED`` for embeddings. We patch both the embedder and
    LLM client constructors to opt into Vertex whenever this project's Google
    credential shape indicates Vertex should be the default.
    """
    try:
        from mem0.embeddings import gemini as _mem0_emb  # type: ignore
        from mem0.llms import gemini as _mem0_llm  # type: ignore
        from google import genai  # type: ignore
        from google.genai import types as _genai_types  # type: ignore
    except Exception:  # noqa: BLE001 — packages optional at import time
        return

    if _prefer_vertex_google():
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")

    def _rebind_client(target_cls: Any, label: str) -> None:
        if getattr(target_cls, "_a20_v1_patched", False):
            return
        _orig_init = target_cls.__init__

        def _patched_init(self: Any, config: Any = None) -> None:  # type: ignore[no-untyped-def]
            _orig_init(self, config)
            api_key = getattr(self.config, "api_key", None)
            use_vertex = _prefer_vertex_google()
            try:
                client_kwargs: dict[str, Any] = {
                    "api_key": api_key,
                    "http_options": _genai_types.HttpOptions(api_version="v1"),
                }
                if use_vertex:
                    client_kwargs["vertexai"] = True
                self.client = genai.Client(**client_kwargs)
            except Exception as exc:  # noqa: BLE001 — defensive: keep original client
                logger.warning("a20: could not re-bind Mem0 %s client to v1: %s", label, exc)

        target_cls.__init__ = _patched_init  # type: ignore[assignment]
        target_cls._a20_v1_patched = True  # type: ignore[attr-defined]
        logger.info("a20: patched mem0 %s to prefer Vertex v1 endpoint", label)

    _rebind_client(_mem0_emb.GoogleGenAIEmbedding, "GoogleGenAIEmbedding")
    _rebind_client(_mem0_llm.GeminiLLM, "GeminiLLM")


_patch_mem0_gemini_clients()


class _StubMemory:
    """In-process fallback when Mem0/Qdrant aren't reachable."""

    def __init__(self) -> None:
        self._store: dict[str, list[dict[str, Any]]] = {}

    def add(self, content: str, user_id: str, metadata: dict | None = None) -> dict:
        item = {"content": content, "metadata": metadata or {}}
        self._store.setdefault(user_id, []).append(item)
        return {"id": str(len(self._store[user_id])), **item}

    def search(self, query: str, user_id: str, limit: int = 10) -> list[dict]:
        items = self._store.get(user_id, [])
        q = query.lower()
        scored = [it for it in items if q in it["content"].lower()] or items
        return scored[:limit]

    def delete_all(self, user_id: str) -> None:
        self._store.pop(user_id, None)


class MemoryManager:
    def __init__(self) -> None:
        self._settings = get_settings()
        self._client: Any = None
        self._using_stub = False
        self._provider_chain: list[tuple[str, dict[str, Any]]] = self._build_provider_chain()
        self._provider_index = -1
        self._degraded_until: datetime | None = None
        self._degraded_reason: str | None = None
        self._last_successful_add_at: datetime | None = None
        self._last_successful_search_at: datetime | None = None

    def _base_mem0_config(self) -> dict[str, Any]:
        # When running against Vertex AI (Express Mode), the embedder needs the
        # Vertex ``AQ.…`` key, not the AI-Studio ``AIza…`` key. ``GOOGLE_API_KEY``
        # by convention holds the Vertex key in this project; fall back to
        # ``GEMINI_API_KEY`` for plain AI-Studio setups.
        use_vertex = _prefer_vertex_google()
        if use_vertex and self._settings.GOOGLE_API_KEY:
            embedder_key = self._settings.GOOGLE_API_KEY
        else:
            embedder_key = self._settings.GEMINI_API_KEY or self._settings.GOOGLE_API_KEY

        return {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": self._settings.QDRANT_URL,
                    "collection_name": self._settings.QDRANT_COLLECTION,
                },
            },
            "embedder": {
                "provider": "gemini",
                "config": {
                    "api_key": embedder_key,
                    "model": self._settings.EMBEDDING_MODEL,
                    "embedding_dims": 1536,
                },
            },
        }

    def _openai_fallback_config(self) -> dict[str, Any]:
        return {
            "vector_store": {
                "provider": "qdrant",
                "config": {
                    "url": self._settings.QDRANT_URL,
                    "collection_name": self._settings.QDRANT_COLLECTION,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "api_key": self._settings.OPENAI_API_KEY,
                    "model": self._settings.OPENAI_EMBEDDING_MODEL,
                    "embedding_dims": 1536,
                    "output_dimensionality": 1536,
                },
            },
        }

    def _llm_block(self) -> dict[str, Any]:
        """Pick the best available LLM provider for Mem0 fact extraction.

        Priority: Gemini > Groq > OpenAI. Mem0 sends *long* extraction prompts
        (full conversation context + system prompt) which routinely exceed
        Groq's free-tier 6K-tokens-per-minute limit and trip 413 rate-limit
        errors. Gemini Flash free tier allows ~1M TPM and accepts much larger
        contexts, so it's the safer default here. Groq stays as a fallback
        for short prompts when Gemini quota is exhausted.

        Note: this is independent from the LLM used by the chat pipeline
        (`utils.llm.get_llm_client`) which still prefers Groq for low latency
        on short user-facing turns.
        """
        if self._settings.GEMINI_API_KEY or self._settings.GOOGLE_API_KEY:
            use_vertex = _prefer_vertex_google()
            llm_key = self._settings.GOOGLE_API_KEY if use_vertex else (
                self._settings.GEMINI_API_KEY or self._settings.GOOGLE_API_KEY
            )
            return {
                "provider": "gemini",
                "config": {
                    "api_key": llm_key,
                    "model": self._settings.LLM_MODEL,
                },
            }
        if self._settings.GROQ_API_KEY:
            return {
                "provider": "groq",
                "config": {
                    "api_key": self._settings.GROQ_API_KEY,
                    "model": self._settings.GROQ_MODEL,
                },
            }
        if self._settings.OPENAI_API_KEY:
            return {
                "provider": "openai",
                "config": {"api_key": self._settings.OPENAI_API_KEY, "model": "gpt-4o-mini"},
            }
        return {}

    def _build_provider_chain(self) -> list[tuple[str, dict[str, Any]]]:
        """Build an embedder→full-config chain.

        Mem0 requires a working embedder (vector store needs vectors). Groq does
        not expose embeddings, so Groq-only deployments fall through to the
        in-memory stub. Set GEMINI_API_KEY or OPENAI_API_KEY to enable real
        Mem0 persistence on the local Qdrant.
        """
        providers: list[tuple[str, dict[str, Any]]] = []
        llm_block = self._llm_block()
        if not llm_block:
            return providers

        if self._settings.GEMINI_API_KEY:
            cfg = self._base_mem0_config()
            cfg["llm"] = llm_block
            providers.append(("gemini", cfg))

        if self._settings.OPENAI_API_KEY:
            cfg = self._openai_fallback_config()
            cfg["llm"] = llm_block
            providers.append(("openai", cfg))

        return providers

    def _activate_provider(self, index: int) -> None:
        from mem0 import Memory  # type: ignore

        provider_name, provider_config = self._provider_chain[index]
        started_at = time.perf_counter()
        client = Memory.from_config(provider_config)
        # Probe one round-trip so a bad embedder/model surfaces NOW instead
        # of at the first user chat turn (which would silently demote the
        # whole memory layer to the in-memory stub — see the post-mortem in
        # docs/evaluation/mem0_benchmark.md for what that looks like).
        probe_user = "__mem0_probe__"
        try:
            client.add("ping", user_id=probe_user, metadata={"probe": True})
        finally:
            try:
                client.delete_all(user_id=probe_user)
            except Exception:  # noqa: BLE001 — best-effort cleanup
                pass
        self._client = client
        self._provider_index = index
        self._using_stub = False
        self._degraded_until = None
        self._degraded_reason = None
        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
        logger.info("Mem0 initialized with provider=%s init_ms=%.1f", provider_name, duration_ms)

    def _fallback_to_stub(self, reason: str) -> None:
        logger.warning("%s; using in-memory stub", reason)
        self._client = _StubMemory()
        self._using_stub = True
        self._provider_index = -1
        self._degraded_until = None
        self._degraded_reason = reason

    def _mark_degraded(self, reason: str) -> None:
        seconds = max(1, int(self._settings.MEMORY_CIRCUIT_BREAKER_SECONDS))
        self._degraded_until = datetime.utcnow() + timedelta(seconds=seconds)
        self._degraded_reason = reason[:500]
        logger.warning("Mem0 temporarily degraded for %ss: %s", seconds, self._degraded_reason)

    @property
    def is_degraded(self) -> bool:
        if self._degraded_until is None:
            return False
        if datetime.utcnow() >= self._degraded_until:
            self._degraded_until = None
            self._degraded_reason = None
            return False
        return True

    @property
    def provider_name(self) -> str | None:
        if self._using_stub:
            return "stub"
        if 0 <= self._provider_index < len(self._provider_chain):
            return self._provider_chain[self._provider_index][0]
        return None

    def status(self) -> dict[str, Any]:
        degraded = self.is_degraded
        return {
            "provider": self.provider_name,
            "using_stub": self._using_stub,
            "degraded": degraded,
            "degraded_reason": self._degraded_reason if degraded else None,
            "degraded_until": self._degraded_until.isoformat() if degraded and self._degraded_until else None,
            "provider_index": self._provider_index,
            "providers_configured": [name for name, _ in self._provider_chain],
            "last_successful_add_at": self._last_successful_add_at.isoformat() if self._last_successful_add_at else None,
            "last_successful_search_at": self._last_successful_search_at.isoformat() if self._last_successful_search_at else None,
        }

    def _move_to_next_provider(self, exc: Exception) -> bool:
        next_index = self._provider_index + 1
        while next_index < len(self._provider_chain):
            provider_name, _ = self._provider_chain[next_index]
            try:
                self._activate_provider(next_index)
                logger.warning("Mem0 provider failed (%s); switched to provider=%s", exc, provider_name)
                return True
            except Exception as next_exc:  # pragma: no cover - provider-specific import/runtime fallback
                logger.warning("Mem0 provider init failed for provider=%s: %s", provider_name, next_exc)
                next_index += 1
        self._fallback_to_stub(f"Mem0 provider chain exhausted after error: {exc}")
        return False

    def _ensure_client(self) -> None:
        if self._client is not None:
            return
        if self.is_degraded:
            return
        if not self._provider_chain:
            logger.info("Mem0 disabled because no OpenAI embedding key is configured; using in-memory stub")
            self._client = _StubMemory()
            self._using_stub = True
            self._provider_index = -1
            return
        try:
            self._activate_provider(0)
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            logger.warning("Mem0 provider init failed for provider=%s: %s", self._provider_chain[0][0], exc)
            if _is_transient_mem0_error(exc):
                self._mark_degraded(f"Mem0 provider init temporarily failed: {exc}")
                return
            self._fallback_to_stub(f"Mem0 provider chain exhausted after error: {exc}")

    def _switch_to_stub(self, exc: Exception) -> None:
        self._fallback_to_stub(f"Mem0 request failed: {exc}")

    @property
    def using_stub(self) -> bool:
        return self._using_stub

    def warmup(self) -> None:
        """Resolve the backing client before the first user request.

        This only initializes the client. It intentionally avoids a probe call
        so startup does not trigger an embedding request or force a stub
        fallback before the first real chat turn.
        """
        self._ensure_client()

    def add_memory(self, user_id: str, content: str, metadata: Optional[dict] = None):
        self._ensure_client()
        if self.is_degraded:
            raise MemoryTemporarilyUnavailable(self._degraded_reason or "Mem0 is temporarily degraded")
        if self._client is None:
            raise MemoryTemporarilyUnavailable("Mem0 client is not initialized")
        started_at = time.perf_counter()
        try:
            if self._using_stub:
                result = self._client.add(content=content, user_id=user_id, metadata=metadata)
            else:
                result = self._client.add(
                messages=[{"role": "user", "content": content}],
                user_id=user_id,
                metadata=metadata or {},
            )
            self._log_operation("add_memory", user_id=user_id, started_at=started_at, extra={"using_stub": self._using_stub})
            if not self._using_stub:
                self._last_successful_add_at = datetime.utcnow()
            return result
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            if _is_transient_mem0_error(exc):
                self._mark_degraded(f"Mem0 add failed transiently: {exc}")
                raise MemoryTemporarilyUnavailable(str(exc)) from exc
            if self._move_to_next_provider(exc):
                return self.add_memory(user_id=user_id, content=content, metadata=metadata)
            self._switch_to_stub(exc)
            result = self._client.add(content=content, user_id=user_id, metadata=metadata)
            self._log_operation("add_memory", user_id=user_id, started_at=started_at, extra={"using_stub": True, "fallback": True})
            return result

    def _search_real(self, user_id: str, query: str, limit: int) -> list[dict]:
        """Mem0 ≥0.1.x changed `search` to require `filters=` instead of
        passing `user_id` at the top level. Try the new shape first and fall
        back to the older keyword for forward/backward compatibility.
        """
        try:
            return self._client.search(
                query=query,
                limit=limit,
                filters={"user_id": user_id},
            )
        except TypeError:
            # Old mem0 versions don't accept `filters=`; use the legacy kwarg.
            return self._client.search(query=query, user_id=user_id, limit=limit)

    def search_memory(self, user_id: str, query: str, limit: int = 10) -> list[dict]:
        self._ensure_client()
        if self.is_degraded:
            logger.warning("Mem0 search skipped while degraded user_id=%s reason=%s", user_id, self._degraded_reason)
            return []
        if self._client is None:
            logger.warning("Mem0 search skipped because client is not initialized user_id=%s", user_id)
            return []
        started_at = time.perf_counter()
        try:
            if self._using_stub:
                result = self._client.search(query=query, user_id=user_id, limit=limit)
                self._log_operation("search_memory", user_id=user_id, started_at=started_at, extra={"limit": limit, "hits": len(result), "using_stub": True})
                return result
            result = self._search_real(user_id, query, limit)
            # mem0 may return dict {"results": [...]} or a plain list depending on version
            if isinstance(result, dict):
                results = result.get("results", [])
            else:
                results = result or []
            self._log_operation("search_memory", user_id=user_id, started_at=started_at, extra={"limit": limit, "hits": len(results), "using_stub": False})
            self._last_successful_search_at = datetime.utcnow()
            return results
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            if _is_transient_mem0_error(exc):
                self._mark_degraded(f"Mem0 search failed transiently: {exc}")
                return []
            if self._move_to_next_provider(exc):
                return self.search_memory(user_id=user_id, query=query, limit=limit)
            self._switch_to_stub(exc)
            result = self._client.search(query=query, user_id=user_id, limit=limit)
            self._log_operation("search_memory", user_id=user_id, started_at=started_at, extra={"limit": limit, "hits": len(result), "using_stub": True, "fallback": True})
            return result

    def delete_user_memory(self, user_id: str) -> None:
        self._ensure_client()
        started_at = time.perf_counter()
        try:
            if self._using_stub:
                self._client.delete_all(user_id=user_id)
            else:
                self._client.delete_all(user_id=user_id)
            self._log_operation("delete_user_memory", user_id=user_id, started_at=started_at, extra={"using_stub": self._using_stub})
        except Exception as exc:  # pragma: no cover - defensive runtime fallback
            if self._move_to_next_provider(exc):
                self.delete_user_memory(user_id=user_id)
                return
            self._switch_to_stub(exc)
            self._client.delete_all(user_id=user_id)
            self._log_operation("delete_user_memory", user_id=user_id, started_at=started_at, extra={"using_stub": True, "fallback": True})

    def _log_operation(
        self,
        operation: str,
        *,
        user_id: str,
        started_at: float,
        extra: dict[str, Any] | None = None,
    ) -> None:
        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
        payload = {
            "operation": operation,
            "user_id": user_id,
            "duration_ms": duration_ms,
            "provider_index": self._provider_index,
            **(extra or {}),
        }
        if duration_ms >= _SLOW_MEM0_OPERATION_MS:
            logger.warning("mem0.slow_operation %s", payload)
        else:
            logger.debug("mem0.operation %s", payload)


_memory_manager: Optional[MemoryManager] = None


def get_memory() -> MemoryManager:
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = MemoryManager()
    return _memory_manager
