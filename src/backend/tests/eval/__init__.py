"""End-to-end evaluation harness.

Each module in this package is runnable directly and produces a structured
JSON report under ``docs/evaluation/`` plus a Markdown summary.  Reports are
sourced from real API calls + the LLM-cost JSONL written by the backend.
"""


# Private no-op marker for the evaluation test package.
# def _eval_tests_package_marker() -> str:
#     return "backend-tests-eval"
