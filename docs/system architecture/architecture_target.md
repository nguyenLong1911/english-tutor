# Kien truc muc tieu he thong - Agentic Language Tutor

Tai lieu nay duoc tao dua tren `docs/project requirements/PRD_v2.md` va tuan thu yeu cau dau ra trong `docs/system architecture/requirements.md`: tech stack, system architecture diagram, database schema, auth flow va API spec don gian.

## 1. Muc tieu kien truc

Agentic Language Tutor la web app hoc ngoai ngu co tri nho dai han cho nguoi di lam ban ron. Kien truc muc tieu can giai quyet 5 yeu cau chinh:

- Duy tri persistent memory xuyen phien hoc bang Mem0/Qdrant.
- Dieu phoi luong gia su bang LangGraph thay vi chat endpoint don thuan.
- Ca nhan hoa bai hoc theo CEFR level, nganh nghe, loi sai, mood va lich su on tap.
- Ho tro micro-learning: mo app la co bai on/nghiem vu ngan, luu tien do tu dong.
- Theo doi chi phi, latency, error va xoa du lieu ca nhan theo yeu cau.

## 2. Tech stack muc tieu

| Tang | Cong nghe | Vai tro | Ghi chu |
|---|---|---|---|
| Frontend | React + Vite + TailwindCSS | Web app mobile-responsive: onboarding, chat, review, dashboard, settings | Repo hien tai dung `src/frontend` |
| Backend API | FastAPI | REST API, auth, session, rate limit, orchestration entrypoint | Repo hien tai dung `src/backend/app` |
| AI orchestration | LangGraph | Dieu phoi mood, guardrails, intent, memory, scaffolding, memory writer | Mo rong tu 4-node PRD thanh graph co guardrails va learning flow |
| LLM provider | Gemini/Groq/OpenAI/Claude fallback | Tao phan hoi, scaffolding, phan tich context, sinh cau hoi | Uu tien provider co cost/latency phu hop alpha |
| Memory layer | Mem0 + Qdrant | Semantic memory va vector search cho facts ca nhan hoa | Target 1,000-2,000 facts/user, retrieval P95 < 1s |
| Database | PostgreSQL | User profile, auth, session logs, review schedule, analytics, audit | Quan he ro, phu hop RBAC va bao cao |
| Cache/rate limit/session | Redis | Rate limit 50 queries/user/day, session restore, short-lived cache | Giam tai DB/LLM |
| Scheduler | APScheduler/background workers | Morning brief, weekly email, memory outbox flush, metrics snapshot | Co the tach worker sau alpha |
| Observability | Sentry + structured logs + metrics table | Error tracking, trace id, latency, token cost | Can co tu Sprint 1 |
| Deployment | Vercel/Static host FE + Railway/AWS/GCP BE | Deploy nhanh cho alpha | Docker Compose dung cho local/dev |

## 3. System architecture

### 3.1 Component diagram

```mermaid
flowchart LR
    U["Learner/Admin"] --> FE["Frontend Web App<br/>React + Vite"]
    FE -->|HTTPS JSON API| API["FastAPI Backend<br/>/api/v1"]

    API --> AUTH["Auth & RBAC<br/>JWT cookie, Google OAuth"]
    API --> RL["Rate Limit Middleware<br/>Redis"]
    API --> ORCH["LangGraph Tutor Pipeline"]
    API --> SQL[("PostgreSQL<br/>profiles, reviews, logs, analytics")]
    API --> REDIS[("Redis<br/>rate limit, session cache")]

    ORCH --> GUARD["Input/Output Guardrails"]
    ORCH --> MEMR["Memory Retrieval"]
    MEMR --> MEM0["Mem0 Client"]
    MEM0 --> QDRANT[("Qdrant Vector DB<br/>semantic facts")]

    ORCH --> CORPUS["Corpus Retrieval<br/>curriculum, vocab, error bank"]
    CORPUS --> QDRANT
    CORPUS --> SQL

    ORCH --> LLM["LLM Provider Chain<br/>Gemini/Groq/OpenAI/Claude"]
    ORCH --> SCAF["Scaffolding Engine<br/>hints before answer"]
    ORCH --> MEMW["Memory Writer / Outbox"]
    MEMW --> SQL
    MEMW --> MEM0

    API --> SCHED["Scheduler / Workers"]
    SCHED --> SQL
    SCHED --> MEM0
    SCHED --> EMAIL["Email Provider<br/>weekly/reset/brief"]

    API --> OBS["Sentry + Logs + Metrics"]
    ORCH --> OBS
```

