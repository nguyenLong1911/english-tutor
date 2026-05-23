"""File-based checkpoint utility for incremental data-prep runs.

Implements the guide's recommendations from
§ "Trí nhớ Ngắn hạn và Quản lý Điểm kiểm soát Phiên" and
§ "phiên chạy lũy tiến (incremental runs)":

* Atomic JSON writes (write to ``*.tmp`` then ``os.replace``).
* Tracks ``visited`` / ``unvisited`` URL queues so that repeated runs do not
  re-scrape pages and the agent can resume after a crash at the *last*
  successful step rather than from scratch.
* Records ``last_step`` + arbitrary ``metrics`` so an orchestrator can decide
  whether to skip / replay / advance.

The format is intentionally a flat JSON dict so it is human-inspectable and
trivial to diff in code review.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

log = logging.getLogger(__name__)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class CheckpointState:
    """Serializable checkpoint payload."""

    run_id: str = ""
    last_step: str = ""
    visited: List[str] = field(default_factory=list)
    unvisited: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    updated_at: str = field(default_factory=_utcnow_iso)


@dataclass
class Checkpoint:
    """Atomic, thread-safe checkpoint persisted as JSON.

    Typical use::

        ckpt = Checkpoint(Path("data/processed/_ckpt_jfleg.json")).load()
        for url in ckpt.pending(seed_urls):
            try:
                process(url)
                ckpt.mark_visited(url, step="extract")
            except Exception:
                ckpt.save()  # flush partial progress
                raise
    """

    path: Path
    state: CheckpointState = field(default_factory=CheckpointState)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    # ------------------------------------------------------------------ I/O
    def load(self) -> "Checkpoint":
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self.state = CheckpointState(**payload)
            except Exception as exc:
                log.warning("Checkpoint %s corrupt (%s); starting fresh", self.path, exc)
                self.state = CheckpointState()
        return self

    def save(self) -> None:
        with self._lock:
            self.state.updated_at = _utcnow_iso()
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Atomic write: tmp → fsync → os.replace.
            fd, tmp = tempfile.mkstemp(
                prefix=self.path.name + ".",
                suffix=".tmp",
                dir=str(self.path.parent),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(asdict(self.state), f, ensure_ascii=False, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, self.path)
            except Exception:
                if os.path.exists(tmp):
                    os.unlink(tmp)
                raise

    # --------------------------------------------------------- queue helpers
    def pending(self, all_urls: Iterable[str]) -> List[str]:
        """Return URLs not yet visited (preserves input order)."""
        seen = set(self.state.visited)
        return [u for u in all_urls if u not in seen]

    def mark_visited(self, url: str, *, step: str = "", flush: bool = True) -> None:
        with self._lock:
            if url not in self.state.visited:
                self.state.visited.append(url)
            if url in self.state.unvisited:
                self.state.unvisited.remove(url)
            if step:
                self.state.last_step = step
        if flush:
            self.save()

    def enqueue(self, urls: Iterable[str]) -> None:
        with self._lock:
            seen = set(self.state.visited) | set(self.state.unvisited)
            for u in urls:
                if u not in seen:
                    self.state.unvisited.append(u)
                    seen.add(u)

    def update_metrics(self, **kwargs: Any) -> None:
        with self._lock:
            self.state.metrics.update(kwargs)

    # ------------------------------------------------------------- info
    def __len__(self) -> int:
        return len(self.state.visited)

    @property
    def is_empty(self) -> bool:
        return not self.state.visited and not self.state.unvisited
