"""Pydantic schemas for the A20 data pipeline.

These schemas drive *Constrained Decoding* (Level 4 from the guide).
They are passed directly to ``client.beta.chat.completions.parse`` so the LLM
infrastructure forces token probabilities outside the schema to zero,
guaranteeing structurally valid JSON output.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# 1. Common Errors (V-English Error Bank)
# ---------------------------------------------------------------------------

class ErrorCategory(str, Enum):
    """Linguistic error categories grounded in Vietnamese-English contrastive
    analysis (see citations [14], [15], [34] in the guide)."""

    PREPOSITIONS = "prepositions"
    ARTICLES = "articles"
    TENSES = "tenses"  # legacy alias kept for backward-compat with seed bank
    TENSE_AND_ASPECT = "tense_and_aspect"
    PRONUNCIATION_CONFUSION = "pronunciation_confusion"
    SUBJECT_VERB_AGREEMENT = "subject_verb_agreement"
    COPULA_BE_OMISSION = "copula_be_omission"
    COPULA_BE_REDUNDANCY = "copula_be_redundancy"
    ADVERB_MISPLACEMENT = "adverb_misplacement"
    WORD_CHOICE_LEXICAL = "word_choice_lexical"
    WORD_ORDER = "word_order"
    L1_INTERFERENCE_STRUCTURE = "l1_interference_structure"
    PUNCTUATION_AND_AGREEMENT = "punctuation_and_agreement"
    COLLOCATIONS = "collocations"
    COUNTABLE_UNCOUNTABLE = "countable_uncountable"
    CONDITIONALS = "conditionals"
    REPORTED_SPEECH = "reported_speech"
    PASSIVE_VOICE = "passive_voice"
    MODAL_VERBS = "modal_verbs"
    PHRASAL_VERBS = "phrasal_verbs"
    FALSE_FRIENDS = "false_friends"
    SENTENCE_STRUCTURE = "sentence_structure"


CEFR_PATTERN = r"^(A1|A2|B1|B2|C1|C2)$"


class ESLErrorInstance(BaseModel):
    """A single ESL grammar error annotation."""

    id: str = Field(..., description="Stable identifier, format: ERR-<CAT>-<HEX6>.")
    category: ErrorCategory = Field(
        ..., description="Phân loại lỗi dựa trên danh mục lỗi ESL Việt-Anh đã định nghĩa."
    )
    error_pattern: str = Field(
        ..., description="Mẫu lỗi ngắn gọn dạng 'wrong → correct'."
    )
    incorrect_example: str = Field(
        ..., description="Đoạn văn gốc chứa lỗi do người Việt viết, chưa hiệu đính."
    )
    correct_example: str = Field(
        ..., description="Đoạn văn sau khi đã được hiệu đính chuẩn xác."
    )
    explanation_vi: str = Field(
        ..., description="Giải thích bằng tiếng Việt, chỉ rõ L1 transfer hoặc quy tắc bị nhầm."
    )
    explanation_en: str = Field(
        ..., description="English explanation of the underlying rule."
    )
    scaffolding_hint: str = Field(
        ..., description="Hint sư phạm ngắn gọn, dễ nhớ để hạ thấp Affective Filter."
    )
    importance_score: float = Field(..., ge=0.0, le=1.0)
    frequency: Literal["high", "medium", "low"] = Field(...)
    cefr_level: str = Field(..., pattern=CEFR_PATTERN)
    confidence_score: float = Field(default=0.9, ge=0.0, le=1.0)
    tags: List[str] = Field(default_factory=list)


class ESLGrammarDatasetBatch(BaseModel):
    """A batch of error instances with provenance, used at scrape/extract time."""

    source_url: str = Field(..., description="URL nguồn của tài liệu thu thập.")
    scraped_at: str = Field(..., description="ISO 8601 timestamp.")
    errors_detected: List[ESLErrorInstance] = Field(...)

    @field_validator("scraped_at")
    @classmethod
    def _ensure_iso(cls, v: str) -> str:
        # Permit "Z" suffix; raise if completely unparseable.
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"scraped_at must be ISO 8601: {v!r}") from exc
        return v


# ---------------------------------------------------------------------------
# 2. Industry Vocabulary
# ---------------------------------------------------------------------------

class IndustryVocabItem(BaseModel):
    # ``register`` shadows ``BaseModel.register`` in Pydantic v2; keep the
    # original JSON field name via an alias and expose the Python attribute
    # as ``register_level`` to silence the warning without breaking the data.
    model_config = ConfigDict(populate_by_name=True)

    term: str = Field(..., min_length=1)
    definition_en: str
    definition_vi: str
    example_sentence: str
    industry: Literal["IT", "Marketing", "Sales", "Finance", "Education", "Healthcare"]
    register_level: Literal["formal", "semi-formal", "informal"] = Field(..., alias="register")
    cefr_level: str = Field(..., pattern=CEFR_PATTERN)
    usage_note: str
    related_terms: List[str] = Field(default_factory=list)


class IndustryVocabBatch(BaseModel):
    industry: str
    vocabulary: List[IndustryVocabItem]


class SyntheticErrorBatch(BaseModel):
    """Lightweight batch wrapper used by the synthetic-data generator
    (no provenance fields, unlike :class:`ESLGrammarDatasetBatch`)."""

    errors: List[ESLErrorInstance]


# ---------------------------------------------------------------------------
# 3. Mem0 Facts
# ---------------------------------------------------------------------------

FactType = Literal[
    "error_pattern", "preference", "progress", "context", "goal", "mood_pattern"
]


class Mem0Fact(BaseModel):
    fact_id: str
    user_id: str
    persona: Literal["first_timer", "speed_runner", "qa_destroyer"]
    fact_type: FactType
    content: str = Field(..., description="No PII. Action-oriented memory string.")
    importance_score: float = Field(..., ge=0.0, le=1.0)
    created_at: str
    tags: List[str] = Field(default_factory=list)
    evidence: str

    @field_validator("created_at")
    @classmethod
    def _check_iso(cls, v: str) -> str:
        try:
            datetime.fromisoformat(v.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"created_at must be ISO 8601: {v!r}") from exc
        return v


class Mem0FactsBatch(BaseModel):
    facts: List[Mem0Fact]


# ---------------------------------------------------------------------------
# 4. IELTS Writing Task 2 samples
# ---------------------------------------------------------------------------

class IELTSWritingSample(BaseModel):
    id: str
    prompt: str = Field(..., description="Đề bài Task 2.")
    band: float = Field(..., ge=4.0, le=9.0)
    essay: str
    examiner_feedback: str = Field(
        ..., description="Đánh giá theo 4 tiêu chí: TR, CC, LR, GRA."
    )
    common_errors: List[str] = Field(
        default_factory=list,
        description="Liên kết tới error_pattern trong V-English Error Bank.",
    )
    cefr_level: str = Field(..., pattern=CEFR_PATTERN)
    topic: str


class IELTSDatasetBatch(BaseModel):
    samples: List[IELTSWritingSample]


# ---------------------------------------------------------------------------
# 5. Pedagogical Prompts (Scaffolding)
# ---------------------------------------------------------------------------

class PedagogicalPrompt(BaseModel):
    id: str
    learner_situation: str = Field(
        ..., description="Bối cảnh học viên gặp khó khăn (Bệnh Nghẽn / Bệnh Quên)."
    )
    scaffolding_steps: List[str] = Field(
        ..., min_length=2, description="Các bước gợi ý dần (i+1)."
    )
    socratic_questions: List[str] = Field(default_factory=list)
    expected_outcome: str
    target_skill: Literal["speaking", "writing", "listening", "reading", "grammar", "vocabulary"]
    cefr_level: str = Field(..., pattern=CEFR_PATTERN)
    affective_filter_strategy: str = Field(
        ..., description="Cách hạ thấp Affective Filter (Krashen)."
    )
    tags: List[str] = Field(default_factory=list)


class PedagogicalPromptBatch(BaseModel):
    prompts: List[PedagogicalPrompt]


# ---------------------------------------------------------------------------
# 6. Mood & Pattern (5 energy levels)
# ---------------------------------------------------------------------------

EnergyLevel = Literal["exhausted", "low", "neutral", "energized", "peak"]


class MoodPatternSample(BaseModel):
    id: str
    user_persona: Literal["first_timer", "speed_runner", "qa_destroyer"]
    energy_level: EnergyLevel
    self_reported_mood: str
    contextual_signals: List[str] = Field(
        default_factory=list,
        description="Tín hiệu cảm xúc gián tiếp (giờ học, hiệu năng, độ dài câu trả lời...)",
    )
    recommended_pace: Literal["slow", "moderate", "fast"]
    recommended_modality: Literal["review", "new_material", "drill", "free_practice"]
    sample_dialogue_turn: str
    timestamp: str


class MoodPatternBatch(BaseModel):
    samples: List[MoodPatternSample]


# ---------------------------------------------------------------------------
# 7. Learner Profile (Evidently-style, drives synthetic dialogue generation)
# ---------------------------------------------------------------------------

L1TransferFocus = Literal[
    "tense_and_aspect",
    "copula_be_omission",
    "copula_be_redundancy",
    "adverb_misplacement",
    "double_conjunction",
    "article_omission",
    "subject_verb_agreement",
    "word_order_svo",
    "word_choice_lexical",
]


class LearnerProfile(BaseModel):
    """Configurable learner profile used to seed synthetic dialogue generation
    (§ "Thiết kế Kịch bản Đối thoại ESL và Kiểm soát Ngữ nghĩa").

    The profile pins down *who* is speaking, at *what* level, with *which*
    L1-transfer biases, so the LLM emits realistic Vietnamese-English ESL
    errors instead of generic "non-native" text.
    """

    profile_id: str
    persona: Literal["first_timer", "speed_runner", "qa_destroyer"]
    cefr_level: str = Field(..., pattern=CEFR_PATTERN)
    occupation: str = Field(..., description="e.g. university student, marketing junior, nurse.")
    l1_transfer_focus: List[L1TransferFocus] = Field(
        ..., min_length=1,
        description="Top error categories this learner systematically produces.",
    )
    register_preference: Literal["formal", "semi-formal", "informal"] = "informal"
    mood: EnergyLevel = "neutral"
    scenario: str = Field(..., description="Concrete dialogue scenario, e.g. 'ordering coffee', 'business email follow-up'.")
    target_skill: Literal["speaking", "writing", "listening", "reading", "grammar", "vocabulary"]
    notes: str = ""


class LearnerProfileBatch(BaseModel):
    profiles: List[LearnerProfile]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
