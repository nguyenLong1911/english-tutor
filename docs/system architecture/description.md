# Kien truc he thong theo PRD v2 - Agentic Language Tutor

Tai lieu nay duoc tao dua tren `docs/project requirements/PRD_v2.md`. Muc tieu la bien yeu cau san pham thanh ban thiet ke ky thuat co the doc truc tiep trong VS Code bang Markdown Preview/Mermaid.

## 1. Muc tieu kien truc

Agentic Language Tutor la web app hoc tieng Anh cho nguoi di lam ban ron, can duy tri tri nho dai han va ca nhan hoa bai hoc qua nhieu phien hoc ngan. Kien truc tap trung vao cac muc tieu:

- Ghi nho loi sai, tu vung, trinh do, nganh nghe, mood va chu de ua thich cua tung nguoi hoc.
- Dieu phoi phan hoi gia su bang LangGraph thay vi mot chatbot endpoint don gian.
- Truy xuat memory P95 duoi 1 giay va phan hoi end-to-end P95 duoi 3 giay.
- Giam chi phi token bang retrieval-first memory thay vi day toan bo lich su hoi thoai vao prompt.
- Ho tro micro-learning, spaced repetition, scaffolding va delete-my-data cho alpha.

## 2. Tech stack de xuat

| Tang | Cong nghe | Vai tro |
|---|---|---|
| Frontend | Next.js hoac React + Vite, TailwindCSS | Web app mobile-responsive: onboarding, chat, review, dashboard, settings |
| Backend API | FastAPI | REST API, auth, rate limit, session management, entrypoint cho LangGraph |
| Orchestration | LangGraph | Dieu phoi tutor pipeline: retrieval, context, scaffolding, memory writer |
| LLM Core | GPT-4o / Claude Sonnet | Hieu ngon ngu, sinh phan hoi, giai thich loi, tao hint |
| Memory Layer | Mem0 + Vector DB/Qdrant | Luu va truy xuat semantic facts dai han |
| Database | PostgreSQL | User profile, auth, session logs, review schedule, analytics |
| Cache | Redis | Rate limit, session cache, short-lived retrieval cache |
| Scheduler/Worker | Background jobs/APScheduler/Celery | SM-2 review, morning brief, weekly progress email, memory compaction |
| Monitoring | Sentry/Datadog + cost logs | Error tracking, latency, token cost per user/session |
| Infrastructure | Vercel + Railway/AWS/GCP | Deploy frontend/backend cho alpha |

## 3. Component diagram

```mermaid
flowchart LR
    User["Learner / Admin"] --> FE["Frontend Web App<br/>Onboarding, Chat, Review, Dashboard, Settings"]
    FE -->|HTTPS JSON API<br/>cookies/JWT| API["FastAPI Backend<br/>/api/v1"]

    API --> Auth["Auth Service<br/>email/password, Google OAuth, roles"]
    API --> Rate["Rate Limit Middleware<br/>Redis, 50 queries/user/day"]
    API --> Routers["API Routers<br/>auth, chat, learning, review, admin, gdpr"]
    API --> DB[("PostgreSQL<br/>profiles, sessions, reviews, logs")]
    API --> Redis[("Redis<br/>rate limit, session cache")]

    Routers --> Graph["LangGraph Tutor Pipeline"]
    Graph --> Guard["Input/Output Guardrails"]
    Graph --> Intent["Intent Router<br/>practice, quick Q&A, progress check"]
    Graph --> MemRead["Memory Retrieval<br/>top-K personal facts"]
    MemRead --> Mem0["Mem0 Client"]
    Mem0 --> Vector[("Vector DB / Qdrant<br/>semantic memory")]

    Graph --> Context["Context Builder<br/>facts + recent turns + system prompt"]
    Context --> Scaffold["Scaffolding Engine<br/>detect error, 2 hints, reveal answer"]
    Scaffold --> LLM["LLM Provider Chain<br/>GPT-4o / Claude Sonnet"]
    LLM --> Scaffold

    Graph --> MemWrite["Memory Writer<br/>extract and upsert facts"]
    MemWrite --> Outbox[("memory_fact_outbox<br/>retryable queue")]
    Outbox --> Mem0

    API --> Scheduler["Scheduler / Background Jobs"]
    Scheduler --> SM2["SM-2 Spaced Repetition"]
    Scheduler --> Morning["Morning Brief"]
    Scheduler --> Email["Weekly Progress Email"]
    Scheduler --> Compactor["Memory Compression"]

    SM2 --> DB
    Morning --> Mem0
    Email --> DB
    Compactor --> Mem0

    API --> Obs["Observability<br/>Sentry, Datadog, token cost logs"]
    Graph --> Obs
    LLM --> Cost["Token Cost Monitor"]
    Cost --> DB
```

