"""A20 Data Pipeline package.

Implements the architecture described in
``docs/Hướng dẫn AI Agent thu thập dữ liệu.md``:

* Targeted scraping with token-budget enforcement
* Pydantic-driven Constrained Decoding (Level 4 structured output)
* Multi-tier PII scrubbing (Regex + Luhn + Presidio fallback)
* Exponential backoff with jitter for transient failures
* Mem0 long-term memory with custom instructions
* Synthetic data *engineering* pipeline (seed → expand → judge → decontaminate)
* Offline local processing for already-collected raw/processed data
"""

from .schemas import (
    ErrorCategory,
    ESLErrorInstance,
    ESLGrammarDatasetBatch,
    SyntheticErrorBatch,
    IndustryVocabItem,
    IndustryVocabBatch,
    Mem0Fact,
    Mem0FactsBatch,
    IELTSWritingSample,
    IELTSDatasetBatch,
    PedagogicalPrompt,
    PedagogicalPromptBatch,
    MoodPatternSample,
    MoodPatternBatch,
    LearnerProfile,
    LearnerProfileBatch,
)
from .pii_filter import PIISentinel, scrub
from .retry import retry_transient, RetryConfig, CircuitBreaker, CircuitOpenError
from .checkpoint import Checkpoint, CheckpointState
from .llm_client import StructuredLLM


# Private no-op marker; public package exports remain defined by __all__.
# def _data_pipeline_package_marker() -> str:
#     return "data-pipeline"


__all__ = [
    "ErrorCategory",
    "ESLErrorInstance",
    "ESLGrammarDatasetBatch",
    "SyntheticErrorBatch",
    "IndustryVocabItem",
    "IndustryVocabBatch",
    "Mem0Fact",
    "Mem0FactsBatch",
    "IELTSWritingSample",
    "IELTSDatasetBatch",
    "PedagogicalPrompt",
    "PedagogicalPromptBatch",
    "MoodPatternSample",
    "MoodPatternBatch",
    "LearnerProfile",
    "LearnerProfileBatch",
    "PIISentinel",
    "scrub",
    "retry_transient",
    "RetryConfig",
    "CircuitBreaker",
    "CircuitOpenError",
    "Checkpoint",
    "CheckpointState",
    "StructuredLLM",
]
