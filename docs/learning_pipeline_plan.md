# Learning Pipeline Plan

## Goal

Build a lesson-centered learning pipeline where a learner moves through one lesson at a time:

1. Read the lesson markdown from `data/curriculum_skeleton/<CEFR>/<lesson>.md`.
2. Complete generated practice questions based on that lesson.
3. Review lesson vocabulary as flashcards.
4. Mark the lesson complete and move to the next lesson.

The first version should work before the real vocabulary database and personal learner profile services are complete. Use mock learner data and mock lesson vocabulary behind replaceable service interfaces.

## Current Repo Context

- Lessons already exist as markdown and YAML pairs under `data/curriculum_skeleton`.
- Chat orchestration lives in `src/backend/app/services/langgraph_orchestrator.py`.
- Current chat intent labels are `PRACTICE`, `QUICK_QA`, and `PROGRESS`, with extra graph support for `CONTEXT_INJECT` and `MORNING_BRIEF`.
- Vocabulary and SM-2 review already exist in:
  - `src/backend/app/models/vocabulary.py`
  - `src/backend/app/api/v1/vocabulary.py`
  - `src/backend/app/api/v1/review.py`
  - `src/backend/app/services/sm2_scheduler.py`

## MVP User Flow

### Default Lesson Flow

```text
START_LEARNING
  -> LESSON_READING
  -> PRACTICE
  -> FLASHCARD
  -> LESSON_COMPLETE
  -> NEXT_LESSON
```

### Flow Rules

- If the user says "let's start learning", "start learning", "hoc bai moi", or similar, route to the first incomplete lesson for the user's CEFR level.
- If there is no saved progress, start from the first lesson sorted by folder and filename, for example `data/curriculum_skeleton/A2/01_A2_present_simple_be.md`.
- If the user is reading a lesson and asks for practice, move to practice for that same lesson.
- If the user is reading or practicing a lesson and asks for flashcards, route directly to the flashcard step for the active lesson.
- If the user completes flashcards, mark the lesson complete and offer the next lesson.
- If the user asks a standalone grammar or vocabulary question, keep using the existing `QUICK_QA` path unless the message explicitly mentions the active lesson flow.

## Learning State

Add a learning state object that can live in Redis session state first, then move to PostgreSQL once persistence rules are finalized.

```json
{
  "active_lesson_id": "A2_present_simple_be",
  "active_lesson_path": "data/curriculum_skeleton/A2/01_A2_present_simple_be.md",
  "current_step": "LESSON_READING",
  "practice_set_id": null,
  "practice_completed": false,
  "flashcards_completed": false,
  "completed_lessons": [],
  "last_transition": {
    "from_step": "NONE",
    "to_step": "LESSON_READING",
    "reason": "start_learning",
    "created_at": "2026-05-13T00:00:00Z"
  },
  "latest_practice_result": null
}
```

Recommended enum values for `current_step`:

- `NONE`
- `LESSON_READING`
- `PRACTICE`
- `FLASHCARD`
- `LESSON_COMPLETE`

The agent must read this state before responding. Feedback should match the current step and the most recent transition instead of giving a generic chat answer.

Examples:

- After `QUESTIONS_SUBMITTED` with `passed = true`: "Congrats, you finished this practice set. Do you want to go to flashcards, keep practicing, or open the next lesson later?"
- After `QUESTIONS_SUBMITTED` with `passed = false`: "Good attempt. You got 7/12, so I suggest one more short practice round before flashcards. Want to retry the weak question types?"
- During `LESSON_READING`: "You are reading the lesson now. When you are ready, I can open practice questions for this lesson."
- During `FLASHCARD`: "You are reviewing this lesson's vocabulary. Finish these cards, then you can complete the lesson."

## Agent Response And UI Directive Contract

Every learning-flow response should include both a learner-facing message and a machine-readable UI directive.

