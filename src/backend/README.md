# Backend API — Agentic Language Tutor

**Stack:** FastAPI 0.115+, PostgreSQL 16, Redis 7, Qdrant 1.11  
**Status:** Sprint 3 Complete (MVP ready)

## Quick Start

### Prerequisites
- Docker & Docker Compose 2.x
- Python 3.11+ (for non-Docker dev)
- API keys (optional for dev):
  - `OPENAI_API_KEY` (or Groq/Gemini)
  - `MEM0_API_KEY`

### Docker Setup (Recommended)

```bash
cd src
cp .env.example .env        # Fill in API keys if available
docker compose up -d --build
```

**Services:**
- Backend API: `http://localhost:8000` (Swagger: `/docs`)
- PostgreSQL: `localhost:5432`
- Redis: `localhost:6379`
- Qdrant: `http://localhost:6333`

### First-Time Setup

After stack is up:

```bash
# Run database migrations
docker compose exec backend alembic upgrade head

# Seed runtime data (vocabulary, error_bank, pedagogical_prompt,
# ielts_writing_sample + Mem0 persona facts) from data/processed/
docker compose exec backend python -m app.seeders.seed_processed

# Run integration tests
docker compose exec backend pytest tests/test_integration.py -v
```

## Project Structure

```
backend/
├── app/
│   ├── main.py                    # FastAPI app + routing
│   ├── mcp_client.py              # MCP integration
│   ├── api/v1/                    # API endpoints
│   │   ├── onboarding.py          # POST /onboarding
│   │   ├── chat.py                # POST /chat (LangGraph pipeline)
│   │   ├── review.py              # GET/POST /review (SM-2)
│   │   ├── vocabulary.py          # GET /vocabulary
│   │   ├── analytics.py           # GET /analytics (cached)
│   │   ├── admin.py               # GET /admin/metrics
│   │   └── user.py                # DELETE /user/{id}
│   ├── core/
│   │   ├── config.py              # Settings from .env
│   │   ├── database.py            # SQLAlchemy setup
│   │   ├── redis_client.py        # Redis + SessionStore
│   │   ├── mem0_client.py         # Mem0 memory wrapper
│   │   └── middleware.py          # Rate limiting
│   ├── models/
│   │   ├── schemas.py             # Pydantic schemas (with validators)
│   │   ├── user.py                # SQLAlchemy User model
│   │   └── vocabulary.py          # Vocabulary + UserVocabulary models
│   ├── services/
│   │   ├── langgraph_orchestrator.py   # LangGraph 4-node pipeline
│   │   ├── scaffolding_engine.py       # Error detection + hint generation
│   │   ├── sm2_scheduler.py            # Spaced repetition (SM-2)
│   │   └── memory_manager.py           # Mem0 CRUD
│   ├── seeders/
│   │   └── seed_processed.py      # Ingest data/processed/ into Postgres + Mem0
│   └── utils/
│       ├── llm.py                 # LLM client (OpenAI/Groq/mock)
│       └── validators.py          # PII scrubbing
├── tests/
│   ├── test_integration.py        # End-to-end flows
│   ├── test_sm2_scheduler.py      # SM-2 algorithm tests
│   ├── test_sprint2_benchmarks.py # Performance benchmarks
│   └── ...
├── alembic/                       # Database migrations
├── Dockerfile
├── requirements.txt
├── .env.example
└── README.md (this file)
```

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```bash
# Database
DATABASE_URL=postgresql://user:password@localhost/tutordb

# Redis
REDIS_URL=redis://localhost:6379

# Vector DB (Mem0)
QDRANT_URL=http://localhost:6333

# LLM APIs (optional; mock works without these)
OPENAI_API_KEY=sk-...
MEM0_API_KEY=...

# Admin access
ADMIN_TOKEN=your-secret-admin-token

# App
ENVIRONMENT=development
LOG_LEVEL=DEBUG
```

## Key Features

### 1. Persistent Memory (Mem0)
- Stores user facts, error patterns, learning history
- Semantic search to retrieve relevant context
- Fallback to in-memory storage if Qdrant unavailable

### 2. LangGraph 4-Node Pipeline
For each chat message:
1. **Intent Router** — Classify user intent (PRACTICE, QUICK_QA, PROGRESS)
2. **Memory Retrieval** — Load relevant facts from Mem0
3. **Scaffolding Engine** — Generate hints or reveal answers
4. **Memory Writer** — Extract and save new facts (debounced)

### 3. Spaced Repetition (SM-2)
- Implements SM-2 algorithm from SuperMemo
- Tracks: `ease_factor`, `interval_days`, `next_review`, `mastered`
- GET `/review/due` — words due for review today
- POST `/review/submit` — update SM-2 state on review quality (0-5)

### 4. Scaffolding Engine
- Detects errors by checking `confusion_with` field in Vocabulary DB
- Generates 2-level hints: subtle → explicit
- Give-up reveal with SM-2 quality update

### 5. Analytics & Caching
- GET `/analytics/{user_id}/summary` — accuracy trend, top errors
- GET `/analytics/{user_id}/vocabulary` — breakdown by CEFR/industry
- **Redis cache with 1-hour TTL** to reduce database load
- GET `/analytics/{user_id}/summary?cache_bust=1` to skip cache

### 6. Rate Limiting
- 50 requests per user per day
- Tracked by `user_id` (query param or `X-User-ID` header)
- Returns 429 Too Many Requests when exceeded
- Skips health check, docs, and debug endpoints

