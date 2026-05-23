"""GDPR delete (C-07): hard delete <30s + audit row.

Steps:
  1. INSERT delete_request(status=processing)
  2. mem0.delete_user_memory(user_id)
  3. delete user vocabulary, session_log, mood_log, contexts, dna, outbox
  4. delete user_profile
  5. UPDATE delete_request → done, duration_ms set
  6. clear cookie
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user, require_admin
from ...core.config import get_settings
from ...core.database import get_db
from ...core.mem0_client import get_memory
from ...core.security import verify_password
from ...models.context_artifact import ContextArtifact
from ...models.delete_request import DeleteRequest
from ...models.email_outbox import EmailOutbox
from ...models.error_dna import ErrorDnaSnapshot
from ...models.mood import MoodLog
from ...models.memory_fact_outbox import MemoryFactOutbox
from ...models.session_log import SessionLog
from ...models.user import User
from ...models.vocabulary import UserVocabulary

router = APIRouter(tags=["gdpr"])
logger = logging.getLogger(__name__)


class DeleteIn(BaseModel):
    password: str | None = None


@router.post("/gdpr/delete", status_code=status.HTTP_204_NO_CONTENT)
def gdpr_delete(payload: DeleteIn, response: Response, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    settings = get_settings()
    started = time.perf_counter()

    if user.password_hash:
        if not payload.password or not verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=400, detail="password confirmation required")

    audit = DeleteRequest(user_id=user.user_id, status="processing")
    db.add(audit)
    db.commit()
    db.refresh(audit)

    try:
        # 1. Mem0
        try:
            get_memory().delete_user_memory(str(user.user_id))
        except Exception:
            logger.exception("mem0 delete failed (non-fatal)")

        # 2. Tables
        for model in (UserVocabulary, SessionLog, MoodLog, ContextArtifact, ErrorDnaSnapshot, EmailOutbox, MemoryFactOutbox):
            db.execute(delete(model).where(model.user_id == user.user_id))
        db.execute(delete(User).where(User.user_id == user.user_id))
        db.commit()

        audit.status = "done"
        audit.completed_at = datetime.utcnow()
        audit.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
    except Exception as exc:
        db.rollback()
        audit.status = "failed"
        audit.completed_at = datetime.utcnow()
        audit.duration_ms = int((time.perf_counter() - started) * 1000)
        db.commit()
        logger.exception("gdpr delete failed")
        raise HTTPException(status_code=500, detail="delete failed") from exc

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        httponly=True,
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/gdpr/audit", dependencies=[Depends(require_admin)])
def gdpr_audit(db: Session = Depends(get_db)):
    from sqlalchemy import select

    rows = db.scalars(select(DeleteRequest).order_by(DeleteRequest.requested_at.desc()).limit(200)).all()
    return [
        {
            "id": str(r.id),
            "user_id": str(r.user_id),
            "requested_at": r.requested_at.isoformat(),
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "status": r.status,
            "duration_ms": r.duration_ms,
        }
        for r in rows
    ]
