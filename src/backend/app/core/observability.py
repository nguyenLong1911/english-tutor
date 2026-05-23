"""Observability bootstrapping (Sentry).

No-op when `SENTRY_DSN` is blank so local/dev and tests are unaffected.
Import `init_observability()` once from FastAPI lifespan startup.

Datadog was evaluated and dropped: for single-instance Railway + MVP scale,
Sentry Tracing already covers latency/APM needs at a fraction of the cost.
"""
from __future__ import annotations

import logging
import os
import subprocess
from typing import Any

from .config import get_settings

logger = logging.getLogger(__name__)

_sentry_initialized = False


# ---------------------------------------------------------------------------
# PII scrubbing: drop password/token/JWT-looking values from any event before
# Sentry ingests it. We err on the side of aggressive redaction since we send
# memory snapshots + chat messages through the stack.
# ---------------------------------------------------------------------------
_SENSITIVE_KEYS = {
    "password", "new_password", "current_password",
    "access_token", "refresh_token", "authorization",
    "cookie", "a20_session", "jwt", "api_key", "apikey",
    "sentry_dsn", "openai_api_key", "anthropic_api_key",
    "groq_api_key", "gemini_api_key", "resend_api_key",
    "google_client_secret", "jwt_secret",
}


def _scrub_recursive(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {
            k: "[Filtered]" if str(k).lower() in _SENSITIVE_KEYS else _scrub_recursive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_scrub_recursive(v) for v in obj]
    return obj


def _before_send(event: dict, hint: dict) -> dict | None:
    try:
        # Redact request body, headers, and extra/context payloads.
        if "request" in event:
            event["request"] = _scrub_recursive(event["request"])
        if "extra" in event:
            event["extra"] = _scrub_recursive(event["extra"])
        if "contexts" in event:
            event["contexts"] = _scrub_recursive(event["contexts"])
    except Exception:  # pragma: no cover - never block error reporting
        pass
    return event


def _detect_release() -> str | None:
    """Return a release tag: explicit env > git short SHA > None."""
    for var in ("RELEASE", "SENTRY_RELEASE", "RAILWAY_GIT_COMMIT_SHA"):
        if os.getenv(var):
            return os.getenv(var)[:12]
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, timeout=1
        )
        return out.decode().strip() or None
    except Exception:
        return None


def init_observability() -> None:
    """Initialize Sentry if SENTRY_DSN is present. Idempotent."""
    global _sentry_initialized
    settings = get_settings()

    if settings.SENTRY_DSN and not _sentry_initialized:
        try:
            import sentry_sdk  # type: ignore
            from sentry_sdk.integrations.fastapi import FastApiIntegration  # type: ignore
            from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration  # type: ignore
            from sentry_sdk.integrations.logging import LoggingIntegration  # type: ignore

            sentry_sdk.init(
                dsn=settings.SENTRY_DSN,
                environment=settings.SENTRY_ENVIRONMENT,
                traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                profiles_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
                release=_detect_release(),
                send_default_pii=False,
                before_send=_before_send,
                integrations=[
                    FastApiIntegration(),
                    SqlalchemyIntegration(),
                    # Auto-capture logger.error / logger.exception as breadcrumbs
                    # + events (ERROR level and above).
                    LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
                ],
            )
            _sentry_initialized = True
            logger.info(
                "Sentry initialized (env=%s, release=%s)",
                settings.SENTRY_ENVIRONMENT,
                _detect_release() or "unset",
            )
        except ImportError:
            logger.warning(
                "SENTRY_DSN set but `sentry-sdk` not installed. "
                "Run `pip install 'sentry-sdk[fastapi]'` to enable."
            )
        except Exception:  # pragma: no cover - defensive
            logger.exception("Sentry initialization failed; continuing without it")


# ---------------------------------------------------------------------------
# Thin wrappers so app code doesn't import sentry_sdk directly. These become
# no-ops when Sentry isn't configured, keeping call sites cheap and safe.
# ---------------------------------------------------------------------------

def set_user(user_id: str | None, email: str | None = None, role: str | None = None) -> None:
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk  # type: ignore
        sentry_sdk.set_user(
            {"id": user_id, "email": email, "role": role} if user_id else None
        )
    except Exception:  # pragma: no cover
        pass


def set_tag(key: str, value: Any) -> None:
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk  # type: ignore
        sentry_sdk.set_tag(key, str(value))
    except Exception:  # pragma: no cover
        pass


def capture_exception(exc: BaseException, **extra: Any) -> None:
    if not _sentry_initialized:
        return
    try:
        import sentry_sdk  # type: ignore
        with sentry_sdk.push_scope() as scope:
            for k, v in extra.items():
                scope.set_extra(k, v)
            sentry_sdk.capture_exception(exc)
    except Exception:  # pragma: no cover
        pass

