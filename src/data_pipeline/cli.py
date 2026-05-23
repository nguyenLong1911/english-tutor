"""``python -m data_pipeline`` / ``a20-pipeline`` CLI.

Sub-commands:

    scrape       Run keyless collectors (Wikipedia, HuggingFace by default).
                 IELTS public scraping is opt-in (`--sources ielts`) because
                 most IELTS material is copyrighted; per data_planning.md the
                 IELTS dataset is sourced via manual collection + synthetic.
    validate     Run JSON-Schema validation across data/processed/*.
    quality-process
                 Apply local quality gates to already-processed datasets.
    info         Print a concise status report.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Iterable

log = logging.getLogger("data_pipeline.cli")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


# ---------------------------------------------------------------------------
# scrape
# ---------------------------------------------------------------------------

def cmd_scrape(args: argparse.Namespace) -> int:
    from .sources import wikipedia, huggingface, ielts_public

    # Default collectors exclude `ielts`: Cambridge / British Council pages
    # are copyright-protected (robots.txt disallow). Per ``docs/data_planning.md``
    # the IELTS dataset is filled via manual seed + synthetic generation,
    # not scraping. Pass ``--sources ielts`` explicitly to opt in.
    selected = set(args.sources or ["wikipedia", "huggingface"])
    report: dict = {}

    if "wikipedia" in selected:
        report["wikipedia"] = wikipedia.collect(
            industries=args.industries.split(",") if args.industries else None,
            out_dir=Path(args.out_dir) / "wikipedia" / "glossaries",
        )
    if "huggingface" in selected:
        report["huggingface"] = huggingface.collect(
            out_dir=Path(args.out_dir) / "huggingface",
            use_hf=args.use_hf,
        )
    if "ielts" in selected:
        report["ielts"] = ielts_public.collect(
            out_dir=Path(args.out_dir) / "ielts",
        )

    summary_path = Path(args.out_dir) / "scrape_report.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("scrape report → %s", summary_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------

def cmd_extract(args: argparse.Namespace) -> int:
    """Run rule-based extractors that promote raw → processed without an LLM."""
    from .extractors import jfleg_to_errors, wiki_to_industry_vocab

    selected = set(args.targets or ["jfleg", "wiki_vocab"])
    report: dict = {}
    if "jfleg" in selected:
        report["jfleg_to_errors"] = jfleg_to_errors.run(
            raw_dir=Path(args.raw_dir) / "huggingface" / "jfleg",
            out_path=Path("data/processed/common_errors/jfleg_auto_extracted.json"),
            max_records=args.max,
        )
    if "wiki_vocab" in selected:
        report["wiki_to_industry_vocab"] = wiki_to_industry_vocab.run(
            raw_dir=Path(args.raw_dir) / "wikipedia" / "glossaries",
            out_path=Path("data/processed/industry_vocab/wiki_auto_extracted.json"),
            canonical_path=Path("data/processed/industry_vocab/industry_context_library.json"),
            merge=args.merge,
            cap_per_industry=args.cap,
        )
    out = Path(args.raw_dir) / "extract_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    log.info("extract report → %s", out)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .validate import main as _validate_main

    return _validate_main()


def cmd_generate(args: argparse.Namespace) -> int:
    from .generate import run as _generate_run

    return _generate_run(args)


def cmd_process_existing(args: argparse.Namespace) -> int:
    """Process existing raw/processed data without network or LLM calls."""
    from .offline_process import run_all

    run_all(args)
    return 0


def cmd_quality_process(args: argparse.Namespace) -> int:
    """Apply quality gates to processed data without scraping or raw collection."""
    from .quality_process import run_all

    run_all(args)
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    from .audit import main as _audit_main

    return _audit_main(args)


# ---------------------------------------------------------------------------
# info
# ---------------------------------------------------------------------------

def cmd_info(_args: argparse.Namespace) -> int:
    from . import __all__ as exports

    print("a20-data-pipeline – exports:")
    for name in exports:
        print(f"  - {name}")
    raw = Path("data/raw")
    proc = Path("data/processed")
    if raw.exists():
        print("\ndata/raw/:")
        for p in sorted(raw.rglob("*")):
            if p.is_file():
                size = p.stat().st_size
                print(f"  {p.relative_to(raw.parent)}  ({size} bytes)")
    if proc.exists():
        print("\ndata/processed/:")
        for p in sorted(proc.glob("*/*.json")):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                count = (
                    len(data.get("errors", []))
                    or len(data.get("samples", []))
                    or len(data.get("prompts", []))
                    or sum(len(v.get("vocabulary", [])) for v in data.get("industries", {}).values())
                    or sum(len(v.get("facts", [])) for v in data.get("users", {}).values())
                )
            except Exception:
                count = "?"
            print(f"  {p.relative_to(proc.parent)}  entries={count}")
    return 0


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="a20-pipeline", description="A20 data pipeline CLI")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scrape", help="Run keyless collectors")
    sc.add_argument(
        "--sources",
        nargs="+",
        choices=["wikipedia", "huggingface", "ielts"],
        default=None,
        help="Subset of collectors. Default = wikipedia + huggingface "
             "(ielts is opt-in; see docs/data_pipeline_doc.md §2.4).",
    )
    sc.add_argument("--industries", default=None,
                    help="Comma-separated subset of industries for Wikipedia.")
    sc.add_argument("--use-hf", action="store_true",
                    help="Also try the `datasets` package path.")
    sc.add_argument("--out-dir", default="data/raw")
    sc.set_defaults(func=cmd_scrape)

    ex = sub.add_parser("extract", help="Rule-based extractors (no LLM)")
    ex.add_argument(
        "--targets",
        nargs="+",
        choices=["jfleg", "wiki_vocab"],
        default=None,
    )
    ex.add_argument("--raw-dir", default="data/raw")
    ex.add_argument("--max", type=int, default=1000,
                    help="Max JFLEG candidates to emit (jfleg target).")
    ex.add_argument("--cap", type=int, default=100,
                    help="Cap per industry for wiki_vocab target.")
    ex.add_argument("--merge", action="store_true",
                    help="Merge wiki_vocab into the canonical library.")
    ex.set_defaults(func=cmd_extract)

    va = sub.add_parser("validate", help="Validate processed datasets")
    va.set_defaults(func=cmd_validate)

    gen = sub.add_parser(
        "generate",
        help="Synthetic data generation (Seed -> Expand -> Judge -> Decontaminate, needs OPENAI_API_KEY)",
    )
    from .generate import add_arguments as _add_generate_args
    _add_generate_args(gen)
    gen.set_defaults(func=cmd_generate)

    proc = sub.add_parser(
        "process-existing",
        help="Clean and expand already-collected data only (no scraping, no LLM).",
    )
    proc.add_argument("--promote-jfleg", type=int, default=500)
    proc.add_argument("--errors-target", type=int, default=500)
    proc.add_argument("--ielts-target", type=int, default=60)
    proc.add_argument("--pedagogical-target", type=int, default=80)
    proc.add_argument("--mood-target", type=int, default=60)
    proc.add_argument("--mem0-target", type=int, default=100)
    proc.set_defaults(func=cmd_process_existing)

    qp = sub.add_parser(
        "quality-process",
        help="Quality-gate existing data/processed files only (no scraping).",
    )
    qp.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip the bounded aggregate LLM certification call.",
    )
    qp.set_defaults(func=cmd_quality_process)

    au = sub.add_parser(
        "audit",
        help="Check local raw/processed data readiness against PRD and scraping docs.",
    )
    au.set_defaults(func=cmd_audit)

    info = sub.add_parser("info", help="Show pipeline status")
    info.set_defaults(func=cmd_info)

    return p


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(getattr(args, "verbose", False))
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