```json
{
  "agent_message": "Congrats, you finished this practice set. Do you want to go to flashcards or keep practicing?",
  "learning_state": {
    "active_lesson_id": "A2_present_simple_be",
    "current_step": "PRACTICE"
  },
  "ui_directive": {
    "screen": "PRACTICE_RESULT",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "practice_set_id": "A2_present_simple_be-20260513-001",
    "reason": "questions_submitted"
  },
  "suggested_actions": [
    {"label": "Go to flashcards", "intent": "LESSON_FLASHCARD"},
    {"label": "Keep practicing", "intent": "LESSON_PRACTICE"},
    {"label": "Read lesson again", "intent": "READ_LESSON"}
  ]
}
```

`ui_directive.screen` enum values:

- `LESSON_READER`
- `PRACTICE_RUNNER`
- `PRACTICE_RESULT`
- `FLASHCARD_RUNNER`
- `LESSON_COMPLETE`
- `CHAT`

Frontend rule: whenever the backend returns `ui_directive.action = "OPEN"`, the frontend should open the matching window immediately. The chat message can still be shown, but navigation should be driven by `ui_directive`, not by parsing the text.

## Backend Services

### `lesson_catalog.py`

Responsible for reading lesson files from `data/curriculum_skeleton`.

Functions:

```python
def list_lessons(cefr_level: str | None = None) -> list[LessonSummary]
def get_lesson(lesson_id: str) -> LessonContent
def get_next_lesson(user_id: str, cefr_level: str) -> LessonSummary
```

Notes:

- Use YAML metadata as the machine-readable source when available.
- Use markdown as the learner-facing lesson content.
- Sorting should follow the numeric filename prefix, not lexical topic name.

### `lesson_vocabulary_provider.py`

Temporary interface for lesson vocabulary. Start with mock data and later switch to the real vocabulary database.

Functions:

```python
def get_lesson_vocabulary(lesson_id: str, learner: LearnerProfile) -> list[LessonVocabularyItem]
```

Mock vocabulary item shape:

```json
{
  "word_id": "mock-A2-present-simple-be-001",
  "word": "am",
  "pos": "verb",
  "definition_vi": "la, thi, o dang ngoi thu nhat so it",
  "example": "I am a project assistant.",
  "source": "mock"
}
```

Later replacement:

- Query `Vocabulary` and `UserVocabulary`.
- Filter by lesson metadata, CEFR level, industry, and unseen or due words.
- Keep the response shape stable so the frontend does not change.

### `learner_profile_provider.py`

Temporary interface for personalization. Start with mock values and later wire to `User`.

Mock profile:

```json
{
  "user_id": "mock-user",
  "cefr_level": "A2",
  "industry": "business",
  "learning_goals": ["daily work communication"],
  "weak_points": ["articles", "verb forms"],
  "preferred_language": "vi"
}
```

### `lesson_question_generator.py`

Creates a fixed practice set for a lesson.

Function:

```python
async def create_lesson_questions(
    learner: LearnerProfile,
    lesson: LessonContent,
    vocabulary: list[LessonVocabularyItem],
    question_plan: QuestionPlan = DEFAULT_QUESTION_PLAN,
) -> LessonPracticeSet:
```

Inputs:

- Personal learner information.
- Lesson markdown content.
- Lesson metadata from YAML when available.
- Vocabulary for that lesson.
- Fixed question plan.

Output:

- A schema-validated practice set with deterministic question IDs and stable type names.
- Store the generated set in Redis by `practice_set_id` for the session. Later this can move to a `lesson_practice_attempt` table.

## Practice Question Contract

For MVP, each lesson generates exactly 12 questions.

| Type | Count | Frontend behavior | Autograde |
|---|---:|---|---|
| `multiple_choice_abcd` | 5 | Show four options A-D | Exact option match |
| `write_sentence` | 3 | Textarea answer | LLM/rubric check |
| `vocab_answer` | 2 | Short text input for target word or phrase | Normalized exact/fuzzy match |
| `quick_definition` | 2 | Short text input for meaning/definition | Keyword/rubric check |

Total: 12 questions per lesson.

