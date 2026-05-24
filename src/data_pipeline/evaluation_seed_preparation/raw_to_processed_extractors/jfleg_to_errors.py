"""JFLEG → V-English Error Bank rule-based extractor (no LLM required).

Reads the raw JFLEG JSONL files persisted by
:mod:`data_pipeline.reference_data_collection.sources.huggingface`, computes a token-level diff
between each ``source`` sentence and its closest ``correction``, and emits
``ESLErrorInstance`` candidates classified by simple closed-class lexicons.

Output policy
-------------
* Each record is tagged ``auto:jfleg`` with ``confidence_score = 0.55``.
* The script writes to a *separate* file
  (``data/processed/common_errors/jfleg_auto_extracted.json``) – it does NOT
  merge into the canonical bank automatically. A human reviewer (or, later,
  the LLM-as-a-judge stage) is expected to promote vetted entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import string
from difflib import SequenceMatcher
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from ...shared_pipeline_support.json_dataset_file_io import read_jsonl, save_json
from ...shared_pipeline_support.data_file_paths import JFLEG_AUTO, RAW_JFLEG
from ...shared_pipeline_support.processed_dataset_schemas import ESLErrorInstance

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Closed-class lexicons used by the rule classifier
# ---------------------------------------------------------------------------

PREPS = {
    "in", "on", "at", "of", "to", "for", "with", "by", "from", "about",
    "into", "onto", "upon", "over", "under", "through", "between", "among",
    "against", "during", "before", "after", "since", "until", "across",
    "behind", "beside", "off", "out", "up", "down",
}
ARTICLES = {"a", "an", "the"}
AUX_BE = {"is", "are", "was", "were", "be", "been", "being", "am"}
AUX_DO = {"do", "does", "did", "doing", "done"}
AUX_HAVE = {"have", "has", "had", "having"}
MODALS = {"can", "could", "may", "might", "must", "shall", "should", "will", "would", "ought"}

_PUNCT_RE = re.compile(rf"^[{re.escape(string.punctuation)}]+$")
_TOKEN_RE = re.compile(r"\w+|[^\w\s]")


def tokenize(s: str) -> List[str]:
    return _TOKEN_RE.findall(s)


def _short_id(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:6].upper()


# ---------------------------------------------------------------------------
# Closest-correction picker
# ---------------------------------------------------------------------------

def _best_correction(source: str, corrections: Iterable[str]) -> str | None:
    best: Tuple[float, str] | None = None
    src_tokens = tokenize(source.lower())
    for c in corrections:
        if not c or c.strip() == source.strip():
            continue
        c_tokens = tokenize(c.lower())
        ratio = SequenceMatcher(None, src_tokens, c_tokens).ratio()
        # Prefer corrections that DIFFER but remain *close* (avoid full rewrites).
        if 0.5 <= ratio < 0.99:
            if best is None or ratio > best[0]:
                best = (ratio, c)
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Rule-based classifier on a single diff opcode
# ---------------------------------------------------------------------------

def _classify(span1: List[str], span2: List[str]) -> str | None:
    """Return ErrorCategory string or None to skip."""
    s1 = [t for t in span1 if not _PUNCT_RE.match(t)]
    s2 = [t for t in span2 if not _PUNCT_RE.match(t)]
    if not s1 and not s2:
        return None  # punctuation-only edit
    if len(s1) > 3 or len(s2) > 3:
        return None  # too coarse to attribute confidently

    # Casing-only change (same lowercased tokens) → skip
    if [t.lower() for t in s1] == [t.lower() for t in s2]:
        return None

    in_set = lambda toks, s: all(t.lower() in s for t in toks) if toks else False

    # Single-token replacements / single insertions / single deletions
    one_one = len(s1) <= 1 and len(s2) <= 1

    if one_one and (in_set(s1, ARTICLES) or in_set(s2, ARTICLES)):
        return "articles"
    if one_one and (in_set(s1, PREPS) or in_set(s2, PREPS)):
        return "prepositions"
    if one_one and (in_set(s1, AUX_BE) or in_set(s2, AUX_BE)):
        # be-verb form changes → tense_and_aspect (covers SVA too).
        return "tense_and_aspect"
    if one_one and (in_set(s1, AUX_DO) or in_set(s2, AUX_DO)
                    or in_set(s1, AUX_HAVE) or in_set(s2, AUX_HAVE)):
        return "tense_and_aspect"
    if one_one and (in_set(s1, MODALS) or in_set(s2, MODALS)):
        return "modal_verbs"

    # Verb-form swap heuristic: same first 3 chars, both end in {-s,-ed,-ing}.
    if len(s1) == 1 and len(s2) == 1:
        a, b = s1[0].lower(), s2[0].lower()
        if a[:3] == b[:3] and len(a) >= 3 and len(b) >= 3 and a != b:
            if any(a.endswith(suf) or b.endswith(suf) for suf in ("s", "ed", "ing", "es")):
                return "tense_and_aspect"
            if any(a.endswith(suf) or b.endswith(suf) for suf in ("er", "est", "ly")):
                return "word_choice_lexical"

    # Word-order: same multiset, different order
    if len(s1) >= 2 and sorted(t.lower() for t in s1) == sorted(t.lower() for t in s2):
        return "word_order"

    return "word_choice_lexical"


# ---------------------------------------------------------------------------
# Per-pair extractor
# ---------------------------------------------------------------------------

def extract_from_pair(source: str, correction: str) -> List[ESLErrorInstance]:
    src = tokenize(source)
    cor = tokenize(correction)
    sm = SequenceMatcher(None, [t.lower() for t in src], [t.lower() for t in cor])
    out: List[ESLErrorInstance] = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        span1 = src[i1:i2]
        span2 = cor[j1:j2]
        cat = _classify(span1, span2)
        if cat is None:
            continue
        wrong = " ".join(span1) or "(∅)"
        right = " ".join(span2) or "(∅)"
        pattern = f"{wrong} → {right}"
        sig = f"{cat}|{wrong.lower()}|{right.lower()}|{source[:60].lower()}"
        try:
            out.append(ESLErrorInstance(
                id=f"ERR-{cat[:4].upper()}-{_short_id(sig)}",
                category=cat,
                error_pattern=pattern,
                incorrect_example=source,
                correct_example=correction,
                explanation_vi="Lỗi tự động trích từ JFLEG; cần biên tập viên rà soát.",
                explanation_en=(
                    "Auto-extracted from JFLEG via rule-based diff; awaiting "
                    "linguistic review for L1-Vietnamese transfer attribution."
                ),
                scaffolding_hint="",
                importance_score=0.5,
                frequency="low",
                cefr_level="B1",
                confidence_score=0.55,
                tags=["auto:jfleg", cat, "needs_review"],
            ))
        except Exception as exc:
            log.debug("instance build failed: %s (cat=%s, span1=%s, span2=%s)",
                      exc, cat, span1, span2)
    return out


# ---------------------------------------------------------------------------
# File-level orchestration
# ---------------------------------------------------------------------------

def extract_from_jsonl(
    path: Path,
    *,
    max_records: int | None = None,
) -> List[ESLErrorInstance]:
    out: List[ESLErrorInstance] = []
    for rec in read_jsonl(path):
        src = rec.get("source", "")
        corrections = rec.get("corrections") or []
        best = _best_correction(src, corrections)
        if not best:
            continue
        out.extend(extract_from_pair(src, best))
        if max_records and len(out) >= max_records:
            break
    return out


def run(
    *,
    raw_dir: Path = RAW_JFLEG,
    out_path: Path = JFLEG_AUTO,
    max_records: int = 1000,
) -> dict:
    """End-to-end: read JFLEG JSONLs → ESLErrorInstance → JSON file."""
    all_errors: List[ESLErrorInstance] = []
    for split in ("dev", "test"):
        p = raw_dir / f"jfleg_{split}.jsonl"
        if not p.exists():
            log.warning("missing JFLEG split: %s", p)
            continue
        before = len(all_errors)
        all_errors.extend(extract_from_jsonl(p, max_records=max_records))
        log.info("jfleg[%s] → %d new candidates", split, len(all_errors) - before)
        if len(all_errors) >= max_records:
            break

    # Dedup by (category, pattern, incorrect_example trimmed)
    seen, deduped = set(), []
    for e in all_errors:
        k = (e.category, e.error_pattern.lower(), e.incorrect_example[:80].lower())
        if k in seen:
            continue
        seen.add(k)
        deduped.append(e)

    # Per-category stats
    stats: Dict[str, int] = {}
    for e in deduped:
        stats[e.category.value if hasattr(e.category, "value") else str(e.category)] = (
            stats.get(e.category.value if hasattr(e.category, "value") else str(e.category), 0) + 1
        )

    payload = {
        "metadata": {
            "version": "0.1.0",
            "source": "JFLEG (https://github.com/keisks/jfleg)",
            "extractor": "rule-based diff (data_pipeline.evaluation_seed_preparation.raw_to_processed_extractors.jfleg_to_errors)",
            "needs_review": True,
            "total_candidates": len(deduped),
            "category_distribution": stats,
        },
        "errors": [e.model_dump(mode="json") for e in deduped],
    }
    save_json(out_path, payload)
    log.info("wrote %d candidates → %s", len(deduped), out_path)
    return {"count": len(deduped), "stats": stats, "path": str(out_path)}


# ---------------------------------------------------------------------------
# CLI helper (also wired up in data_pipeline.command_line_interface)
# ---------------------------------------------------------------------------

def _cli() -> int:
    p = argparse.ArgumentParser(description="Extract ESL errors from JFLEG.")
    p.add_argument("--raw-dir", default="data/raw/huggingface/jfleg")
    p.add_argument("--out", default="data/processed/common_errors/jfleg_auto_extracted.json")
    p.add_argument("--max", type=int, default=1000)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    res = run(raw_dir=Path(args.raw_dir), out_path=Path(args.out), max_records=args.max)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
