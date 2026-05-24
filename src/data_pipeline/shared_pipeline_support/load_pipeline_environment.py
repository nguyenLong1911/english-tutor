"""Environment loading helpers for CLI and LLM-backed commands."""

from __future__ import annotations

from dotenv import load_dotenv

from .data_file_paths import ROOT, SRC


def load_pipeline_env() -> None:
    """Load supported local env files without printing secret values."""
    load_dotenv(ROOT / ".env")
    load_dotenv(SRC / ".env")