### Question Schema

```json
{
  "question_id": "A2_present_simple_be-q001",
  "lesson_id": "A2_present_simple_be",
  "type": "multiple_choice_abcd",
  "prompt": "Choose the correct sentence.",
  "choices": [
    {"key": "A", "text": "I am a manager."},
    {"key": "B", "text": "I is a manager."},
    {"key": "C", "text": "I are a manager."},
    {"key": "D", "text": "I be a manager."}
  ],
  "correct_answer": "A",
  "target_vocab": [],
  "rubric": {
    "must_include": [],
    "acceptable_answers": ["A"],
    "explanation_vi": "Sau I dung am."
  },
  "difficulty": "A2"
}
```

For `write_sentence`, `choices` should be empty and `rubric` should include:

```json
{
  "must_include": ["am"],
  "target_structure": "present simple be",
  "min_words": 4,
  "explanation_vi": "Cau can dung dung dang cua be va co y nghia ro rang."
}
```

For `vocab_answer`, the prompt asks the learner to produce a word or phrase:

```json
{
  "type": "vocab_answer",
  "prompt": "Complete the sentence: I ___ responsible for scheduling meetings.",
  "correct_answer": "am",
  "target_vocab": ["am"]
}
```

For `quick_definition`, the prompt asks for a short meaning:

```json
{
  "type": "quick_definition",
  "prompt": "What does 'assistant' mean in this lesson context?",
  "correct_answer": "tro ly",
  "target_vocab": ["assistant"],
  "rubric": {
    "acceptable_answers": ["tro ly", "nguoi ho tro cong viec"],
    "explanation_vi": "Assistant la nguoi ho tro cong viec cho mot ca nhan hoac nhom."
  }
}
```

## Flashcard Contract

For MVP, return 5 flashcards per lesson.

Source priority:

1. Real vocabulary database if available.
2. Mock lesson vocabulary.
3. Extract candidate terms from YAML `recommended_vocab` or markdown headings as fallback.

Flashcard schema:

```json
{
  "card_id": "mock-A2-present-simple-be-001",
  "lesson_id": "A2_present_simple_be",
  "word": "assistant",
  "pos": "noun",
  "front": "assistant",
  "back": {
    "definition_vi": "tro ly",
    "example": "I am an assistant in the sales team."
  },
  "source": "mock"
}
```

Mock flashcards should not permanently update `UserVocabulary` unless the word has a real `word_id`. Keep mock review completion in session state only.

## API Plan

Add `src/backend/app/api/v1/learning.py`.

Also extend the existing `ChatResponse` schema in `src/backend/app/models/schemas.py` so chat-detected learning transitions can drive the frontend:

```python
class ChatResponse(BaseModel):
    response: str
    hint_count: int
    intent: str
    session_id: str | None = None
    dna_delta: dict | None = None
    recommended_review: list[dict] | None = None
    cefr_step: int | None = None
    learning_state: dict | None = None
    ui_directive: dict | None = None
    suggested_actions: list[dict] | None = None
```

For chat responses, `response` and `agent_message` can carry the same text in MVP. Longer term, prefer `agent_message` for learning flow endpoints and keep `response` for the chat bubble.

### `GET /api/v1/learning/current`

Returns the active learning state and active lesson if one exists.

Query:

```text
user_id=<uuid>
```

Response:

```json
{
  "state": {
    "active_lesson_id": "A2_present_simple_be",
    "current_step": "LESSON_READING"
  },
  "lesson": {
    "lesson_id": "A2_present_simple_be",
    "title": "Present Simple with be",
    "cefr_level": "A2",
    "markdown": "..."
  },
  "agent_message": "You are reading this lesson now. When you are ready, I can open practice questions.",
  "ui_directive": {
    "screen": "LESSON_READER",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "reason": "current_state"
  }
}
```

### `POST /api/v1/learning/start`

Starts or resumes the next lesson.

Body:

```json
{
  "user_id": "uuid",
  "lesson_id": null
}
```

