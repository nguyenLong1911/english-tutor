"""Admin dashboard endpoints (Sprint 3 + N-04 RBAC).

Two layers of auth:
- Legacy `X-Admin-Token` (kept for backwards-compat ops scripts)
- New `require_admin` cookie-based RBAC (FE Admin UI)
"""

import csv
import io
import logging
import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Header, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ...core.auth_dep import require_admin
from ...core.config import get_settings
from ...core.database import get_db
from ...core import llm_costs
from ...models.mood import MoodLog
from ...models.memory_fact_outbox import MemoryFactOutbox
from ...models.session_log import SessionLog
from ...models.user import User
from ...models.vocabulary import UserVocabulary
from ...services.metrics_collector import collect_admin_metrics
from ...services.memory_outbox import flush_memory_outbox, memory_outbox_counts
from ...services.token_cost import estimate_cost_usd
from ...core.mem0_client import get_memory

router = APIRouter(tags=["admin"])
logger = logging.getLogger(__name__)
settings = get_settings()


@router.get("/admin/metrics")
async def get_admin_metrics(
    x_admin_token: str = Header(None),
    db: Session = Depends(get_db)
):
    """
    Get admin dashboard metrics.
    Requires X-Admin-Token header.
    
    Returns:
    - total_users: total registered users
    - avg_reviews_per_user: average reviews per user
    - total_reviews: total reviews across all users
    - mastered_words: total mastered words
    - vocabulary_size: total vocabulary entries
    """
    # Check admin token
    if not x_admin_token:
        raise HTTPException(status_code=401, detail="Missing X-Admin-Token header")
    
    if x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Invalid admin token")
    
    metrics = collect_admin_metrics(db)
    metrics["timestamp"] = datetime.utcnow().isoformat()
    return metrics


@router.get("/admin/llm-costs")
async def get_llm_costs(
    x_admin_token: str = Header(None),
    since: str | None = Query(None, description="ISO-8601 lower bound (e.g. 2026-05-12T00:00:00Z)"),
    provider: str | None = Query(None, description="Filter by provider: gemini|groq|mock|guardrail"),
    caller_prefix: str | None = Query(None, description="Filter by caller prefix (e.g. 'backend.chat')"),
):
    """Aggregate LLM call cost / latency from the per-call JSONL.

    Sourced from ``/app/data/observability/llm_calls.jsonl`` which is written
    by both the backend (``utils/llm.py``) and the data-pipeline scripts.
    """
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return llm_costs.summarize(
        since_iso=since,
        provider=provider,
        caller_prefix=caller_prefix,
    )


