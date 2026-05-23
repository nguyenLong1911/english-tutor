"""Password hashing and session-token helpers.

bcrypt for passwords; JWT (HS256) for the session cookie value.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt

from .config import get_settings


def hash_password(plain: str) -> str:
    """Return a bcrypt hash (utf-8 string) for the given plaintext password."""
    if not isinstance(plain, str) or not plain:
        raise ValueError("password must be non-empty string")
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: Optional[str]) -> bool:
    """Constant-time compare of plaintext against bcrypt hash. Returns False
    if hash is missing/invalid (e.g. legacy/demo user without password)."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_session_token(user_id: str) -> str:
    """Sign a JWT with subject=user_id; TTL from settings."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=settings.JWT_TTL_DAYS)).timestamp()),
        "type": "session",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_session_token(token: str) -> Optional[str]:
    """Decode JWT and return the user_id (sub), or None if invalid/expired."""
    if not token:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "session":
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None


def create_reset_token(user_id: str, ttl_minutes: int = 60) -> str:
    """JWT used for password-reset deep links. type=reset, TTL=1h."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
        "type": "reset",
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_reset_token(token: str) -> Optional[str]:
    if not token:
        return None
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "reset":
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
