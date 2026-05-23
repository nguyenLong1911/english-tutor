from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class OnboardingCreate(BaseModel):
    email: Optional[str] = None
    display_name: Optional[str] = None
    cefr_level: str
    industry: str
    learning_goals: List[str]
    preferred_study_time: Optional[str] = None
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "email": "user@example.com",
            "cefr_level": "B1",
            "industry": "marketing",
            "learning_goals": ["business", "presentations"]
        }
    })
    
    @field_validator("cefr_level")
    @classmethod
    def validate_cefr_level(cls, v: str) -> str:
        valid_levels = ["A1", "A2", "B1", "B2", "C1"]
        if v not in valid_levels:
            raise ValueError(f"CEFR level must be one of {valid_levels}")
        return v
    
    @field_validator("learning_goals")
    @classmethod
    def validate_learning_goals(cls, v: List[str]) -> List[str]:
        if not v or len(v) == 0:
            raise ValueError("learning_goals must contain at least one goal")
        if len(v) > 10:
            raise ValueError("learning_goals must contain at most 10 goals")
        return v
    
    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("industry must not be empty")
        if len(v) > 100:
            raise ValueError("industry must be at most 100 characters")
        return v


class UserOut(BaseModel):
    user_id: UUID
    email: Optional[str] = None
    display_name: Optional[str] = None
    cefr_level: str
    industry: str
    learning_goals: List[str]
    preferred_study_time: Optional[str] = None
    role: Literal["user", "admin"] = "user"
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VocabularyOut(BaseModel):
    word_id: int
    word: str
    pos: str
    cefr_level: str
    definition_vi: str
    example: str
    industry_tags: List[str]

    model_config = ConfigDict(from_attributes=True)


