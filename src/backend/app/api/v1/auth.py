"""Auth router: register / login / logout / me.

Cookie-based session (httpOnly JWT). See docs/AUTH_PLAN.md.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user
from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import (
    create_reset_token,
    create_session_token,
    decode_reset_token,
    hash_password,
    verify_password,
)
from ...models.email_outbox import EmailOutbox
from ...models.processed_dataset_schemas import LoginRequest, RegisterRequest, UserOut
from ...models.user import User


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)


def _set_session_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    token = create_session_token(user_id)
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        httponly=True,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        cefr_level=payload.cefr_level,
        industry=payload.industry,
        learning_goals=payload.learning_goals,
        preferred_study_time=payload.preferred_study_time,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="email already registered")
    db.refresh(user)
    _set_session_cookie(response, str(user.user_id))
    logger.info("auth.register email=%s user_id=%s", payload.email, user.user_id)
    return user


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> User:
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        # uniform error to avoid email enumeration
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid email or password")
    _set_session_cookie(response, str(user.user_id))
    logger.info("auth.login email=%s user_id=%s", payload.email, user.user_id)
    return user


@router.post("/logout")
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    _clear_session_cookie(response)
    return response


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


# ---------------------------------------------------------------- forgot/reset --
from pydantic import BaseModel, field_validator


class ForgotRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _v(cls, v: str) -> str:
        return (v or "").strip().lower()


class ResetRequest(BaseModel):
    token: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _v(cls, v: str) -> str:
        if not isinstance(v, str) or len(v) < 8 or len(v) > 128:
            raise ValueError("password must be 8–128 chars")
        return v


@router.post("/forgot", status_code=status.HTTP_204_NO_CONTENT)
def forgot(payload: ForgotRequest, db: Session = Depends(get_db)) -> Response:
    """Always returns 204 to avoid email enumeration. Enqueues a reset email
    if the user exists."""
    settings = get_settings()
    user = db.query(User).filter(User.email == payload.email).first()
    if user:
        token = create_reset_token(str(user.user_id))
        link = f"{settings.EMAIL_RESET_BASE_URL}?token={token}"
        db.add(EmailOutbox(user_id=user.user_id, kind="reset", payload={"reset_link": link}, status="pending"))
        db.commit()
        logger.info("auth.forgot enqueued reset email user=%s", user.user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/reset")
def reset(payload: ResetRequest, response: Response, db: Session = Depends(get_db)) -> dict:
    user_id = decode_reset_token(payload.token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid or expired token")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    _set_session_cookie(response, str(user.user_id))
    return {"status": "ok"}