### 3.2 Chat/AI pipeline

```mermaid
flowchart TD
    A["POST /api/v1/chat"] --> B["mood_adapter<br/>derive session length, tone, difficulty"]
    B --> C["input_guard<br/>prompt injection, unsafe input"]
    C -->|blocked| Z["output_guard -> safe response"]
    C -->|ok| D["intent_router<br/>ENGLISH_RAG / learning flow"]
    D --> E["learning_intent_router<br/>lesson, practice, flashcard, status"]
    E --> F["learning_state_loader"]
    F --> G["learning_action_router"]
    G --> H["learning_response_composer"]
    H -->|learning request| Y["memory_writer<br/>queue facts if any"]
    H -->|chat request| I["memory_retrieval<br/>Mem0 top-K facts"]
    I --> J["context_analyzer<br/>pasted work text -> terms"]
    J --> K["scaffolding<br/>detect error, give hints, answer"]
    K --> L["difficulty_tuner<br/>CEFR step, DNA delta, review recs"]
    L --> Y
    Y --> Z
    Z --> M["ChatResponse<br/>response, hint_count, ui_directive, suggested_actions"]
```

### 3.3 Data flow frontend-backend-AI-database

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend
    participant API as FastAPI
    participant Redis
    participant DB as PostgreSQL
    participant Graph as LangGraph
    participant Mem0
    participant LLM

    User->>FE: Nhap cau hoi / cau tra loi / pasted context
    FE->>API: POST /api/v1/chat
    API->>Redis: Check rate limit + session cache
    API->>DB: Load user_profile + recent session facts
    API->>Graph: Run tutor state graph
    Graph->>Mem0: Search top-K personal memories
    Graph->>LLM: Build prompt with profile + memory + context
    LLM-->>Graph: Tutor response + hints + extracted facts
    Graph->>DB: Write session_log, error events, review updates
    Graph->>Mem0: Queue/upsert long-term facts
    API-->>FE: ChatResponse + UI directive
    FE-->>User: Render chat, lesson, review or dashboard update