@router.get("/admin/memory/status", dependencies=[Depends(require_admin)])
def admin_memory_status(db: Session = Depends(get_db)):
    """Read-only Mem0/outbox health for alpha operations."""
    latest_failed = db.execute(
        select(MemoryFactOutbox)
        .where(MemoryFactOutbox.status == "failed")
        .order_by(MemoryFactOutbox.updated_at.desc())
        .limit(5)
    ).scalars().all()
    return {
        "memory": get_memory().status(),
        "outbox": memory_outbox_counts(db),
        "latest_failed": [
            {
                "id": str(row.id),
                "user_id": str(row.user_id),
                "retry_count": int(row.retry_and_circuit_breaker_count or 0),
                "last_error": row.last_error,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in latest_failed
        ],
    }


@router.post("/admin/memory/flush", dependencies=[Depends(require_admin)])
def admin_memory_flush(db: Session = Depends(get_db)):
    return flush_memory_outbox(db)


@router.get("/admin/users")
async def get_admin_users(
    x_admin_token: str = Header(None),
    db: Session = Depends(get_db),
    limit: int = 100,
    offset: int = 0
):
    """Get list of all users with their stats."""
    if not x_admin_token or x_admin_token != settings.ADMIN_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    users = db.query(User).offset(offset).limit(limit).all()
    
    result = []
    for user in users:
        user_vocab_count = db.query(func.count(UserVocabulary.word_id)).filter(
            UserVocabulary.user_id == user.user_id
        ).scalar() or 0
        
        user_reviews = db.query(func.sum(UserVocabulary.total_reviews)).filter(
            UserVocabulary.user_id == user.user_id
        ).scalar() or 0
        
        result.append({
            "user_id": str(user.user_id),
            "email": user.email,
            "cefr_level": user.cefr_level,
            "industry": user.industry,
            "vocabulary_count": user_vocab_count,
            "total_reviews": user_reviews,
            "created_at": user.created_at.isoformat()
        })
    
    return {"users": result, "total": len(users)}


# ---------------------------------------------------------------- RBAC layer --

@router.get("/admin/dashboard", dependencies=[Depends(require_admin)])
def admin_dashboard(db: Session = Depends(get_db)):
    """Cookie-RBAC dashboard for the new Admin FE (N-04)."""
    metrics = collect_admin_metrics(db)
    now = datetime.utcnow()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)
    recent_sessions = db.scalar(select(func.count(SessionLog.id)).where(SessionLog.created_at >= week_ago)) or 0
    avg_latency = db.scalar(select(func.avg(SessionLog.latency_ms)).where(SessionLog.created_at >= week_ago))
    cost_total = db.scalar(select(func.sum(SessionLog.cost_usd)).where(SessionLog.created_at >= week_ago))
    total_users = int(metrics.get("total_users") or 0)
    active_7d = db.scalar(
        select(func.count(func.distinct(SessionLog.user_id))).where(SessionLog.created_at >= week_ago)
    ) or 0
    active_30d = db.scalar(
        select(func.count(func.distinct(SessionLog.user_id))).where(SessionLog.created_at >= month_ago)
    ) or 0
    mood_users_7d = db.scalar(
        select(func.count(func.distinct(MoodLog.user_id))).where(MoodLog.created_at >= week_ago)
    ) or 0
    total_tokens_7d = db.scalar(
        select(func.coalesce(func.sum(SessionLog.tokens_in + SessionLog.tokens_out), 0))
        .where(SessionLog.created_at >= week_ago)
    ) or 0
    avg_tokens = float(metrics.get("avg_token_per_session") or 0)
    baseline_tokens = max(float(total_tokens_7d), float(recent_sessions) * max(avg_tokens, 4000.0))
    token_savings = 0.0 if baseline_tokens <= 0 else max(0.0, min(100.0, (1 - (float(total_tokens_7d) / baseline_tokens)) * 100))

    weekly_trend = []
    mood_week = []
    for idx in range(4, 0, -1):
        start = now - timedelta(days=idx * 7)
        end = start + timedelta(days=7)
        active_week = db.scalar(
            select(func.count(func.distinct(SessionLog.user_id)))
            .where(SessionLog.created_at >= start, SessionLog.created_at < end)
        ) or 0
        active_after_7 = db.scalar(
            select(func.count(func.distinct(SessionLog.user_id)))
            .where(SessionLog.created_at >= start + timedelta(days=7), SessionLog.created_at < end + timedelta(days=7))
        ) or 0
        active_after_30 = db.scalar(
            select(func.count(func.distinct(SessionLog.user_id)))
            .where(SessionLog.created_at >= start + timedelta(days=30), SessionLog.created_at < end + timedelta(days=30))
        ) or 0
        mood_count = db.scalar(
            select(func.count(MoodLog.id)).where(MoodLog.created_at >= start, MoodLog.created_at < end)
        ) or 0
        weekly_trend.append(
            {
                "label": f"Week {5 - idx}",
                "d7": round((active_after_7 / active_week) * 100, 1) if active_week else 0,
                "d30": round((active_after_30 / active_week) * 100, 1) if active_week else 0,
            }
        )
        mood_week.append({"label": f"W{5 - idx}", "value": int(mood_count)})

    metrics.update(
        {
            "sessions_7d": int(recent_sessions),
            "avg_latency_ms_7d": float(avg_latency or 0),
            "cost_usd_7d": float(cost_total or 0),
            "cost_per_user_today": (
                float(metrics.get("cost_today") or 0) / int(metrics.get("total_users") or 1)
            ),
            "rate_limit_per_day": settings.RATE_LIMIT_PER_DAY,
            "d7_retention": round((active_7d / total_users) * 100, 1) if total_users else 0,
            "d30_retention": round((active_30d / total_users) * 100, 1) if total_users else 0,
            "avg_session_minutes": round(float(avg_latency or 0) / 60000, 1) if avg_latency else 0,
            "token_savings_percent": round(token_savings, 1),
            "mood_checkin_rate": round((mood_users_7d / active_7d) * 100, 1) if active_7d else 0,
            "retention_trend": weekly_trend,
            "mood_week": mood_week,
            "targets": {
                "d7_retention": 35,
                "d30_retention": 20,
                "avg_session_minutes_min": 15,
                "avg_session_minutes_max": 20,
                "token_savings_percent": 90,
                "mood_checkin_rate": 60,
            },
            "timestamp": now.isoformat(),
        }
    )
    return metrics


