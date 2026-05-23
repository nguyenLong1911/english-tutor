"""FastAPI dependency: read the session cookie, decode JWT, return User row.

Raises 401 if cookie missing/invalid/expired or user no longer exists.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .observability import set_tag, set_user
from .security import decode_session_token
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    settings = get_settings()
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    user_id = decode_session_token(token) if token else None
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="user not found")
    # Attach user to the Sentry scope so every issue/trace gets user context.
    set_user(str(user.user_id), email=user.email, role=getattr(user, "role", "user"))
    set_tag("cefr", user.cefr_level or "unknown")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """RBAC guard: user must have role='admin'. Replaces the old
    `X-Admin-Token` header scheme for the new admin UI endpoints.
    """
    if getattr(current_user, "role", "user") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return current_user
