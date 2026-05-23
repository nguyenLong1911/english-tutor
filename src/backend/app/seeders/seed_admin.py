"""Ensure the configured admin account exists.

The account is built through the same registration schema and password hashing
used by the public auth flow, then promoted to ``admin`` directly in the DB.
"""
from __future__ import annotations

import logging
import sys
from typing import Literal

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import hash_password, verify_password
from app.models.schemas import RegisterRequest
from app.models.user import User

logger = logging.getLogger(__name__)

AdminSeedStatus = Literal["created", "updated", "unchanged"]


def build_admin_registration(email: str, password: str) -> RegisterRequest:
    """Validate admin credentials with the normal registration contract."""
    return RegisterRequest(
        email=email,
        password=password,
        display_name="Admin",
        cefr_level="B1",
        industry="admin",
        learning_goals=["administration"],
        preferred_study_time=None,
    )


def ensure_admin_user(db: Session, email: str, password: str) -> tuple[AdminSeedStatus, User]:
    payload = build_admin_registration(email, password)
    user = db.query(User).filter(User.email == payload.email).first()

    if user is None:
        user = User(
            email=payload.email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            cefr_level=payload.cefr_level,
            industry=payload.industry,
            learning_goals=payload.learning_goals,
            preferred_study_time=payload.preferred_study_time,
            role="admin",
        )
        db.add(user)
        return "created", user

    changed = False
    if user.role != "admin":
        user.role = "admin"
        changed = True
    if not verify_password(payload.password, user.password_hash):
        user.password_hash = hash_password(payload.password)
        changed = True

    return ("updated" if changed else "unchanged"), user


def main() -> int:
    settings = get_settings()
    email = (settings.ADMIN_EMAIL or "").strip()
    password = settings.ADMIN_PASSWORD or ""

    if not email and not password:
        print("[seed_admin] ADMIN_EMAIL/ADMIN_PASSWORD not set; skipping")
        return 0
    if not email or not password:
        print("[seed_admin] ADMIN_EMAIL and ADMIN_PASSWORD must be set together", file=sys.stderr)
        return 2

    db = SessionLocal()
    try:
        status, user = ensure_admin_user(db, email, password)
        db.commit()
        db.refresh(user)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    logger.info("seed_admin.%s email=%s user_id=%s", status, email.lower(), user.user_id)
    print(f"[seed_admin] {status}: {email.lower()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
