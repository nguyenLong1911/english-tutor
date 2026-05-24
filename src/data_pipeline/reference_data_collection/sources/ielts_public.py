"""Public IELTS sample-essay collector.

This collector is **defensive**: it only fetches pages that pass a
``robots.txt`` check via :class:`data_pipeline.reference_data_collection.robots_aware_scraper.TargetedScraper`,
respects a token budget, and stores raw text. We do NOT redistribute
copyrighted essays – the raw cache lives under ``data/raw/ielts/`` and is
gitignored by convention.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Dict, List

from ...shared_pipeline_support.json_dataset_file_io import save_json
from ...shared_pipeline_support.data_file_paths import RAW_IELTS
from ..robots_aware_scraper import TargetedScraper

log = logging.getLogger(__name__)

# Curated public listing pages. ``TargetedScraper`` will silently skip any
# URL whose host disallows crawling in robots.txt. Add new entries with care.
DEFAULT_TARGETS: List[Dict[str, str]] = [
    # IELTS Liz – the practice-only pages explicitly invite re-use for study.
    {
        "name": "ielts_liz_writing_index",
        "url": "https://ieltsliz.com/ielts-writing-task-2/",
    },
    {
        "name": "ielts_simon_band9",
        "url": "https://ielts-simon.com/ielts-help-and-english-pr/",
    },
    {
        "name": "british_council_writing_intro",
        "url": "https://www.britishcouncil.org/exam/ielts/test/writing",
    },
]


def collect(
    *,
    targets: List[Dict[str, str]] | None = None,
    out_dir: Path = RAW_IELTS,
    token_budget: int = 4000,
    rate_limit_sec: float = 2.0,
) -> Dict[str, dict]:
    """Fetch each public IELTS landing page and persist cleaned text."""
    targets = targets or DEFAULT_TARGETS
    out_dir.mkdir(parents=True, exist_ok=True)

    scraper = TargetedScraper(
        token_budget=token_budget,
        queue_path=out_dir / "_visited.json",
    )
    summary: Dict[str, dict] = {}
    for t in targets:
        name, url = t["name"], t["url"]
        text = scraper.fetch_clean(url)
        if text is None:
            summary[name] = {"url": url, "status": "skipped"}
            log.info("ielts skip: %s", url)
        else:
            out_file = out_dir / f"{name}.txt"
            out_file.write_text(text, encoding="utf-8")
            summary[name] = {
                "url": url,
                "status": "ok",
                "tokens": len(text.split()),
                "path": str(out_file),
            }
            log.info("ielts ok: %s tokens=%d", url, len(text.split()))
        time.sleep(rate_limit_sec)

    # Persist a manifest so downstream stages (LLM extraction) can iterate.
    manifest = out_dir / "manifest.json"
    save_json(manifest, summary)
    return summary