```

## 4. Database schema muc tieu

PostgreSQL la source of truth cho user/account, tien do hoc, lich on tap, observability va audit. Mem0/Qdrant luu semantic facts dai han; khong thay the relational DB.

### 4.1 ER diagram

```mermaid
erDiagram
    USER_PROFILE {
        uuid user_id PK
        string email UK
        string password_hash
        string display_name
        string cefr_level
        string industry
        array learning_goals
        string preferred_study_time
        string role
        string timezone
        string mood_default
        text agent_opening_message
        datetime created_at
        datetime updated_at
    }

    SESSION_LOG {
        uuid id PK
        uuid user_id FK
        datetime created_at
        string intent
        string provider
        string model
        int tokens_in
        int tokens_out
        float cost_usd
        int latency_ms
        bool was_correct
        int hint_count
    }

    VOCABULARY {
        int word_id PK
        string word
        string pos
        string cefr_level
        text definition_vi
        text example
        array industry_tags
        array confusion_with
        int frequency_rank
    }

    USER_VOCABULARY {
        uuid user_id PK,FK
        int word_id PK,FK
        float ease_factor
        int interval_days
        int repetitions
        date next_review
        date brief_skip_until
        datetime first_seen_at
        datetime last_reviewed_at
        int total_reviews
        bool mastered
    }

    USER_ERROR_EVENT {
        uuid id PK
        uuid user_id FK
        string source
        text original_text
        text corrected_text
        string error_type
        string error_dimension
        string error_subtype
        text error_pattern
        string normalized_error_pattern
        text explanation_vi
        string cefr_level
        string industry
        float confidence
        jsonb source_metadata
        datetime created_at
    }

    USER_FLASHCARD {
        uuid id PK
        uuid user_id FK
        uuid error_event_id FK
        string card_type
        text front
        text back
        text cloze_text
        text explanation_vi
        string error_type
        string normalized_error_pattern
        string source
        bool active
        datetime created_at
    }

    USER_FLASHCARD_REVIEW {
        uuid user_id PK,FK
        uuid flashcard_id PK,FK
        float ease_factor
        int interval_days
        int repetitions
        date next_review
        datetime first_seen_at
        datetime last_reviewed_at
        int total_reviews
        bool mastered
    }

    LESSON_PROGRESS {
        uuid user_id PK,FK
        string lesson_id PK
        string status
        bool is_current
        string active_lesson_path
        string practice_set_id
        bool practice_completed
        bool flashcards_completed
        int latest_score
        int latest_total
        float latest_accuracy
        jsonb latest_practice_result
        datetime started_at
        datetime completed_at
        datetime updated_at
    }

    MOOD_LOG {
        uuid id PK
        uuid user_id FK
        string mood
        jsonb derived_config
        datetime created_at
    }

    CONTEXT_ARTIFACT {
        uuid id PK
        uuid user_id FK
        string text_hash
        jsonb extracted_terms
        datetime created_at
    }

    ERROR_DNA_SNAPSHOT {
        uuid id PK
        uuid user_id FK
        date week_start
        jsonb dimensions
        datetime created_at
    }

    MEMORY_FACT_OUTBOX {
        uuid id PK
        uuid user_id FK
        text content
        jsonb fact_metadata
        string status
        int retry_count
        datetime scheduled_at
        datetime created_at
        datetime updated_at
        datetime flushed_at
        jsonb mem0_result
        text last_error
    }

    METRICS_LOG {
        uuid id PK
        datetime captured_at
        int total_users
        int total_reviews
        float avg_reviews_per_user
        int mastered_words
        int vocabulary_size
        int avg_token_per_session
        float cost_today
        float p95_latency_ms
        string snapshot_source
    }

    DELETE_REQUEST {
        uuid id PK
        uuid user_id
        datetime requested_at
        datetime completed_at
        string status
        int duration_ms
    }

    EMAIL_OUTBOX {
        uuid id PK
        uuid user_id FK
        string kind
        jsonb payload
        string status
        datetime scheduled_at
        datetime sent_at
        text last_error
    }

    ERROR_BANK {
        string error_id PK
        string category
        text error_pattern
        text incorrect_example
        text correct_example
        text explanation_vi
        text scaffolding_hint
        float importance_score
        string frequency
        string cefr_level
        array tags
        float confidence_score
        string source
    }

    PEDAGOGICAL_PROMPT {
        string prompt_id PK
        text learner_situation
        array scaffolding_steps
        array socratic_questions
        text expected_outcome
        string target_skill
        string cefr_level
        text affective_filter_strategy
        array tags
    }

    USER_PROFILE ||--o{ SESSION_LOG : has
    USER_PROFILE ||--o{ USER_VOCABULARY : reviews
    VOCABULARY ||--o{ USER_VOCABULARY : scheduled_as
    USER_PROFILE ||--o{ USER_ERROR_EVENT : makes
    USER_ERROR_EVENT ||--o{ USER_FLASHCARD : creates
    USER_PROFILE ||--o{ USER_FLASHCARD : owns
    USER_FLASHCARD ||--o{ USER_FLASHCARD_REVIEW : scheduled_as
    USER_PROFILE ||--o{ LESSON_PROGRESS : progresses
    USER_PROFILE ||--o{ MOOD_LOG : logs
    USER_PROFILE ||--o{ CONTEXT_ARTIFACT : submits
    USER_PROFILE ||--o{ ERROR_DNA_SNAPSHOT : aggregates
    USER_PROFILE ||--o{ MEMORY_FACT_OUTBOX : queues
    USER_PROFILE ||--o{ EMAIL_OUTBOX : receives
```

### 4.2 Mem0 fact schema

Mem0 facts can duoc gan metadata de truy xuat nhanh, xoa theo user va nen memory khi vuot nguong.

```json
{
  "user_id": "uuid",
  "fact_type": "error_pattern | vocabulary | mood_pattern | industry_vocab | skill_level | topic_preference",
  "content": "User confuses 'affect' with 'effect' in marketing contexts",
  "metadata": {
    "source_session": "session_id",
    "cefr_level": "B1",
    "industry": "marketing",
    "importance_score": 0.85,
    "review_count": 3,
    "last_updated": "2026-05-15"
  }
}
```

### 4.3 Du lieu chinh theo use case

| Use case | Bang/Memory lien quan |
|---|---|
| Onboarding | `user_profile`, initial Mem0 facts |
| Chat gia su | `session_log`, `user_error_event`, `memory_fact_outbox`, Mem0 |
| Spaced repetition | `user_vocabulary`, `user_flashcard_review`, `vocabulary`, `user_flashcard` |
| Error DNA | `user_error_event`, `error_dna_snapshot`, `error_bank` |
| Mood-adaptive session | `mood_log`, Mem0 `mood_pattern` |
| Context injection | `context_artifact`, Mem0 `industry_vocab` |
| Admin cost dashboard | `session_log`, `metrics_log` |
| Delete my data | `delete_request`, cascade DB delete, Mem0 delete by user |

## 5. Auth flow va phan quyen

### 5.1 Roles

| Role | Quyen |
|---|---|
| `user` | Onboarding, chat, review, dashboard ca nhan, mood, context injection, xoa du lieu cua minh |
| `admin` | Tat ca quyen user + admin dashboard, metrics, memory status/flush, user role update, GDPR audit |

### 5.2 Email/password login

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend
    participant API as FastAPI
    participant DB as PostgreSQL

    User->>FE: Dang ky email + password + onboarding fields
    FE->>API: POST /api/v1/register
    API->>API: Validate email/password/onboarding
    API->>API: Hash password
    API->>DB: Create user_profile(role=user)
    API-->>FE: Set JWT cookie + UserOut

    User->>FE: Dang nhap
    FE->>API: POST /api/v1/login
    API->>DB: Find user by email
    API->>API: Verify password hash
    API-->>FE: Set JWT cookie + UserOut

    FE->>API: GET /api/v1/me
    API->>API: Validate JWT cookie
    API->>DB: Load user profile
    API-->>FE: Current user + role
```

### 5.3 Google OAuth

```mermaid
sequenceDiagram
    participant User
    participant FE as Frontend
    participant API as FastAPI
    participant Google
    participant DB as PostgreSQL

    User->>FE: Chon "Continue with Google"
    FE->>API: GET /api/v1/start
    API-->>FE: Google authorization URL
    FE->>Google: Redirect user
    Google-->>FE: Authorization code
    FE->>API: POST /api/v1/callback
    API->>Google: Exchange code, verify identity
    API->>DB: Create/update user_profile
    API-->>FE: Set JWT cookie + UserOut
```

### 5.4 Admin authorization

```mermaid
flowchart TD
    A["Request admin endpoint"] --> B["Read JWT/session"]
    B --> C{"Authenticated?"}
    C -->|No| D["401 Unauthorized"]
    C -->|Yes| E["Load user_profile.role"]
    E --> F{"role == admin?"}
    F -->|No| G["403 Forbidden"]
    F -->|Yes| H["Execute admin action"]
```

## 6. API spec don gian

Tat ca API chinh nam duoi prefix `/api/v1`. Response loi nen co shape chung:

```json
{
  "error": "Request failed",
  "detail": "Human-readable message",
  "trace_id": "request-trace-id"
}
```

### 6.1 Auth va user

| Method | Endpoint | Auth | Mo ta |
|---|---|---|---|
| POST | `/register` | Public | Tao user bang email/password + onboarding |
| POST | `/login` | Public | Dang nhap, set session cookie/JWT |
| POST | `/logout` | User | Xoa session cookie |
| GET | `/me` | User | Lay profile hien tai |
| POST | `/forgot` | Public | Tao reset email/outbox |
| POST | `/reset` | Public | Doi password bang reset token |
| GET | `/start` | Public | Bat dau Google OAuth |
| POST | `/callback` | Public | Google OAuth callback |
| GET | `/user/{user_id}` | User/Admin | Lay profile user |
| POST | `/user/{user_id}/preferences` | User/Admin | Cap nhat preferences |
| DELETE | `/user/{user_id}` | User/Admin | Xoa user co gioi han quyen |

### 6.2 Onboarding va learning

| Method | Endpoint | Auth | Mo ta |
|---|---|---|---|
| POST | `/onboarding` | Public/User | Tao profile onboarding 3 buoc |
| POST | `/onboarding/demo` | Public | Tao demo learner |
| GET | `/learning/current` | User | Lay lesson state hien tai |
| POST | `/learning/start` | User | Bat dau/resume lesson |
| POST | `/learning/{lesson_id}/questions` | User | Sinh cau hoi on tap |
| POST | `/learning/{lesson_id}/questions/submit` | User | Cham bai, cap nhat progress |
| GET | `/learning/{lesson_id}/flashcards` | User | Lay flashcards cua lesson |
| POST | `/learning/{lesson_id}/complete` | User | Danh dau lesson hoan thanh |

### 6.3 Tutor, memory va review

| Method | Endpoint | Auth | Mo ta |
|---|---|---|---|
| POST | `/chat` | User/Demo | Chay LangGraph tutor pipeline |
| GET | `/session/restore` | User | Khoi phuc chat/session gan nhat |
| DELETE | `/session/{user_id}` | User/Admin | Xoa session cache cua user |
| GET | `/vocabulary/new` | User | Lay tu vung moi theo profile |
| GET | `/review/due` | User | Lay vocab/error flashcards den lich SM-2 |
| POST | `/review/submit` | User | Submit quality 0-5, cap nhat SM-2 |
| GET | `/brief/today` | User | Morning brief retrieval questions |
| POST | `/brief/submit` | User | Submit cau tra loi morning brief |
| POST | `/mood` | User | Luu mood dau phien va derived config |
| GET | `/mood/today` | User | Lay mood hom nay |
| POST | `/context/analyze` | User | Phan tich pasted work text, extract terms |

### 6.4 Analytics, DNA, GDPR va admin

| Method | Endpoint | Auth | Mo ta |
|---|---|---|---|
| GET | `/analytics/{user_id}/summary` | User/Admin | Tong quan tien do ca nhan |
| GET | `/analytics/{user_id}/vocabulary` | User/Admin | Thong ke tu vung |
| GET | `/dna/{user_id}` | User/Admin | Error DNA snapshot |
| GET | `/dna/all/list` | Admin | Danh sach DNA snapshots |
| POST | `/gdpr/delete` | User | Xoa du lieu ca nhan va memory |
| GET | `/gdpr/audit` | Admin | Audit delete requests |
| GET | `/admin/metrics` | Admin | Metrics tong quan |
| GET | `/admin/llm-costs` | Admin | Chi phi LLM |
| GET | `/admin/memory/status` | Admin | Trang thai Mem0/outbox |
| POST | `/admin/memory/flush` | Admin | Flush queued memory facts |
| GET | `/admin/dashboard` | Admin | Dashboard tong hop |
| GET | `/admin/dashboard.csv` | Admin | Export CSV |
| POST | `/admin/users/{user_id}/role` | Admin | Cap nhat role user/admin |

## 7. Non-functional requirements

| Danh muc | Muc tieu |
|---|---|
| Chat latency | P95 end-to-end < 3s; P99 < 5s |
| Memory retrieval | P95 < 1s |
| Loading UI | Khong co loading chinh > 2s neu co cached/session state |
| Scale alpha | 100-200 active users; rate limit 50 queries/user/day |
| Token cost | Giam >= 80%, target 90%, bang retrieval-first thay vi full-history prompt |
| Data deletion | Hoan thanh delete request < 30s voi audit row |
| Privacy | PII scrubbing truoc khi luu Mem0; user co quyen delete memory |
| Availability | 99.5% trong giai doan alpha |
| Accessibility | Mobile responsive, WCAG AA cho cac flow chinh |
| Observability | Moi request co trace id, latency, provider/model, token/cost neu dung LLM |

## 8. Deployment view

```mermaid
flowchart TB
    subgraph Client
        Browser["Mobile/Desktop Browser"]
    end

    subgraph Edge
        FEHost["Frontend Host<br/>Vercel/static hosting"]
    end

    subgraph BackendRuntime["Backend Runtime<br/>Railway/AWS/GCP VM"]
        API["FastAPI container"]
        Worker["Scheduler/worker process"]
    end

    subgraph DataStores["Managed/self-hosted data stores"]
        PG[("PostgreSQL")]
        Redis[("Redis")]
        Qdrant[("Qdrant")]
    end

    subgraph External["External services"]
        LLM["LLM APIs"]
        Sentry["Sentry"]
        Email["Email provider"]
    end

    Browser --> FEHost
    FEHost --> API
    API --> PG
    API --> Redis
    API --> Qdrant
    API --> LLM
    API --> Sentry
    Worker --> PG
    Worker --> Qdrant
    Worker --> Email
```

## 9. Ranh gioi alpha va huong mo rong

### Alpha must-have

- Email/password auth, Google OAuth optional.
- Onboarding 3 buoc: CEFR, industry, learning goals.
- Chat text-based voi LangGraph, guardrails, memory retrieval, scaffolding.
- SM-2 review cho vocabulary va error flashcards.
- Mood check-in, context injection MVP.
- Admin dashboard cho cost, latency, users va memory outbox.
- GDPR delete flow.

### Sau alpha

- Native mobile app.
- Voice/pronunciation assessment.
- Payment/subscription.
- Multi-language support.
- Advanced memory compression va cohort benchmarking cho Error DNA.