If `lesson_id` is null, use the first incomplete lesson.

### `POST /api/v1/learning/{lesson_id}/questions`

Generates or returns the current 12-question practice set.

Response:

```json
{
  "practice_set_id": "A2_present_simple_be-20260513-001",
  "lesson_id": "A2_present_simple_be",
  "total_questions": 12,
  "question_counts": {
    "multiple_choice_abcd": 5,
    "write_sentence": 3,
    "vocab_answer": 2,
    "quick_definition": 2
  },
  "questions": [],
  "agent_message": "Here are 12 practice questions for this lesson.",
  "ui_directive": {
    "screen": "PRACTICE_RUNNER",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "practice_set_id": "A2_present_simple_be-20260513-001",
    "reason": "practice_started"
  }
}
```

### `POST /api/v1/learning/{lesson_id}/questions/submit`

Submits answers for a practice set.

Body:

```json
{
  "user_id": "uuid",
  "practice_set_id": "A2_present_simple_be-20260513-001",
  "answers": [
    {"question_id": "A2_present_simple_be-q001", "answer": "A"}
  ]
}
```

Response:

```json
{
  "score": 9,
  "total": 12,
  "accuracy": 0.75,
  "passed": true,
  "feedback": [],
  "next_step": "FLASHCARD",
  "agent_message": "Congrats, you finished this practice set. Do you want to go to flashcards or keep practicing?",
  "ui_directive": {
    "screen": "PRACTICE_RESULT",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "practice_set_id": "A2_present_simple_be-20260513-001",
    "reason": "questions_submitted"
  },
  "suggested_actions": [
    {"label": "Go to flashcards", "intent": "LESSON_FLASHCARD"},
    {"label": "Keep practicing", "intent": "LESSON_PRACTICE"},
    {"label": "Read lesson again", "intent": "READ_LESSON"}
  ]
}
```

Default pass threshold: 70 percent.

### `GET /api/v1/learning/{lesson_id}/flashcards`

Returns 5 lesson flashcards from real DB or mock provider.

Response:

```json
{
  "lesson_id": "A2_present_simple_be",
  "total_cards": 5,
  "cards": [],
  "agent_message": "You are reviewing this lesson's vocabulary. Finish these cards, then you can complete the lesson.",
  "ui_directive": {
    "screen": "FLASHCARD_RUNNER",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "reason": "flashcards_started"
  }
}
```

### `POST /api/v1/learning/{lesson_id}/complete`

Marks flashcards done and completes the lesson.

Response:

```json
{
  "completed_lesson_id": "A2_present_simple_be",
  "next_lesson_id": "A2_articles",
  "next_step": "LESSON_READING",
  "agent_message": "Lesson complete. Do you want to open the next lesson now?",
  "ui_directive": {
    "screen": "LESSON_COMPLETE",
    "action": "OPEN",
    "lesson_id": "A2_present_simple_be",
    "next_lesson_id": "A2_articles",
    "reason": "lesson_completed"
  }
}
```

## LangGraph Orchestration Changes

Keep the existing chat intents, but add a second classification layer for learning flow. This avoids breaking code that already expects `PRACTICE`, `QUICK_QA`, or `PROGRESS`.

Add fields to `ChatState`:

```python
learning_intent: Literal[
    "NONE",
    "START_LEARNING",
    "READ_LESSON",
    "LESSON_PRACTICE",
    "LESSON_FLASHCARD",
    "NEXT_LESSON",
    "LESSON_STATUS",
]
learning_state: dict[str, Any]
active_lesson: dict[str, Any] | None
agent_message: str
ui_directive: dict[str, Any] | None
suggested_actions: list[dict[str, str]]
```

Add or modify graph nodes:

```text
mood_adapter
  -> input_guard
  -> intent_router
  -> learning_intent_router
  -> learning_state_loader
  -> learning_action_router
  -> learning_response_composer
  -> memory_retrieval
  -> context_analyzer
  -> scaffolding
  -> difficulty_tuner
  -> memory_writer
  -> output_guard
```

