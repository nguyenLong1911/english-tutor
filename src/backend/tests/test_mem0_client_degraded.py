from __future__ import annotations

from app.core.mem0_client import MemoryManager, MemoryTemporarilyUnavailable


class _QuotaMemoryManager(MemoryManager):
    def _build_provider_chain(self):  # type: ignore[override]
        return [("vertex", {})]

    def _activate_provider(self, index: int) -> None:  # type: ignore[override]
        self._client = object()
        self._provider_index = index
        self._using_stub = False

    def _search_real(self, user_id: str, query: str, limit: int):  # type: ignore[override]
        raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")


def test_search_quota_marks_degraded_without_switching_to_stub():
    manager = _QuotaMemoryManager()

    assert manager.search_memory("user-1", "hello", limit=3) == []

    status = manager.status()
    assert status["degraded"] is True
    assert status["using_stub"] is False
    assert status["provider"] == "vertex"


def test_add_while_degraded_raises_temporary_unavailable_not_stub():
    manager = _QuotaMemoryManager()
    manager.search_memory("user-1", "hello", limit=3)

    try:
        manager.add_memory("user-1", "content", {"fact_type": "goal"})
    except MemoryTemporarilyUnavailable:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected temporary unavailable")

    assert manager.status()["using_stub"] is False