## 4. LangGraph tutor pipeline

Pipeline alpha trong PRD gom 4 node cot loi: Memory Retrieval, Context Builder, Scaffolding Engine va Memory Writer. Ban thiet ke duoi day mo rong nhe de ho tro mood, guardrails va intent routing ma van giu dung loi kien truc PRD.

```mermaid
flowchart TD
    A["POST /api/v1/chat"] --> B["Load user profile<br/>level, industry, goals"]
    B --> C["Mood Adapter<br/>optional mood check-in"]
    C --> D["Input Guard<br/>privacy, unsafe input, prompt injection"]
    D -->|blocked| O["Output Guard<br/>safe response"]
    D -->|ok| E["Intent Router<br/>practice / Q&A / progress / context injection"]

    E --> F["Memory Retrieval<br/>Mem0 semantic search top-K=10"]
    F --> G["Context Builder<br/>memory facts + 3-5 turns + task prompt"]
    G --> H["Scaffolding Engine<br/>detect error, hint 1, hint 2, answer after rule"]
    H --> I["LLM Call<br/>GPT-4o or Claude Sonnet"]
    I --> J["Response Composer<br/>tone, explanation, UI directive"]
    J --> K["Memory Writer<br/>extract new facts and error events"]
    K --> L["PostgreSQL Writes<br/>session log, review result, analytics"]
    K --> M["Mem0 Upsert<br/>error, vocab, mood, industry, skill"]
    J --> O
    O --> N["ChatResponse to Frontend"]
```

## 5. Data flow chinh

```mermaid
sequenceDiagram
    participant U as User
    participant FE as Frontend
    participant API as FastAPI
    participant Redis
    participant DB as PostgreSQL
    participant LG as LangGraph
    participant Mem0
    participant LLM

    U->>FE: Nhap cau tra loi hoac paste van ban cong viec
    FE->>API: POST /api/v1/chat
    API->>Redis: Check rate limit va cache ngan han
    API->>DB: Load profile, session gan nhat, review due
    API->>LG: Run tutor graph
    LG->>Mem0: Retrieve top-K facts cua user
    LG->>LLM: Prompt = profile + facts + recent turns + pedagogy rules
    LLM-->>LG: Phan hoi, hints, detected errors, facts moi
    LG->>DB: Luu session_log, error_event, review_result
    LG->>Mem0: Upsert long-term memory facts
    API-->>FE: Tra response + suggested actions + ui directive
    FE-->>U: Hien chat/review/dashboard update
```

## 6. Memory fact schema

Mem0/Qdrant luu semantic facts dai han. PostgreSQL van la source of truth cho user, session, audit va bao cao.

```json
{
  "user_id": "uuid",
  "fact_type": "error_pattern | vocabulary | mood_pattern | industry_vocab | skill_level | topic_preference",
  "content": "User confuses 'affect' as a verb with 'effect' as a noun",
  "embedding": [0.01, 0.02],
  "importance_score": 0.85,
  "last_updated": "2025-04-10",
  "review_count": 3,
  "source_session": "session_id"
}
```

## 7. Database schema muc tieu