### 7. Data Validation (Pydantic v2)
All request schemas have validators:
- `OnboardingCreate`: CEFR level ∈ {A1, A2, B1, B2, C1}, goals non-empty
- `ReviewSubmit`: quality ∈ [0, 5], word_id > 0
- `ChatRequest`: message length ∈ [1, 5000]
- etc.

### 8. GDPR Compliance
- DELETE `/user/{user_id}` — cascade delete from PostgreSQL, Mem0, Redis
- PII scrubber: emails/phones → `[EMAIL]`/`[PHONE]` before storing in Mem0

## API Endpoints

### Onboarding
```bash
POST /api/v1/onboarding
{
  "email": "user@example.com",
  "cefr_level": "B1",
  "industry": "marketing",
  "learning_goals": ["business vocab"]
}
```

### Chat
```bash
POST /api/v1/chat
{
  "user_id": "uuid",
  "message": "What is a stakeholder?"
}
→ { "response": "...", "hint_count": 1, "intent": "QUICK_QA" }
```

### Review
```bash
GET /api/v1/review/due?user_id=uuid
→ { "words": [{ "word_id": 1, "word": "campaign", ... }, ...] }

POST /api/v1/review/submit
{
  "user_id": "uuid",
  "word_id": 1,
  "quality": 4
}
→ { "next_review": "2026-05-15", "interval_days": 6, ... }
```

### Analytics (Cached)
```bash
GET /api/v1/analytics/{user_id}/summary
→ {
  "accuracy_trend": [{"date": "...", "accuracy": 78}, ...],
  "top_errors": [{"error": "affect/effect", "count": 5}, ...],
  "vocabulary": {"total_learned": 120, "mastered": 45}
}

GET /api/v1/analytics/{user_id}/vocabulary
→ {
  "total_learned": 120,
  "mastered": 45,
  "by_cefr": {"A2": 30, "B1": 60, "B2": 30},
  "by_industry": {"marketing": 50, "tech": 40, ...}
}
```

### Admin
```bash
GET /api/v1/admin/metrics
(Requires X-Admin-Token header)
→ { "total_users": 50, "avg_token_per_session": 150, ... }
```

### User
```bash
DELETE /api/v1/user/{user_id}
→ { "status": "deleted", "user_id": "..." }
```

## Testing

### Run All Tests
```bash
docker compose exec backend pytest -v
```

### Run Specific Test Suite
```bash
# Integration tests (onboarding → chat → review flows)
docker compose exec backend pytest tests/test_integration.py -v

# SM-2 scheduler unit tests (100% coverage)
docker compose exec backend pytest tests/test_sm2_scheduler.py -v

# Sprint 2 benchmarks (LangGraph latency, Mem0 P95)
docker compose exec backend pytest tests/test_sprint2_benchmarks.py -v

# LLM fallback chain (Gemini → Groq → mock)
docker compose exec backend pytest tests/test_llm_fallback_chain.py -v
```

### Create Demo User
```bash
curl -X POST http://localhost:8000/api/v1/onboarding/demo
→ { "user_id": "...", "cefr_level": "B1", "industry": "marketing" }
```

## Performance Metrics

| Metric | Target | Actual (Sprint 3) |
|---|---|---|
| Chat latency P95 | <3s | ~2.5s |
| Mem0 search latency P95 | <1s | 47.5ms |
| Analytics query (cached) | <100ms | ~50ms (1st), <10ms (cache hit) |
| Rate limit lookup | <10ms | <5ms |
| SM-2 recalc | <10ms | ~2ms |

## Database Migrations

### Create New Migration
```bash
docker compose exec backend alembic revision --autogenerate -m "describe change"
docker compose exec backend alembic upgrade head
```

### Rollback
```bash
docker compose exec backend alembic downgrade -1
```

## Troubleshooting

### Backend won't start
```bash
# Check logs
docker compose logs backend

# Restart stack
docker compose down && docker compose up -d --build

# Check health
curl http://localhost:8000/health
```

### Vocabulary / processed data not seeding
```bash
docker compose exec backend python -m app.seeders.seed_processed --only vocabulary
```

### Rate limit too strict
- Edit `core/middleware.py`: `RATE_LIMIT_REQUESTS`
- Restart: `docker compose restart backend`

### Mem0 errors
- Check `.env`: `MEM0_API_KEY`, `QDRANT_URL`
- Mem0 has in-memory fallback; works without real keys
- See `core/mem0_client.py` for fallback logic

## Development (Non-Docker)

```bash
# Create virtual env
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Set up .env with local database
export DATABASE_URL=postgresql://...
export REDIS_URL=redis://localhost:6379
...

# Run migrations
alembic upgrade head

# Start server
uvicorn app.main:app --reload --port 8000
```

## Contributing

1. **Sprint Plan** — See [../../docs/SPRINT.md](../../docs/SPRINT.md)
2. **Update SPRINT.md** when checkboxes are completed
3. **AI Logging** — Automatic via git hooks (run `bash scripts/setup_hooks.sh` once)
4. **Tests** — Add tests in `tests/` and verify with `pytest`
5. **Code style** — Black for formatting, Pylint for linting

## Sprint Completion Status

- ✅ **Sprint 1** — Infrastructure + mock API
- ✅ **Sprint 2** — LangGraph orchestrator + scaffolding + session restore
- ✅ **Sprint 3** — Analytics + rate limiting + validators + integration tests

Next: Frontend deployment (Vercel) + load testing.
