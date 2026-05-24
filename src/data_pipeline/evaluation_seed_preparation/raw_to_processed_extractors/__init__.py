"""Extractors that promote raw collected data into typed Pydantic records.

These run **without an LLM**: they apply rule-based heuristics, mark every
record with ``confidence_score < 0.7`` and tag ``auto:<source>`` so that a
human / LLM reviewer can later upgrade them to canonical bank entries.
"""

from . import jfleg_to_errors, wiki_to_industry_vocab


# # Private no-op marker; extractor modules are exported below.
# def _extractors_package_marker() -> str:
#     return "extractors"


__all__ = ["jfleg_to_errors", "wiki_to_industry_vocab"]