```mermaid
erDiagram
    USER_PROFILE {
        uuid user_id PK
        string email UK
        string password_hash
        string display_name
        string cefr_level
        string industry
        string goals
        string role
        datetime created_at
    }

    SESSION_LOG {
        uuid session_id PK
        uuid user_id FK
        string mode
        int duration_seconds
        int token_input
        int token_output
        decimal estimated_cost
        datetime started_at
        datetime ended_at
    }

    MESSAGE_LOG {
        uuid message_id PK
        uuid session_id FK
        uuid user_id FK
        string role
        text content
        string intent
        datetime created_at
    }

    USER_ERROR_EVENT {
        uuid error_id PK
        uuid user_id FK
        uuid session_id FK
        string category
        text original_text
        text corrected_text
        text explanation
        float confidence
        datetime created_at
    }

    REVIEW_ITEM {
        uuid review_id PK
        uuid user_id FK
        string item_type
        text prompt
        text answer
        int interval_days
        float ease_factor
        datetime due_at
        datetime last_reviewed_at
    }

    MEMORY_FACT_OUTBOX {
        uuid outbox_id PK
        uuid user_id FK
        uuid session_id FK
        string fact_type
        text content
        string status
        int retry_count
        datetime scheduled_at
    }

    MOOD_CHECKIN {
        uuid mood_id PK
        uuid user_id FK
        int mood_score
        string strategy
        datetime created_at
    }

    ADMIN_METRIC_SNAPSHOT {
        uuid metric_id PK
        string metric_name
        decimal metric_value
        string dimension
        datetime captured_at
    }

    USER_PROFILE ||--o{ SESSION_LOG : owns
    USER_PROFILE ||--o{ MESSAGE_LOG : sends
    USER_PROFILE ||--o{ USER_ERROR_EVENT : makes
    USER_PROFILE ||--o{ REVIEW_ITEM : reviews
    USER_PROFILE ||--o{ MEMORY_FACT_OUTBOX : queues
    USER_PROFILE ||--o{ MOOD_CHECKIN : checks
    SESSION_LOG ||--o{ MESSAGE_LOG : contains
    SESSION_LOG ||--o{ USER_ERROR_EVENT : detects
    SESSION_LOG ||--o{ MEMORY_FACT_OUTBOX : produces
```

## 8. API spec alpha

| Method | Endpoint | Muc dich |
|---|---|---|
| POST | `/api/v1/auth/register` | Dang ky email/password |
| POST | `/api/v1/auth/login` | Dang nhap, set JWT cookie |
| GET | `/api/v1/auth/me` | Lay user hien tai |
| POST | `/api/v1/onboarding` | Luu level, industry, goals |
| POST | `/api/v1/chat` | Chay LangGraph tutor pipeline |
| GET | `/api/v1/review/today` | Lay bai on SM-2 hom nay |
| POST | `/api/v1/review/{review_id}/answer` | Cham ket qua on tap va cap nhat interval |
| GET | `/api/v1/dashboard/progress` | Top loi sai, accuracy trend, vocabulary stats |
| POST | `/api/v1/context-injection` | Tao mini-lesson tu van ban cong viec |
| POST | `/api/v1/mood-checkin` | Luu mood va chon chien luoc phien hoc |
| DELETE | `/api/v1/gdpr/me` | Xoa memory va du lieu ca nhan theo yeu cau |
| GET | `/api/v1/admin/metrics` | Token cost, latency, query count, active users |
| GET | `/api/v1/admin/export.csv` | Export CSV bao cao alpha |

## 9. Non-functional requirements mapping

| Yeu cau PRD | Thiet ke dap ung |
|---|---|
| End-to-end response P95 < 3s | Redis cache, Mem0 top-K retrieval, prompt ngan, provider fallback |
| Memory retrieval P95 < 1s | Vector DB index, top-K=10, cache query lap lai |
| Token cost giam 80-90% | Retrieval-first context, khong inject full conversation history |
| Delete memory < 30s | GDPR endpoint xoa PostgreSQL user data + Mem0 facts theo user_id |
| 100-200 concurrent users alpha | FastAPI async, Redis rate limit, DB index, background outbox |
| Privacy | PII scrubbing truoc khi ghi Mem0, audit log cho delete/export |
| Observability | Trace id, Sentry, latency metrics, token cost per session |

## 10. Alpha delivery plan theo PRD

| Sprint | Kien truc can hoan thanh |
|---|---|
| Sprint 1 | Infra, auth, onboarding, PostgreSQL schema, Redis rate limit, Mem0 connection, admin cost metrics |
| Sprint 2 | LangGraph 4-node pipeline, scaffolding engine, chat UI, SM-2 review, mood check-in |
| Sprint 3 | Progress dashboard, memory compression, context injection MVP, alpha monitoring, bug fix |

## 11. Ranh gioi du lieu

- PostgreSQL luu du lieu dinh danh, lich su phien hoc, analytics, review schedule va audit.
- Mem0/Qdrant luu semantic facts ca nhan hoa co the truy xuat bang vector search.
- Redis chi luu du lieu ngan han: rate limit, session cache, retrieval cache.
- LLM provider khong phai source of truth; moi output quan trong phai duoc parse, scrub PII va luu co cau truc.

## 12. VS Code usage

Mo file nay trong VS Code va nhan `Ctrl + Shift + V` de xem Mermaid Preview. Neu VS Code chua render Mermaid, cai extension `Markdown Preview Mermaid Support`.
