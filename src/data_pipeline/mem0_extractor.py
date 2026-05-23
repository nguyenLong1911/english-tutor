"""Mem0 long-term memory extractor with custom instructions.

Wraps the ``mem0`` SDK (when available) and a stub fallback so the rest of
the pipeline can run in environments without the dependency installed.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .env import load_pipeline_env

log = logging.getLogger(__name__)


CUSTOM_INSTRUCTIONS = (
    "You are a memory extraction assistant for a Vietnamese-English ESL "
    "grammar error dataset. Your sole task is to extract domain-specific "
    "linguistic facts, including:\n"
    "1. Systematic grammar error patterns made by Vietnamese learners "
    "(e.g., tense confusion, copula insertion/omission, adverb misplacement).\n"
    "2. Valid linguistic explanations linking errors to L1 Vietnamese transfer.\n"
    "3. Correct English equivalents and CEFR level estimations.\n"
    "Ignore casual chatter, user meta-information, and non-linguistic data. "
    "Always return facts as a structured JSON object with a single 'facts' array."
)


@dataclass
class Mem0Extractor:
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    custom_instructions: str = CUSTOM_INSTRUCTIONS
    _impl: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        load_pipeline_env()
        self.api_key = self.api_key or os.getenv("OPENAI_API_KEY")
        self._impl = self._init_backend()

    # ------------------------------------------------------------------
    def _init_backend(self):
        try:
            from mem0 import Memory  # type: ignore
        except Exception:
            log.warning("mem0 SDK unavailable; using stub backend.")
            return None

        config: Dict[str, Any] = {
            "llm": {
                "provider": self.provider,
                "config": {
                    "model": self.model,
                    "api_key": self.api_key,
                    "temperature": 0.2,
                    "max_tokens": 2000,
                },
            },
            "custom_instructions": self.custom_instructions,
        }
        if self.base_url:
            config["llm"]["config"]["openai_base_url"] = self.base_url
        return Memory.from_config(config)

    # ----------------------------------------------------- public methods
    def add(self, content: str, *, user_id: str, metadata: Optional[dict] = None) -> Any:
        if self._impl is None:
            log.debug("[mem0-stub] add: %s for %s", content[:80], user_id)
            return {"id": None, "stub": True}
        return self._impl.add(content, user_id=user_id, metadata=metadata or {})

    def search(self, query: str, *, user_id: str, limit: int = 5) -> List[dict]:
        if self._impl is None:
            return []
        return self._impl.search(query=query, user_id=user_id, limit=limit)