### Learning Intent Router

Classification labels:

- `START_LEARNING`: "let's start learning", "start lesson", "hoc bai", "bat dau hoc".
- `READ_LESSON`: "show me the lesson", "read lesson", "open lesson".
- `LESSON_PRACTICE`: "practice this lesson", "give me exercises", answer submissions during active practice.
- `LESSON_FLASHCARD`: "flashcard", "review vocab", "on tu vung".
- `NEXT_LESSON`: "next lesson", "continue", "bai tiep theo".
- `LESSON_STATUS`: "where am I", "current lesson", "learning progress in this lesson".
- `NONE`: no lesson-flow request.

Routing rules:

- `START_LEARNING` should create or resume `learning_state` and return the markdown lesson.
- `LESSON_PRACTICE` should call `lesson_question_generator`.
- `LESSON_FLASHCARD` should call `lesson_vocabulary_provider`.
- `NEXT_LESSON` should only advance after `current_step == LESSON_COMPLETE`, unless the user explicitly skips.
- `NONE` falls back to the current chat behavior.

### Learning Response Composer

Add a node that turns learning state changes into consistent feedback and UI routing.

Inputs:

- `learning_state`
- `learning_intent`
- latest practice result, if any
- learner profile and mood config

Outputs:

- `agent_message`
- `ui_directive`
- `suggested_actions`

Response rules:

- Do not give generic encouragement without referencing the actual state or result.
- After practice submission, mention score and next options.
- After lesson completion, ask whether to open the next lesson.
- If the user jumps to flashcards, acknowledge the jump and open `FLASHCARD_RUNNER`.
- If the user asks for a state already active, return the same `ui_directive.screen` and a short state-aware message.
- If no learning intent is detected, leave `ui_directive = null` and continue the existing chat path.

## Frontend Integration Notes

The frontend can build around a simple step machine:

```text
LessonReader -> PracticeRunner -> FlashcardRunner -> CompletionPrompt
```

The frontend should also listen for `ui_directive` on chat responses and learning endpoint responses.

Screen mapping:

| `current_step` or `ui_directive.screen` | Frontend window |
|---|---|
| `LESSON_READING` / `LESSON_READER` | Lesson markdown reader |
| `PRACTICE` / `PRACTICE_RUNNER` | Practice question runner |
| `PRACTICE_RESULT` | Practice result and suggested actions |
| `FLASHCARD` / `FLASHCARD_RUNNER` | Lesson flashcard window |
| `LESSON_COMPLETE` | Completion prompt with next lesson CTA |
| `CHAT` | Normal chat view |

Navigation rules:

- If `ui_directive.action = "OPEN"`, open the mapped window immediately.
- If a chat message triggers `START_LEARNING`, open `LESSON_READER`.
- If a chat message triggers `LESSON_PRACTICE`, open `PRACTICE_RUNNER`.
- If a chat message triggers `LESSON_FLASHCARD`, open `FLASHCARD_RUNNER`.
- If a practice submit response returns `PRACTICE_RESULT`, open the result window before asking the learner what they want next.
- If a completion response returns `LESSON_COMPLETE`, open the completion prompt and show the next lesson action.
- Never parse `agent_message` to decide navigation. Use only `ui_directive`.

Important stable values:

- Every practice set has exactly 12 questions.
- Question type enum values are fixed.
- Flashcards return exactly 5 cards for MVP unless a lesson has fewer than 5 available vocab items; mock provider should still fill to 5.
- Practice pass threshold is 70 percent.
- `ui_directive` tells the frontend what screen to show after each backend action.
- `agent_message` is only learner-facing copy.

## Persistence Plan

MVP:

- Store active learning state in Redis session.
- Store generated practice set in Redis by `practice_set_id`.
- Do not store mock flashcard words in `UserVocabulary`.

Future database tables:

