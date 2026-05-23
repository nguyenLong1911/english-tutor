"""Promote Wikipedia raw glossary terms into ``industry_context_library.json``.

This extractor runs **without an LLM**. It performs the work that *does not*
require Vietnamese-language understanding:

* Map raw ``{term, definition_en}`` to the canonical ``IndustryVocabItem``
  schema.
* Heuristically pick a CEFR level from definition length (proxy for
  complexity) and term capitalisation (proper nouns → C1).
* Default ``register='semi-formal'`` (Wikipedia tone).
* Leave ``definition_vi`` and ``example_sentence`` empty and tag the entry
  with ``needs_translation`` / ``needs_example`` so the LLM enrichment stage
  (Sprint 2) can fill them.

The promoter writes to a side-car file by default
(``data/processed/industry_vocab/wiki_auto_extracted.json``) so the curated
manual seed bank is never overwritten. Use ``--merge`` to APPEND
(de-duplicated) into the canonical library when you trust the source.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Dict, List

from ..json_io import load_json, save_json
from ..paths import INDUSTRY_CANONICAL, RAW_WIKIPEDIA_GLOSSARIES, WIKI_AUTO

log = logging.getLogger(__name__)

REGISTER_DEFAULT = "semi-formal"


def _guess_cefr(term: str, definition_en: str) -> str:
    """Lightweight heuristic – not a substitute for a real CEFR classifier."""
    n_words = len(definition_en.split())
    has_caps = any(c.isupper() for c in term[1:])  # mid-word caps → likely jargon
    if n_words >= 35 or has_caps:
        return "C1"
    if n_words >= 22:
        return "B2"
    if n_words >= 12:
        return "B1"
    return "A2"


def _to_vocab_item(term: str, definition_en: str, industry: str) -> dict:
    return {
        "term": term,
        "definition_en": definition_en,
        "definition_vi": "",                 # filled by LLM stage
        "example_sentence": "",              # filled by LLM stage
        "industry": industry,
        "register": REGISTER_DEFAULT,
        "cefr_level": _guess_cefr(term, definition_en),
        "usage_note": "",
        "related_terms": [],
        "_meta": {
            "source": "wikipedia",
            "needs_translation": True,
            "needs_example": True,
            "auto_promoted": True,
        },
    }


def _load_raw(raw_dir: Path) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for f in sorted(raw_dir.glob("*.json")):
        try:
            data = load_json(f)
        except Exception as exc:
            log.warning("skip %s: %s", f, exc)
            continue
        industry = data.get("industry") or f.stem.title()
        out[industry] = data.get("terms", [])
    return out


def run(
    *,
    raw_dir: Path = RAW_WIKIPEDIA_GLOSSARIES,
    out_path: Path = WIKI_AUTO,
    canonical_path: Path = INDUSTRY_CANONICAL,
    merge: bool = False,
    cap_per_industry: int = 100,
) -> dict:
    raw = _load_raw(raw_dir)
    industries_payload: Dict[str, dict] = {}

    canonical = None
    if merge and canonical_path.exists():
        canonical = load_json(canonical_path)

    stats: Dict[str, dict] = {}
    for industry, terms in raw.items():
        # Build set of existing terms (lower-cased) to avoid duplicates.
        seen: set[str] = set()
        if canonical and industry in canonical.get("industries", {}):
            for v in canonical["industries"][industry].get("vocabulary", []):
                seen.add(v["term"].strip().lower())

        promoted: List[dict] = []
        for t in terms:
            term, defn = (t.get("term") or "").strip(), (t.get("definition_en") or "").strip()
            if not term or not defn or len(defn) < 8:
                continue
            if term.lower() in seen:
                continue
            seen.add(term.lower())
            promoted.append(_to_vocab_item(term, defn, industry))
            if len(promoted) >= cap_per_industry:
                break

        industries_payload[industry] = {
            "description": f"Auto-promoted from Wikipedia (CC BY-SA 4.0). Awaiting VI translation + examples.",
            "vocabulary": promoted,
        }
        stats[industry] = {"promoted": len(promoted), "raw_available": len(terms)}

        if merge and canonical is not None:
            canonical.setdefault("industries", {}).setdefault(
                industry, {"description": "", "vocabulary": []}
            )["vocabulary"].extend(promoted)

    payload = {
        "metadata": {
            "version": "0.1.0",
            "source": "wikipedia",
            "extractor": "data_pipeline.extractors.wiki_to_industry_vocab",
            "merged_into_canonical": merge,
            "stats": stats,
        },
        "industries": industries_payload,
    }
    save_json(out_path, payload)
    log.info("wrote → %s (industries=%d, total=%d)", out_path,
             len(industries_payload),
             sum(s["promoted"] for s in stats.values()))

    if merge and canonical is not None:
        save_json(canonical_path, canonical)
        log.info("merged into canonical → %s", canonical_path)

    return {"stats": stats, "out_path": str(out_path)}


def _cli() -> int:
    p = argparse.ArgumentParser(description="Promote Wikipedia raw → industry vocab")
    p.add_argument("--raw-dir", default="data/raw/wikipedia/glossaries")
    p.add_argument("--out", default="data/processed/industry_vocab/wiki_auto_extracted.json")
    p.add_argument(
        "--canonical",
        default="data/processed/industry_vocab/industry_context_library.json",
    )
    p.add_argument("--merge", action="store_true",
                   help="Append into the canonical library (in addition to side-car).")
    p.add_argument("--cap", type=int, default=100, help="Max items per industry.")
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    res = run(
        raw_dir=Path(args.raw_dir),
        out_path=Path(args.out),
        canonical_path=Path(args.canonical),
        merge=args.merge,
        cap_per_industry=args.cap,
    )
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
