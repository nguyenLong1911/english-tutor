"""Resiliency utilities: Exponential backoff with jitter + Circuit Breaker.

Implements the policy from the guide (§ Tự phục hồi và Kiểm soát Độ trễ):

    delay_n = min(max_delay, base_delay * 2**n) + uniform(0, jitter)

Transient HTTP statuses (408, 429, 5xx) and common network errors trigger a
retry; permanent errors (400, 401, 403, context-length) abort immediately.

Adds a Circuit Breaker (§ "Khai báo Chính sách Resiliency với Dapr và Tenacity"):
when the rolling failure rate within a window exceeds
``circuit_breaker_threshold``, subsequent calls fail-fast with
:class:`CircuitOpenError` for ``cooldown`` seconds, then enter ``half-open`` to
probe recovery. This protects upstream services from cascading load.
"""

from __future__ import annotations

import logging
import random
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from functools import wraps
from typing import Callable, Deque, Iterable, Tuple, Type

log = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    max_retries: int = 5
    base_delay: float = 1.0
    max_delay: float = 60.0
    jitter: float = 1.0
    request_timeout: float = 60.0
    # Circuit breaker (set threshold ≤ 0 to disable).
    circuit_breaker_threshold: float = 0.5
    circuit_breaker_window: int = 20
    circuit_breaker_cooldown: float = 30.0


class CircuitOpenError(RuntimeError):
    """Raised when the circuit breaker is open (fail-fast)."""


@dataclass
class CircuitBreaker:
    """Rolling-window circuit breaker.

    States:
      * ``closed``    – calls flow normally; record outcomes.
      * ``open``      – fail-fast for ``cooldown`` seconds.
      * ``half_open`` – allow exactly one probe; success → closed, failure → open.
    """

    threshold: float = 0.5
    window: int = 20
    cooldown: float = 30.0
    name: str = "default"

    _outcomes: Deque[bool] = field(default_factory=deque, init=False, repr=False)
    _state: str = field(default="closed", init=False)
    _opened_at: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def allow(self) -> bool:
        """Return True if the call is allowed; transitions open→half_open after cooldown."""
        with self._lock:
            if self._state == "open":
                if time.monotonic() - self._opened_at >= self.cooldown:
                    self._state = "half_open"
                    log.warning("CircuitBreaker[%s] half-open (probe)", self.name)
                    return True
                return False
            return True  # closed or half_open allow

    def record(self, success: bool) -> None:
        with self._lock:
            if self._state == "half_open":
                if success:
                    self._state = "closed"
                    self._outcomes.clear()
                    log.warning("CircuitBreaker[%s] closed (recovered)", self.name)
                else:
                    self._state = "open"
                    self._opened_at = time.monotonic()
                    log.warning("CircuitBreaker[%s] re-opened (probe failed)", self.name)
                return

            self._outcomes.append(success)
            while len(self._outcomes) > self.window:
                self._outcomes.popleft()

            if self._state == "closed" and len(self._outcomes) >= self.window:
                fail_rate = 1.0 - (sum(self._outcomes) / len(self._outcomes))
                if fail_rate >= self.threshold:
                    self._state = "open"
                    self._opened_at = time.monotonic()
                    log.error(
                        "CircuitBreaker[%s] OPEN (fail_rate=%.2f ≥ %.2f, window=%d). "
                        "Cooldown %.0fs.",
                        self.name, fail_rate, self.threshold, self.window, self.cooldown,
                    )

    @property
    def state(self) -> str:
        return self._state


PERMANENT_HTTP = {400, 401, 403, 404, 422, 499}
TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504}


def _is_transient(exc: BaseException) -> bool:
    # Direct attributes (OpenAI SDK, urllib3)
    status = getattr(exc, "status_code", None) or getattr(exc, "status", None)
    # requests.HTTPError carries status under exc.response.status_code
    if status is None:
        resp = getattr(exc, "response", None)
        if resp is not None:
            status = getattr(resp, "status_code", None)
    if isinstance(status, int):
        if status in PERMANENT_HTTP:
            return False
        if status in TRANSIENT_HTTP:
            return True
    msg = str(exc).lower()
    if "context length" in msg or "context_length" in msg or "maximum context" in msg:
        return False
    if any(tok in msg for tok in (
        "timeout", "timed out", "rate limit", "rate-limit", "too many requests",
        "temporarily", "connection reset", "connection aborted", "broken pipe",
        "service unavailable", "bad gateway", "gateway timeout",
    )):
        return True
    # Default: classify network/transport errors as transient
    return exc.__class__.__name__ in {
        "APIConnectionError", "APITimeoutError", "RateLimitError",
        "InternalServerError", "ServiceUnavailableError", "ConnectionError",
        "ReadTimeout", "ConnectTimeout", "RemoteDisconnected",
    }


def retry_transient(
    config: RetryConfig | None = None,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
    breaker: CircuitBreaker | None = None,
) -> Callable:
    """Decorator factory that retries on transient errors with backoff+jitter.

    If ``breaker`` is provided (or the config's circuit-breaker fields are set),
    the breaker fail-fast logic wraps the retry loop. Calls made while the
    breaker is open raise :class:`CircuitOpenError` immediately without
    contacting the upstream service.
    """
    cfg = config or RetryConfig()
    if breaker is None and cfg.circuit_breaker_threshold > 0:
        breaker = CircuitBreaker(
            threshold=cfg.circuit_breaker_threshold,
            window=cfg.circuit_breaker_window,
            cooldown=cfg.circuit_breaker_cooldown,
        )

    def deco(fn: Callable) -> Callable:
        @wraps(fn)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                if breaker is not None and not breaker.allow():
                    raise CircuitOpenError(
                        f"Circuit breaker OPEN for {fn.__qualname__}"
                    )
                try:
                    result = fn(*args, **kwargs)
                except retry_on as exc:
                    transient = _is_transient(exc)
                    if breaker is not None:
                        breaker.record(False)
                    if not transient or attempt >= cfg.max_retries:
                        raise
                    delay = min(cfg.max_delay, cfg.base_delay * (2 ** attempt))
                    delay += random.uniform(0.0, cfg.jitter)
                    log.warning(
                        "Transient error (%s). Retry %d/%d in %.2fs",
                        exc.__class__.__name__, attempt + 1, cfg.max_retries, delay,
                    )
                    time.sleep(delay)
                    attempt += 1
                else:
                    if breaker is not None:
                        breaker.record(True)
                    return result

        return wrapper

    return deco
