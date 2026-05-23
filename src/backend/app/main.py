from contextlib import asynccontextmanager, suppress
import asyncio
import logging
import logging.config
import os
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .api.v1 import (
    auth,
    auth_google,
    chat,
    onboarding,
    review,
    vocabulary,
    analytics,
    admin,
    user,
    mood,
    context as context_router,
    brief,
    dna,
    gdpr,
    learning,
)
from .core.config import get_settings
from .core.database import SessionLocal
from .core.mem0_client import get_memory
from .core.observability import init_observability
from .core.redis_client import get_redis
from .core.middleware import RateLimitMiddleware
from .services.memory_outbox import memory_outbox_counts
from .mcp_client import MCPClient
from .services.metrics_collector import hourly_metrics_logging_loop
from .services.scheduler import start_scheduler, stop_scheduler

def _configure_logging() -> None:
    level_name = os.getenv("LOGLEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Keep app graph logs visible while silencing noisy Gemini/http transport
    # internals. Warnings/errors still surface.
    for logger_name in (
        "google_genai",
        "google_genai.models",
        "google",
        "google.auth",
        "google.api_core",
        "httpx",
        "httpcore",
        "httpcore.connection",
        "httpcore.http11",
    ):
        logging.getLogger(logger_name).setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)

mcp = MCPClient()
_startup_ready = False
_memory_warmup_status = "pending"
_MEM0_STARTUP_WARMUP_TIMEOUT_SECONDS = float(os.getenv("MEM0_STARTUP_WARMUP_TIMEOUT_SECONDS", "8.0"))


def _normalize_trace_id(value: str | None) -> str:
    raw = str(value or "").strip()
    if raw and len(raw) <= 96 and all(ch.isalnum() or ch in "-_." for ch in raw):
        return raw
    return str(uuid.uuid4())


def _tag_sentry_request(trace_id: str, request: Request) -> None:
    try:
        import sentry_sdk  # type: ignore

        sentry_sdk.set_tag("trace_id", trace_id)
        sentry_sdk.set_tag("http.path", request.url.path)
        sentry_sdk.set_tag("http.method", request.method)
    except Exception:
        pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _startup_ready, _memory_warmup_status
    init_observability()
    metrics_stop_event = asyncio.Event()
    metrics_task = asyncio.create_task(hourly_metrics_logging_loop(metrics_stop_event))
    await mcp.connect()
    warmup_started_at = time.perf_counter()
    try:
        await asyncio.wait_for(
            asyncio.to_thread(get_memory().warmup),
            timeout=_MEM0_STARTUP_WARMUP_TIMEOUT_SECONDS,
        )
        _memory_warmup_status = "ready"
        logger.info("Mem0 warmup completed duration_ms=%s", int((time.perf_counter() - warmup_started_at) * 1000))
    except TimeoutError:
        _memory_warmup_status = "timeout"
        logger.warning(
            "Mem0 warmup timed out duration_ms=%s timeout_seconds=%.1f; chat will use per-request fallback",
            int((time.perf_counter() - warmup_started_at) * 1000),
            _MEM0_STARTUP_WARMUP_TIMEOUT_SECONDS,
        )
    except Exception:
        _memory_warmup_status = "failed"
        logger.exception("Mem0 warmup failed; chat will use per-request fallback")
    start_scheduler()
    _startup_ready = True
    try:
        yield
    finally:
        _startup_ready = False
        metrics_stop_event.set()
        metrics_task.cancel()
        with suppress(asyncio.CancelledError):
            await metrics_task
        await stop_scheduler()
        await mcp.disconnect()
        redis = get_redis()
        await redis.aclose()


app = FastAPI(title="A20 Tutor Backend", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def request_trace_middleware(request: Request, call_next):
    trace_id = _normalize_trace_id(request.headers.get("X-Trace-Id"))
    request.state.trace_id = trace_id
    started_at = time.perf_counter()
    status_code = 500
    _tag_sentry_request(trace_id, request)

    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception:
        logger.exception(
            "http_request_failed trace_id=%s method=%s path=%s",
            trace_id,
            request.method,
            request.url.path,
        )
        raise
    finally:
        duration_ms = int((time.perf_counter() - started_at) * 1000)
        response = locals().get("response")
        if response is not None:
            response.headers["X-Trace-Id"] = trace_id
            response.headers["X-Response-Time-Ms"] = str(duration_ms)

        log_fn = logger.warning if duration_ms >= 5000 else logger.info
        log_fn(
            "http_request_complete trace_id=%s method=%s path=%s status_code=%s duration_ms=%s",
            trace_id,
            request.method,
            request.url.path,
            status_code,
            duration_ms,
        )

# Add rate limiting middleware (before CORS)
# Note: Middleware order matters; rate limit should be outermost
app.add_middleware(RateLimitMiddleware, redis=get_redis())

# CORS: must be explicit (not "*") because we send cookies with credentials.
_settings = get_settings()
_cors_origins = [o.strip() for o in _settings.FRONTEND_ORIGIN.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins or ["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Trace-Id", "X-Response-Time-Ms"],
)


# Global exception handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.warning(
        "request_validation_failed trace_id=%s method=%s path=%s errors=%s",
        trace_id,
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation error",
            "detail": "Request data is invalid",
            "trace_id": trace_id,
        },
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Request failed",
            "detail": detail,
            "trace_id": trace_id,
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    trace_id = getattr(request.state, "trace_id", str(uuid.uuid4()))
    logger.error("Unhandled exception trace_id=%s", trace_id, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": "Internal server error",
            "trace_id": trace_id,
        },
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not _startup_ready:
        return JSONResponse(status_code=503, content={"status": "starting", "memory_warmup": _memory_warmup_status})
    payload = {"status": "ready", "memory_warmup": _memory_warmup_status, "memory": get_memory().status()}
    try:
        db = SessionLocal()
        try:
            payload["memory_outbox"] = memory_outbox_counts(db)
        finally:
            db.close()
    except Exception:
        logger.exception("ready: failed to load memory outbox counts")
    return payload


@app.get("/api/v1/debug/sentry")
def _debug_sentry_trigger():
    """One-click Sentry smoke test. Always raises — if Sentry is configured
    correctly the error surfaces in the dashboard within ~30 seconds.

    Safe to leave in prod: requires no auth, but only useful if someone
    knows the exact path. Revealing it does not expose any data.
    """
    raise RuntimeError("Sentry smoke test from A20 backend — this is expected")


@app.get("/api/hello")
def hello():
    return {"message": "hello from FastAPI backend"}


@app.get("/api/tools")
async def list_tools():
    return {"tools": await mcp.list_tools()}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(auth_google.router, prefix="/api/v1")
app.include_router(onboarding.router, prefix="/api/v1")
app.include_router(vocabulary.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(user.router, prefix="/api/v1")
app.include_router(mood.router, prefix="/api/v1")
app.include_router(context_router.router, prefix="/api/v1")
app.include_router(brief.router, prefix="/api/v1")
app.include_router(dna.router, prefix="/api/v1")
app.include_router(gdpr.router, prefix="/api/v1")
app.include_router(learning.router, prefix="/api/v1")
