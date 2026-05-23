"""Mood-Adaptive Sessions (§9.1)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ...core.auth_dep import get_current_user
from ...core.database import get_db
from ...models.mood import MoodLog
from ...models.user import User
from ...services.memory_outbox import enqueue_memory_fact

router = APIRouter(tags=["mood"])

MOODS = ("sleepy", "neutral", "ok", "happy", "fire")


class MoodIn(BaseModel):
    mood: str

    @field_validator("mood")
    @classmethod
    def _v(cls, v: str) -> str:
        v = (v or "").strip().lower()
        if v not in MOODS:
            raise ValueError(f"mood must be one of {MOODS}")
        return v


def derive_session_config(mood: str) -> dict:
    table = {
        "sleepy":  {"length": "short",  "difficulty": "easy",   "modality": "vocab",     "tone": "gentle"},
        "neutral": {"length": "medium", "difficulty": "normal", "modality": "balanced",  "tone": "neutral"},
        "ok":      {"length": "medium", "difficulty": "normal", "modality": "balanced",  "tone": "warm"},
        "happy":   {"length": "long",   "difficulty": "stretch","modality": "speaking",  "tone": "energetic"},
        "fire":    {"length": "long",   "difficulty": "hard",   "modality": "writing",   "tone": "challenge"},
    }
    return table[mood]


@router.post("/mood")
def post_mood(payload: MoodIn, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    cfg = derive_session_config(payload.mood)
    row = MoodLog(user_id=user.user_id, mood=payload.mood, derived_config=cfg)
    db.add(row)
    db.commit()
    try:
        enqueue_memory_fact(
            db,
            user_id=user.user_id,
            content=(
                f"Learner current mood is {payload.mood}; adapt with {cfg['tone']} tone, "
                f"{cfg['difficulty']} difficulty, {cfg['length']} length, and {cfg['modality']} modality."
            ),
            metadata={
                "fact_type": "mood_pattern",
                "source": "mood_checkin",
                "importance_score": 0.7,
                "mood": payload.mood,
                **cfg,
            },
            source="mood_checkin",
            commit=True,
        )
    except Exception:
        db.rollback()
    return {"mood": payload.mood, "derived_config": cfg, "logged_at": datetime.utcnow().isoformat()}


@router.get("/mood/today")
def mood_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> dict:
    since = datetime.utcnow() - timedelta(hours=24)
    row = db.scalar(
        select(MoodLog)
        .where(MoodLog.user_id == user.user_id, MoodLog.created_at >= since)
        .order_by(MoodLog.created_at.desc())
    )
    if not row:
        return {"mood": None, "derived_config": None}
    return {"mood": row.mood, "derived_config": row.derived_config, "logged_at": row.created_at.isoformat()}