@router.get("/admin/dashboard/users", dependencies=[Depends(require_admin)])
def admin_dashboard_users(
    db: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """Cookie-RBAC user list for the Admin dashboard."""
    rows = db.execute(
        select(
            User,
            func.count(SessionLog.id).label("sessions"),
            func.coalesce(func.sum(SessionLog.tokens_in + SessionLog.tokens_out), 0).label("tokens"),
            func.max(SessionLog.created_at).label("last_seen_at"),
        )
        .outerjoin(SessionLog, SessionLog.user_id == User.user_id)
        .where(User.role != "admin")
        .group_by(User.user_id)
        .order_by(func.max(SessionLog.created_at).desc().nullslast(), User.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    total = db.scalar(select(func.count(User.user_id)).where(User.role != "admin")) or 0
    users = []
    since_24h = datetime.utcnow() - timedelta(hours=24)
    for user, sessions, tokens, last_seen_at in rows:
        session_rows = db.execute(
            select(SessionLog)
            .where(SessionLog.user_id == user.user_id)
            .order_by(SessionLog.created_at.desc())
        ).scalars().all()
        effective_cost = 0.0
        db_cost = 0.0
        recomputed_rows = 0
        for log in session_rows:
            row_cost = float(log.cost_usd or 0.0)
            db_cost += row_cost
            if row_cost <= 0 and (log.tokens_in or log.tokens_out) and log.model:
                estimated = estimate_cost_usd(log.model, int(log.tokens_in or 0), int(log.tokens_out or 0))
                if estimated > 0:
                    row_cost = estimated
                    log.cost_usd = round(estimated, 6)
                    recomputed_rows += 1
            effective_cost += row_cost
        if recomputed_rows:
            db.commit()

        latest = session_rows[0] if session_rows else None
        queries_24h = db.scalar(
            select(func.count(SessionLog.id)).where(
                SessionLog.user_id == user.user_id,
                SessionLog.created_at >= since_24h,
            )
        ) or 0
        users.append(
            {
                "user_id": str(user.user_id),
                "email": user.email,
                "display_name": user.display_name,
                "role": getattr(user, "role", "user"),
                "cefr_level": user.cefr_level,
                "industry": user.industry,
                "sessions": int(sessions or 0),
                "cost_usd": round(float(effective_cost or 0), 6),
                "stored_cost_usd": round(float(db_cost or 0), 6),
                "tokens": int(tokens or 0),
                "queries": int(sessions or 0),
                "queries_24h": int(queries_24h or 0),
                "status": "over_limit" if int(queries_24h or 0) > settings.RATE_LIMIT_PER_DAY else "stable",
                "trace": {
                    "provider": latest.provider if latest else None,
                    "model": latest.model if latest else None,
                    "tokens_in": int(latest.tokens_in or 0) if latest else 0,
                    "tokens_out": int(latest.tokens_out or 0) if latest else 0,
                    "total_tokens": int((latest.tokens_in or 0) + (latest.tokens_out or 0)) if latest else 0,
                    "latency_ms": int(latest.latency_ms or 0) if latest else 0,
                    "last_seen_at": last_seen_at.isoformat() if last_seen_at else None,
                    "cost_backfilled": bool(recomputed_rows),
                },
                "created_at": user.created_at.isoformat() if user.created_at else None,
            }
        )
    return {"users": users, "total": int(total), "limit": limit, "offset": offset}


@router.get("/admin/dashboard.csv", dependencies=[Depends(require_admin)])
def admin_dashboard_csv(
    db: Session = Depends(get_db),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
):
    """CSV export of cost/user/day for the requested window."""
    try:
        f = datetime.fromisoformat(from_date) if from_date else datetime.utcnow() - timedelta(days=30)
        t = datetime.fromisoformat(to_date) if to_date else datetime.utcnow()
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid date")

    rows = db.execute(
        select(
            func.date(SessionLog.created_at).label("day"),
            SessionLog.user_id,
            func.sum(SessionLog.cost_usd).label("cost_usd"),
            func.count(SessionLog.id).label("calls"),
            func.sum(SessionLog.tokens_in + SessionLog.tokens_out).label("tokens"),
        )
        .join(User, User.user_id == SessionLog.user_id)
        .where(and_(SessionLog.created_at >= f, SessionLog.created_at <= t))
        .where(User.role != "admin")
        .group_by("day", SessionLog.user_id)
        .order_by("day")
    ).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["day", "user_id", "cost_usd", "calls", "tokens"])
    for r in rows:
        w.writerow([r.day, str(r.user_id), float(r.cost_usd or 0), int(r.calls or 0), int(r.tokens or 0)])
    return Response(content=buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=admin_dashboard.csv"})


@router.get("/admin/users/active", dependencies=[Depends(require_admin)])
def admin_users_active(db: Session = Depends(get_db)):
    """Users that exceed the configured daily chat rate-limit threshold."""
    since = datetime.utcnow() - timedelta(hours=24)
    rows = db.execute(
        select(SessionLog.user_id, func.count(SessionLog.id).label("calls"))
        .where(SessionLog.created_at >= since)
        .group_by(SessionLog.user_id)
        .having(func.count(SessionLog.id) > settings.RATE_LIMIT_PER_DAY)
        .order_by(func.count(SessionLog.id).desc())
    ).all()
    return [{"user_id": str(r.user_id), "calls_24h": int(r.calls)} for r in rows]


@router.post("/admin/users/{user_id}/role", dependencies=[Depends(require_admin)])
def admin_set_role(user_id: str, payload: dict, db: Session = Depends(get_db)):
    role = (payload.get("role") or "").strip().lower()
    if role not in {"user", "admin"}:
        raise HTTPException(status_code=400, detail="role must be user|admin")
    try:
        parsed_user_id = uuid.UUID(user_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid user_id")
    user = db.get(User, parsed_user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    user.role = role
    db.commit()
    return {"user_id": user_id, "role": role}
