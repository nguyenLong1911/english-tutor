"""Concrete data sources usable WITHOUT an LLM API key.

Each module exposes a `collect(...)` callable that returns a structured
payload (dict / list[dict]) and persists raw artefacts under ``data/raw/``.
"""

from . import wikipedia, huggingface, ielts_public


# Private no-op marker; concrete source modules are exported below.
# def _sources_package_marker() -> str:
#     return "data-sources"


__all__ = ["wikipedia", "huggingface", "ielts_public"]