class ReviewItem(BaseModel):
    card_kind: Literal["vocab", "error"] = "vocab"
    word_id: Optional[int] = None
    word: Optional[str] = None
    pos: Optional[str] = None
    definition_vi: Optional[str] = None
    example: Optional[str] = None
    next_review: date
    repetitions: int
    ease_factor: float
    interval_days: int
    flashcard_id: Optional[UUID] = None
    front: Optional[str] = None
    back: Optional[str] = None
    cloze_text: Optional[str] = None
    explanation_vi: Optional[str] = None
    error_type: Optional[str] = None
    source: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ReviewSubmit(BaseModel):
    user_id: UUID
    card_kind: Literal["vocab", "error"] = "vocab"
    word_id: Optional[int] = None
    flashcard_id: Optional[UUID] = None
    quality: int
    
    @field_validator("quality")
    @classmethod
    def validate_quality(cls, v: int) -> int:
        if not isinstance(v, int) or v < 0 or v > 5:
            raise ValueError("quality must be an integer between 0 and 5")
        return v
    
    @field_validator("word_id")
    @classmethod
    def validate_word_id(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v <= 0:
            raise ValueError("word_id must be a positive integer")
        return v

    @model_validator(mode="after")
    def validate_card_reference(self) -> "ReviewSubmit":
        if self.card_kind == "vocab" and self.word_id is None:
            raise ValueError("word_id is required for vocab review")
        if self.card_kind == "error" and self.flashcard_id is None:
            raise ValueError("flashcard_id is required for error review")
        return self


class ReviewSubmitResult(BaseModel):
    card_kind: Literal["vocab", "error"] = "vocab"
    word_id: Optional[int] = None
    flashcard_id: Optional[UUID] = None
    next_review: date
    interval_days: int
    ease_factor: float
    repetitions: int
    mastered: bool


class ChatRequest(BaseModel):
    user_id: Optional[UUID]
    message: str
    command: Optional[str] = None
    type: Optional[str] = None
    # Target architecture additions (§9.1, §9.2)
    mood_state: Optional[str] = None
    pasted_context: Optional[str] = None
    
    @field_validator("message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        if not v or len(v.strip()) == 0:
            raise ValueError("message must not be empty")
        if len(v) > 5000:
            raise ValueError("message must be at most 5000 characters")
        return v.strip()

    @field_validator("pasted_context")
    @classmethod
    def validate_pasted(cls, v):
        if v is None:
            return v
        v = str(v).strip()
        if len(v) > 4096:
            raise ValueError("pasted_context exceeds 4KB")
        return v or None


class ChatResponse(BaseModel):
    response: str
    hint_count: int
    intent: str
    session_id: Optional[str] = None
    agent_message: Optional[str] = None
    # Target architecture additions
    dna_delta: Optional[dict] = None
    recommended_review: Optional[List[dict]] = None
    cefr_step: Optional[int] = None
    learning_state: Optional[dict] = None
    ui_directive: Optional[dict] = None
    suggested_actions: Optional[List[dict]] = None

    model_config = ConfigDict(from_attributes=True)


LearningStep = Literal["NONE", "LESSON_READING", "PRACTICE", "FLASHCARD", "LESSON_COMPLETE"]
UIDirectiveScreen = Literal[
    "LESSON_READER",
    "PRACTICE_RUNNER",
    "PRACTICE_RESULT",
    "FLASHCARD_RUNNER",
    "LESSON_COMPLETE",
    "CHAT",
]


class LessonSummary(BaseModel):
    lesson_id: str
    title: str
    cefr_level: str
    lesson_path: str
    metadata_path: Optional[str] = None
    order_index: int
    skill_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class LessonContent(LessonSummary):
    markdown: str


class LessonVocabularyItem(BaseModel):
    word_id: str
    word: str
    pos: str
    definition_vi: str
    example: str
    source: str = "mock"


class LearnerProfile(BaseModel):
    user_id: str
    cefr_level: str
    industry: str
    learning_goals: List[str]
    weak_points: List[str] = Field(default_factory=list)
    preferred_language: str = "vi"


class LearningTransition(BaseModel):
    from_step: LearningStep
    to_step: LearningStep
    reason: str
    created_at: datetime


class LearningState(BaseModel):
    active_lesson_id: Optional[str] = None
    active_lesson_path: Optional[str] = None
    current_step: LearningStep = "NONE"
    practice_set_id: Optional[str] = None
    practice_completed: bool = False
    flashcards_completed: bool = False
    completed_lessons: List[str] = Field(default_factory=list)
    last_transition: Optional[LearningTransition] = None
    latest_practice_result: Optional[Dict[str, Any]] = None


class UIDirective(BaseModel):
    screen: UIDirectiveScreen
    action: Literal["OPEN", "CLOSE", "NONE"] = "OPEN"
    lesson_id: Optional[str] = None
    practice_set_id: Optional[str] = None
    next_lesson_id: Optional[str] = None
    reason: Optional[str] = None


class SuggestedAction(BaseModel):
    label: str
    intent: str


class LessonQuestionChoice(BaseModel):
    key: str
    text: str


class LessonQuestionRubric(BaseModel):
    must_include: List[str] = Field(default_factory=list)
    acceptable_answers: List[str] = Field(default_factory=list)
    target_structure: Optional[str] = None
    min_words: Optional[int] = None
    explanation_vi: Optional[str] = None


class LessonQuestion(BaseModel):
    question_id: str
    lesson_id: str
    type: Literal["multiple_choice_abcd", "write_sentence", "vocab_answer", "quick_definition"]
    prompt: str
    choices: List[LessonQuestionChoice] = Field(default_factory=list)
    correct_answer: str
    target_vocab: List[str] = Field(default_factory=list)
    rubric: LessonQuestionRubric = Field(default_factory=LessonQuestionRubric)
    difficulty: str

    @model_validator(mode="after")
    def validate_question_shape(self) -> "LessonQuestion":
        if self.type == "multiple_choice_abcd":
            if len(self.choices) != 4:
                raise ValueError("multiple_choice_abcd questions must include exactly four choices")
            choice_keys = [choice.key for choice in self.choices]
            if set(choice_keys) != {"A", "B", "C", "D"} or len(set(choice_keys)) != 4:
                raise ValueError("multiple_choice_abcd choices must use keys A, B, C, and D")
            if self.correct_answer not in {"A", "B", "C", "D"}:
                raise ValueError("correct_answer must match one of the multiple-choice keys")
        return self


class LessonPracticeSet(BaseModel):
    practice_set_id: str
    lesson_id: str
    total_questions: int
    question_counts: Dict[str, int]
    questions: List[LessonQuestion]

    @model_validator(mode="after")
    def validate_practice_set_shape(self) -> "LessonPracticeSet":
        if self.total_questions != len(self.questions):
            raise ValueError("total_questions must match the number of questions")

        actual_counts: Dict[str, int] = {}
        for question in self.questions:
            if question.lesson_id != self.lesson_id:
                raise ValueError("all questions must belong to the practice set lesson_id")
            actual_counts[question.type] = actual_counts.get(question.type, 0) + 1

        if sum(self.question_counts.values()) != self.total_questions:
            raise ValueError("question_counts must sum to total_questions")
        if self.question_counts != actual_counts:
            raise ValueError("question_counts must match generated question types")
        return self


class FlashcardBack(BaseModel):
    definition_vi: str
    example: str


class LessonFlashcard(BaseModel):
    card_id: str
    lesson_id: str
    word: str
    pos: str
    front: str
    back: FlashcardBack
    source: str = "mock"


class RegisterRequest(BaseModel):
    """Email + password registration. Carries onboarding fields too so the
    sign-up form is one shot (matches PRD US-N01: "email + password is
    enough"). Password must be at least 8 characters; bcrypt is applied
    server-side."""
    email: str
    password: str
    display_name: Optional[str] = None
    cefr_level: str
    industry: str
    learning_goals: List[str]
    preferred_study_time: Optional[str] = None

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if "@" not in v or "." not in v.split("@")[-1]:
            raise ValueError("invalid email")
        if len(v) > 255:
            raise ValueError("email too long")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if not isinstance(v, str) or len(v) < 8:
            raise ValueError("password must be at least 8 characters")
        if len(v) > 128:
            raise ValueError("password too long")
        return v

    @field_validator("cefr_level")
    @classmethod
    def validate_cefr_level(cls, v: str) -> str:
        valid_levels = ["A1", "A2", "B1", "B2", "C1"]
        if v not in valid_levels:
            raise ValueError(f"CEFR level must be one of {valid_levels}")
        return v

    @field_validator("learning_goals")
    @classmethod
    def validate_learning_goals(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("learning_goals must contain at least one goal")
        if len(v) > 10:
            raise ValueError("learning_goals must contain at most 10 goals")
        return v

    @field_validator("industry")
    @classmethod
    def validate_industry(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("industry must not be empty")
        if len(v) > 100:
            raise ValueError("industry must be at most 100 characters")
        return v


class LoginRequest(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def lower_email(cls, v: str) -> str:
        return (v or "").strip().lower()

    @field_validator("password")
    @classmethod
    def non_empty_password(cls, v: str) -> str:
        if not v:
            raise ValueError("password required")
        return v
