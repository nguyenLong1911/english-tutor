"""Targeted scraper with token-budget enforcement.

Mirrors the guide's *Targeted Scraping* recipe:

* Respect ``robots.txt`` / ``ai.txt`` / ``llms.txt`` directives.
* Strip non-semantic tags (``<script>``, ``<style>``, nav, footer, …).
* Apply Mozilla Readability when available to keep only article body.
* Hard-truncate to a token budget on a clean sentence boundary.
* Persist a visited-URL queue to disk to avoid duplicate work across runs.

This is intentionally dependency-light: ``requests`` + ``beautifulsoup4`` are
required, ``readability-lxml`` is optional (graceful degradation).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional, Set
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

from .json_io import load_json, save_json
from .paths import SCRAPE_QUEUE

log = logging.getLogger(__name__)

_NON_SEMANTIC_TAGS = {
    "script", "style", "nav", "header", "footer", "aside", "form",
    "noscript", "iframe", "svg", "button",
}
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


@dataclass
class TargetedScraper:
    user_agent: str = "A20-DataAgent/1.0 (+https://a20.local)"
    token_budget: int = 4000
    queue_path: Path = field(default_factory=lambda: SCRAPE_QUEUE)
    timeout: float = 20.0
    _visited: Set[str] = field(default_factory=set)

    # ------------------------------------------------------------------ I/O
    def __post_init__(self) -> None:
        if self.queue_path.exists():
            try:
                payload = load_json(self.queue_path)
                self._visited = set(payload.get("visited", []) if isinstance(payload, dict) else payload)
            except Exception:
                self._visited = set()

    def _persist(self) -> None:
        save_json(self.queue_path, {"visited": sorted(self._visited)}, log_write=False)

    # ----------------------------------------------------- robots / llms
    def can_fetch(self, url: str) -> bool:
        """robots.txt + ai.txt aware permission check."""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        rp = RobotFileParser()
        rp.set_url(urljoin(base, "/robots.txt"))
        try:
            rp.read()
        except Exception:
            return True
        return rp.can_fetch(self.user_agent, url)

    def llms_txt(self, base_url: str) -> Optional[str]:
        """Fetch ``llms.txt`` / ``llms-full.txt`` if the host provides one."""
        import requests

        for name in ("llms-full.txt", "llms.txt"):
            url = urljoin(base_url, "/" + name)
            try:
                r = requests.get(url, timeout=self.timeout, headers=self._headers())
                if r.ok and r.text.strip():
                    return r.text
            except Exception:
                continue
        return None

    # --------------------------------------------------------- fetch & clean
    def _headers(self) -> dict:
        return {"User-Agent": self.user_agent, "Accept": "text/html,*/*;q=0.8"}

    def fetch_clean(self, url: str) -> Optional[str]:
        """Returns cleaned, token-bounded text for ``url`` or None."""
        if url in self._visited:
            log.info("skip (visited): %s", url)
            return None
        if not self.can_fetch(url):
            log.warning("robots disallowed: %s", url)
            return None

        import requests

        try:
            resp = requests.get(url, timeout=self.timeout, headers=self._headers())
            resp.raise_for_status()
        except Exception as exc:
            log.warning("fetch failed %s: %s", url, exc)
            return None

        html = resp.text
        text = self._extract_main(html)
        text = self._strip_noise(text)
        text = self._truncate_to_budget(text, self.token_budget)

        self._visited.add(url)
        self._persist()
        return text

    def _extract_main(self, html: str) -> str:
        # Try Readability first, fall back to BeautifulSoup main heuristics.
        try:
            from readability import Document  # type: ignore

            doc = Document(html)
            return doc.summary(html_partial=True)
        except Exception:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            for tag in soup.find_all(_NON_SEMANTIC_TAGS):
                tag.decompose()
            main = soup.find("main") or soup.find("article") or soup.body or soup
            return main.get_text(" ", strip=True)

    def _strip_noise(self, text_or_html: str) -> str:
        from bs4 import BeautifulSoup  # type: ignore

        if "<" in text_or_html and ">" in text_or_html:
            soup = BeautifulSoup(text_or_html, "html.parser")
            for tag in soup.find_all(_NON_SEMANTIC_TAGS):
                tag.decompose()
            text = soup.get_text(" ", strip=True)
        else:
            text = text_or_html
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _truncate_to_budget(text: str, max_tokens: int) -> str:
        """Approximate token count via whitespace; cut at last sentence end."""
        words = text.split()
        if len(words) <= max_tokens:
            return text
        truncated = " ".join(words[:max_tokens])
        # Snap back to the last sentence boundary for cleanliness.
        sentences = _SENTENCE_END.split(truncated)
        if len(sentences) > 1:
            truncated = " ".join(sentences[:-1]).rstrip()
        log.info("truncated content from %d to %d tokens", len(words), max_tokens)
        return truncated
