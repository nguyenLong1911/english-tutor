from functools import lru_cache
import os

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


_LOCAL_FALLBACK_HOSTS = {
    "postgres": "localhost",
    "qdrant": "localhost",
    "redis": "localhost",
}


def _preserve_docker_service_hosts() -> bool:
    return os.getenv("USE_DOCKER_SERVICE_HOSTS", "").strip().lower() in {"1", "true", "yes", "on"}


def _rewrite_docker_service_host(url: str) -> str:
    if not isinstance(url, str) or _preserve_docker_service_hosts():
        return url

    scheme, sep, remainder = url.partition("://")
    if not sep:
        return url

    authority, path_sep, tail = remainder.partition("/")
    if not authority:
        return url

    host_start = authority.rfind("@") + 1
    host_end = authority.find(":", host_start)
    if host_end == -1:
        host_end = len(authority)

    host = authority[host_start:host_end]
    replacement = _LOCAL_FALLBACK_HOSTS.get(host)
    if replacement is None:
        return url

    rewritten_authority = authority[:host_start] + replacement + authority[host_end:]
    rebuilt = f"{scheme}{sep}{rewritten_authority}"
    if path_sep:
        rebuilt += f"{path_sep}{tail}"
    return rebuilt


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = "postgresql+psycopg://tutor:tutorpass@localhost:5432/tutordb"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_scheme(cls, v: str) -> str:
        # Railway/Heroku-style URLs come as `postgresql://...` but the app is
        # wired for the psycopg3 driver. Promote to the `+psycopg` scheme if
        # no driver is already specified.
        if isinstance(v, str) and v.startswith("postgresql://"):
            v = "postgresql+psycopg://" + v[len("postgresql://") :]
        if isinstance(v, str) and v.startswith("postgres://"):
            v = "postgresql+psycopg://" + v[len("postgres://") :]
        return _rewrite_docker_service_host(v)

    REDIS_URL: str = "redis://localhost:6379/0"
    QDRANT_URL: str = "http://localhost:6333"

    @field_validator("REDIS_URL", "QDRANT_URL", mode="before")
    @classmethod
    def _normalize_service_urls(cls, v: str) -> str:
        return _rewrite_docker_service_host(v)

    QDRANT_COLLECTION: str = "tutor_memory"

    GEMINI_API_KEY: str = ""
    # Alias accepted because the official ``google-genai`` SDK reads
    # ``GOOGLE_API_KEY`` by convention. If both are set, ``GEMINI_API_KEY``
    # wins; otherwise ``GOOGLE_API_KEY`` is promoted into ``GEMINI_API_KEY``
    # at startup so every downstream consumer (utils/llm, mem0_client,
    # scaffolding_engine, observability) just keeps reading the one field.
    GOOGLE_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    GROQ_API_KEY: str = ""
    GROQ_API_KEY_1: str = ""
    GROQ_API_KEY_2: str = ""
    ANTHROPIC_API_KEY: str = ""

    @model_validator(mode="after")
    def _promote_google_api_key(self) -> "Settings":
        if not self.GEMINI_API_KEY and self.GOOGLE_API_KEY:
            self.GEMINI_API_KEY = self.GOOGLE_API_KEY
        return self

    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_MAX_OUTPUT_TOKENS: int = 4096
    LLM_OUTPUT_TOKENS_MULTIPLIER: int = 10

    # As of mid-2026 Google's free tier no longer covers gemini-1.5-flash
    # or gemini-2.0-flash for newly-created Cloud projects (quota=0). The
    # 2.5 line still has a usable free tier and is the safest default.
    LLM_MODEL: str = "gemini-2.5-flash"
    # Bare model id (no ``models/`` prefix). Vertex AI routing (forced by
    # GOOGLE_GENAI_USE_VERTEXAI=True in our env) resolves bare ids to
    # ``publishers/google/models/<id>``; with the AI-Studio-style ``models/``
    # prefix it builds ``publishers/google/models/models/...`` and 404s,
    # which silently demotes Mem0 to the in-memory stub. See
    # ``docs/evaluation/mem0_benchmark.md`` for the regression history.
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Root directory holding the curated JSON artefacts produced by
    # ``src/data_pipeline`` (Sprint 1). Mounted read-only into the backend
    # container at ``/app/data/processed`` by ``docker-compose.yml``. Seeded
    # at startup by ``app.seeders.seed_processed``.
    PROCESSED_DATA_DIR: str = "/app/data/processed"

    RATE_LIMIT_PER_DAY: int = 50
    SESSION_TTL_SECONDS: int = 86400

    ADMIN_TOKEN: str = "change-me-in-prod"
    ADMIN_EMAIL: str = ""
    ADMIN_PASSWORD: str = ""

    # Auth (Sprint 4)
    JWT_SECRET: str = "change-me-jwt-secret-dev-only"
    JWT_ALGORITHM: str = "HS256"
    JWT_TTL_DAYS: int = 7
    SESSION_COOKIE_NAME: str = "a20_session"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    # Google OAuth (optional; left blank disables /auth/google/*)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # Email provider (Resend primary; leave blank → outbox rows stay pending)
    RESEND_API_KEY: str = ""
    EMAIL_FROM: str = "A20 Tutor <no-reply@a20-tutor.local>"
    EMAIL_RESET_BASE_URL: str = "http://localhost:5173/auth/reset"

    # Observability (leave blank → Sentry not initialized, no crash)
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"
    SENTRY_TRACES_SAMPLE_RATE: float = 0.1

    # Scheduler (APScheduler). Disable in tests / dev if needed.
    SCHEDULER_ENABLED: bool = True

    # Memory compaction
    MEM0_USER_FACT_CAP: int = 2000
    MEMORY_WRITE_MODE: str = "queued"
    MEMORY_VERTEX_RPM_LIMIT: int = 4
    MEMORY_OUTBOX_MAX_RETRIES: int = 8
    MEMORY_CIRCUIT_BREAKER_SECONDS: int = 60
    MEMORY_OUTBOX_FLUSH_BATCH: int = 1
    MEMORY_OPPORTUNISTIC_FLUSH_ENABLED: bool = False

    # Difficulty tuner: min sessions required before bumping CEFR step
    DIFFICULTY_MIN_SESSIONS: int = 3
    DIFFICULTY_UP_THRESHOLD: float = 0.85
    DIFFICULTY_DOWN_THRESHOLD: float = 0.45
    PRACTICE_HINTS_ENABLED: bool = True
    PRACTICE_QUESTION_LLM_ENABLED: bool = True

    # Morning Brief
    BRIEF_HOUR_LOCAL: int = 6  # 06:00 user-timezone

    # Guardrails (LLM safety). All flags default to ON; flip to false in
    # tests / scripts that need raw model behaviour.
    GUARDRAILS_ENABLED: bool = True
    GUARDRAILS_BLOCK_PROMPT_INJECTION: bool = True
    GUARDRAILS_BLOCK_SYSTEM_LEAK: bool = True
    GUARDRAILS_BLOCK_IDENTITY_LEAK: bool = True
    GUARDRAILS_REDACT_PII_OUTPUT: bool = True
    # Gemini provider-level safety thresholds. Accepted values mirror the
    # Gemini REST enum: BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE,
    # BLOCK_LOW_AND_ABOVE. Educational content rarely trips MEDIUM, so this
    # is a safe default for an English-tutor app.
    GEMINI_SAFETY_THRESHOLD: str = "BLOCK_MEDIUM_AND_ABOVE"


@lru_cache
def get_settings() -> Settings:
    return Settings()
