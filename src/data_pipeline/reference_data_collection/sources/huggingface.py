"""ESL learner-corpus loader.

Two paths are provided:

1. **GitHub raw download** (default, no extra deps): pulls JFLEG dev/test
   files directly from the public ``keisks/jfleg`` repo. JFLEG is a
   permissively-licensed grammatical-error-correction corpus.
2. **HuggingFace ``datasets`` package** (opt-in via ``use_hf=True``):
   loads the same datasets through the standard library when installed.

JFLEG entries are persisted as JSONL with fields:
    {"source": str, "corrections": list[str]}
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Iterable, List

import requests

from ...shared_pipeline_support.json_dataset_file_io import write_jsonl
from ...shared_pipeline_support.data_file_paths import RAW_HUGGINGFACE, RAW_JFLEG

log = logging.getLogger(__name__)

USER_AGENT = "A20-DataPipeline/0.1 (research)"

# Public raw URLs (CC0 / permissive – see https://github.com/keisks/jfleg)
JFLEG_FILES: Dict[str, Dict[str, str]] = {
    "dev": {
        "src": "https://raw.githubusercontent.com/keisks/jfleg/master/dev/dev.src",
        "ref0": "https://raw.githubusercontent.com/keisks/jfleg/master/dev/dev.ref0",
        "ref1": "https://raw.githubusercontent.com/keisks/jfleg/master/dev/dev.ref1",
        "ref2": "https://raw.githubusercontent.com/keisks/jfleg/master/dev/dev.ref2",
        "ref3": "https://raw.githubusercontent.com/keisks/jfleg/master/dev/dev.ref3",
    },
    "test": {
        "src": "https://raw.githubusercontent.com/keisks/jfleg/master/test/test.src",
        "ref0": "https://raw.githubusercontent.com/keisks/jfleg/master/test/test.ref0",
        "ref1": "https://raw.githubusercontent.com/keisks/jfleg/master/test/test.ref1",
        "ref2": "https://raw.githubusercontent.com/keisks/jfleg/master/test/test.ref2",
        "ref3": "https://raw.githubusercontent.com/keisks/jfleg/master/test/test.ref3",
    },
}


def _download(url: str, *, session: requests.Session, timeout: float = 30.0) -> str | None:
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
    except Exception as exc:
        log.warning("download failed %s: %s", url, exc)
        return None
    return r.text


def _zip_jfleg(src: str, refs: List[str]) -> Iterable[Dict[str, object]]:
    src_lines = src.splitlines()
    ref_lines = [r.splitlines() for r in refs]
    for i, s in enumerate(src_lines):
        s = s.strip()
        if not s:
            continue
        corrections = []
        for rl in ref_lines:
            if i < len(rl):
                c = rl[i].strip()
                if c and c != s:
                    corrections.append(c)
        yield {"source": s, "corrections": list(dict.fromkeys(corrections))}


def collect_jfleg(
    *,
    out_dir: Path = RAW_JFLEG,
    splits: Iterable[str] = ("dev", "test"),
) -> Dict[str, dict]:
    """Download JFLEG, persist as JSONL. Returns per-split stats."""
    out_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    summary: Dict[str, dict] = {}
    for split in splits:
        files = JFLEG_FILES.get(split)
        if not files:
            log.warning("unknown jfleg split: %s", split)
            continue
        src = _download(files["src"], session=session)
        if src is None:
            summary[split] = {"count": 0, "error": "src download failed"}
            continue
        refs = []
        for k in ("ref0", "ref1", "ref2", "ref3"):
            txt = _download(files[k], session=session)
            if txt is not None:
                refs.append(txt)
        records = list(_zip_jfleg(src, refs))
        out = out_dir / f"jfleg_{split}.jsonl"
        write_jsonl(out, records)
        summary[split] = {
            "count": len(records),
            "with_corrections": sum(1 for r in records if r["corrections"]),
            "path": str(out),
        }
        log.info("jfleg[%s] %d sentences → %s", split, len(records), out)
    return summary


def collect_via_hf(dataset_name: str, *, out_dir: Path) -> Dict[str, dict]:
    """Optional path: use ``datasets`` package if installed."""
    try:
        from datasets import load_dataset  # type: ignore
    except Exception:
        log.warning("`datasets` package not installed; skipping HF path.")
        return {"error": "datasets package not installed"}

    out_dir.mkdir(parents=True, exist_ok=True)
    ds = load_dataset(dataset_name)
    summary: Dict[str, dict] = {}
    for split, data in ds.items():
        out = out_dir / f"{dataset_name.replace('/', '__')}_{split}.jsonl"
        write_jsonl(out, data)
        summary[split] = {"count": len(data), "path": str(out)}
    return summary


def collect(
    *,
    out_dir: Path = RAW_HUGGINGFACE,
    use_hf: bool = False,
) -> Dict[str, dict]:
    """Top-level collector. By default downloads JFLEG via GitHub raw."""
    summary: Dict[str, dict] = {"jfleg": collect_jfleg(out_dir=out_dir / "jfleg")}
    if use_hf:
        summary["hf_jfleg"] = collect_via_hf("jfleg", out_dir=out_dir / "hf_jfleg")
    return summary
