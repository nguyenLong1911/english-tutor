"""Mem0 compaction worker (N-05).

Policy: cap 2.000 facts per user. When exceeded, decay low-importance
facts and merge duplicates. Current Mem0 SDK doesn't expose bulk delete
by score threshold, so we rely on its Qdrant collection directly when
available; otherwise we log and noop.
"""
from __future__ import annotations

import logging
from typing import Any

from ..core.config import get_settings
from ..core.mem0_client import get_memory

logger = logging.getLogger(__name__)


def compact_user(user_id: str, cap: int | None = None) -> dict[str, Any]:
    settings = get_settings()
    cap = cap or settings.MEM0_USER_FACT_CAP

    mm = get_memory()
    mm.warmup()
    if mm.using_stub:
        logger.debug("memory_compactor: stub backend, skipping user=%s", user_id)
        return {"user_id": user_id, "skipped": True, "reason": "stub"}

    try:
        client = mm._client  # type: ignore[attr-defined]
        # Best-effort: request a large page then trim if Mem0 exposes listing.
        all_fn = getattr(client, "get_all", None)
        if callable(all_fn):
            items = all_fn(user_id=user_id) or []
            items = items.get("results", []) if isinstance(items, dict) else items
        else:
            items = []
        if len(items) <= cap:
            return {"user_id": user_id, "count": len(items), "trimmed": 0}

        # Sort by importance ascending (unknown = 0) then oldest first and
        # delete the bottom overflow.
        def _score(row: dict) -> float:
            md = row.get("metadata") or {}
            return float(md.get("importance_score", 0.0))

        items.sort(key=lambda r: (_score(r), r.get("created_at") or ""))
        overflow = items[: len(items) - cap]
        delete_fn = getattr(client, "delete", None)
        trimmed = 0
        if callable(delete_fn):
            for row in overflow:
                try:
                    delete_fn(memory_id=row.get("id"))
                    trimmed += 1
                except Exception:  # pragma: no cover - per-row resilience
                    logger.exception("memory_compactor: delete failed")
        return {"user_id": user_id, "count": len(items), "trimmed": trimmed}
    except Exception:  # pragma: no cover - defensive
        logger.exception("memory_compactor failed for user=%s", user_id)
        return {"user_id": user_id, "error": True}


def compact_all(db) -> int:
    from ..models.user import User
    from sqlalchemy import select

    user_ids = db.scalars(select(User.user_id)).all()
    for uid in user_ids:
        compact_user(str(uid))
    logger.info("memory_compactor: processed %s users", len(user_ids))
    return len(user_ids)