```text
lesson_progress
  user_id
  lesson_id
  current_step
  status
  started_at
  completed_at
  last_activity_at

lesson_practice_attempt
  attempt_id
  user_id
  lesson_id
  practice_set_id
  score
  total
  accuracy
  passed
  answers_json
  created_at
```

## Testing Plan

Unit tests:

- `lesson_catalog` sorts lessons by CEFR folder and numeric prefix.
- `lesson_vocabulary_provider` returns 5 mock vocabulary items when DB data is unavailable.
- `lesson_question_generator` always returns 12 questions with the required type counts.
- Question schema validation rejects missing choices for `multiple_choice_abcd`.
- Learning intent router detects start, practice, flashcard, and next-lesson requests.
- Learning response composer returns state-aware `agent_message` for reading, practice result, flashcard, and lesson-complete states.
- UI directive mapper returns the correct screen for every `current_step`.

Integration tests:

- New user starts learning and receives first lesson markdown.
- User asks for practice and receives 12 questions.
- User submits 12 answers and receives score, `agent_message`, suggested actions, and `ui_directive.screen = PRACTICE_RESULT`.
- User asks for flashcards during lesson reading and receives 5 cards plus `ui_directive.screen = FLASHCARD_RUNNER`.
- User completes flashcards and receives next lesson ID plus `ui_directive.screen = LESSON_COMPLETE`.
- Chat message "let's start learning" returns `ui_directive.screen = LESSON_READER`.
- Chat message "I want flashcards now" during an active lesson returns `ui_directive.screen = FLASHCARD_RUNNER`.
- Existing `QUICK_QA`, `PRACTICE`, and `PROGRESS` behavior still works when no learning-flow intent is detected.

## Implementation Phases

### Phase 1: Lesson and Mock Data Foundation

- Add `lesson_catalog.py`.
- Add `lesson_vocabulary_provider.py` with mock fallback.
- Add `learner_profile_provider.py` with mock fallback.
- Add Pydantic schemas for lesson, question, practice set, flashcard, and learning state.

### Phase 2: Practice Generation

- Add `lesson_question_generator.py`.
- Enforce the fixed 12-question plan.
- Add JSON schema validation and deterministic fallback questions if the LLM returns invalid output.
- Add unit tests for counts and schema.

### Phase 3: Learning API

- Add `api/v1/learning.py`.
- Register the router in `app/main.py`.
- Persist learning state and practice sets in Redis.
- Add integration tests for start, questions, submit, flashcards, and complete.

### Phase 4: LangGraph Integration

- Extend `ChatState` with learning fields.
- Add `learning_intent_router`, `learning_state_loader`, and `learning_action_router`.
- Add `learning_response_composer` for state-aware feedback, encouragement, suggested actions, and UI directives.
- Keep existing chat behavior as fallback.
- Add tests for messages like "let's start learning" and "I want flashcards now".

### Phase 5: Real Vocabulary Integration

- Replace mock vocabulary provider internals with real DB queries.
- Keep the same output schema.
- Decide whether lesson flashcards should update SM-2 immediately or only after explicit learner rating.

## Assumptions

- The user should be allowed to request flashcards before finishing practice.
- The default pass threshold for practice is 70 percent.
- The first implementation can use Redis for learning state and generated practice sets.
- Mock flashcards should not update SM-2 database rows.
- UI copy can be Vietnamese, but API enum names and schemas should stay English and stable.

## Open Questions

1. Should practice be mandatory before a lesson can be completed, or can the learner skip directly to flashcards and next lesson? ->The learner can skip easily if they want.
2. Should the pass threshold stay fixed at 70 percent, or vary by CEFR level and learner mood? -> Stay
3. Should generated questions be regenerated every attempt, or should the same practice set be reused until passed? -> regenerated every attempts.
4. Should flashcard completion require SM-2 quality ratings, or is a simple "reviewed all cards" action enough for the lesson flow? -> Currenly just make it simple
5. Which language should generated feedback use by default: Vietnamese, English, or based on learner preference? -> Vietnamese, everything's here should go for Vietnamese
