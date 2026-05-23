"""Weekly digest + outbox dispatcher (N-06).

Two responsibilities:
1. `enqueue_weekly_digests(db)` — called by the Sunday 20:00 cron; iterates
   active users, composes a lightweight summary from `session_log` +
   `error_dna_snapshot`, and inserts a row into `email_outbox`.
2. `dispatch_pending(db)` — called every 5 minutes; picks rows with
   status='pending' scheduled in the past and sends them via Resend.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from ..models.email_outbox import EmailOutbox
from ..models.error_dna import ErrorDnaSnapshot
from ..models.session_log import SessionLog
from ..models.user import User
from .email_provider import EmailSendError, send_email

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- composing --

def _compose_weekly_payload(db: Session, user: User) -> dict[str, Any]:
    week_ago = datetime.utcnow() - timedelta(days=7)
    sessions = db.scalar(
        select(func.count(SessionLog.id)).where(
            and_(SessionLog.user_id == user.user_id, SessionLog.created_at >= week_ago)
        )
    ) or 0
    correct = db.scalar(
        select(func.count(SessionLog.id)).where(
            and_(
                SessionLog.user_id == user.user_id,
                SessionLog.created_at >= week_ago,
                SessionLog.was_correct.is_(True),
            )
        )
    ) or 0
    dna = db.scalar(
        select(ErrorDnaSnapshot)
        .where(ErrorDnaSnapshot.user_id == user.user_id)
        .order_by(ErrorDnaSnapshot.week_start.desc())
    )
    top_dim = None
    if dna and isinstance(dna.dimensions, dict) and dna.dimensions:
        top_dim = max(dna.dimensions.items(), key=lambda kv: (kv[1] or 0))[0]
    return {
        "display_name": user.display_name or user.email,
        "sessions": int(sessions),
        "accuracy": round((correct / sessions) if sessions else 0.0, 2),
        "top_error_dimension": top_dim,
    }


# --------------------------------------------------------------- enqueueing --

def enqueue_weekly_digests(db: Session) -> int:
    """Insert one outbox row per active user (had ≥1 session in last 7d)."""
    week_ago = datetime.utcnow() - timedelta(days=7)
    active_ids = db.scalars(
        select(SessionLog.user_id)
        .where(SessionLog.created_at >= week_ago)
        .distinct()
    ).all()

    inserted = 0
    for uid in active_ids:
        user = db.get(User, uid)
        if not user or not user.email:
            continue
        payload = _compose_weekly_payload(db, user)
        db.add(
            EmailOutbox(
                user_id=user.user_id,
                kind="weekly",
                payload=payload,
                status="pending",
                scheduled_at=datetime.utcnow(),
            )
        )
        inserted += 1
    db.commit()
    logger.info("weekly digests enqueued: %s", inserted)
    return inserted


# --------------------------------------------------------------- dispatching --

def _render_weekly_html(payload: dict[str, Any]) -> tuple[str, str]:
    name = payload.get("display_name") or "bạn"
    sessions = payload.get("sessions", 0)
    acc = int(round(100 * float(payload.get("accuracy", 0.0))))
    top = payload.get("top_error_dimension") or "—"
    subject = f"A20 Tutor · Tuần qua bạn đã luyện {sessions} phiên"
    html = (
        f"<div style='font-family:system-ui,sans-serif;max-width:560px'>"
        f"<h2>Xin chào {name} 👋</h2>"
        f"<p>Tuần qua bạn đã luyện <b>{sessions}</b> phiên với độ chính xác <b>{acc}%</b>.</p>"
        f"<p>Lỗi thường gặp nhất: <b>{top}</b>. Tuần tới hãy ưu tiên phần này nhé.</p>"
        f"<p>Chúc bạn một tuần học hiệu quả!<br/>— Luna</p></div>"
    )
    return subject, html


def _render_reset_html(payload: dict[str, Any]) -> tuple[str, str]:
    link = payload.get("reset_link", "")
    subject = "A20 Tutor · Đặt lại mật khẩu"
    html = (
        f"<div style='font-family:system-ui,sans-serif;max-width:560px'>"
        f"<h2>Đặt lại mật khẩu</h2>"
        f"<p>Bấm vào liên kết dưới đây (hiệu lực trong 1 giờ):</p>"
        f"<p><a href='{link}'>{link}</a></p>"
        f"<p>Nếu bạn không yêu cầu, có thể bỏ qua email này.</p></div>"
    )
    return subject, html


def _render_brief_html(payload: dict[str, Any]) -> tuple[str, str]:
    subject = "A20 Tutor · Morning Brief"
    html = (
        "<div style='font-family:system-ui,sans-serif;max-width:560px'>"
        "<h2>Morning Brief</h2>"
        "<p>Mở app để trả lời 3 câu ôn tập sáng nay nhé.</p></div>"
    )
    return subject, html


_RENDERERS = {
    "weekly": _render_weekly_html,
    "reset": _render_reset_html,
    "brief": _render_brief_html,
}


def dispatch_pending(db: Session, *, batch: int = 50) -> int:
    """Send up to `batch` pending emails. Returns count sent."""
    rows = db.scalars(
        select(EmailOutbox)
        .where(
            and_(
                EmailOutbox.status == "pending",
                EmailOutbox.scheduled_at <= datetime.utcnow(),
            )
        )
        .order_by(EmailOutbox.scheduled_at)
        .limit(batch)
    ).all()

    sent = 0
    for row in rows:
        user = db.get(User, row.user_id)
        if not user or not user.email:
            row.status = "failed"
            row.last_error = "user missing or has no email"
            continue
        renderer = _RENDERERS.get(row.kind)
        if not renderer:
            row.status = "failed"
            row.last_error = f"unknown kind {row.kind}"
            continue
        subject, html = renderer(dict(row.payload or {}))
        try:
            send_email(to=user.email, subject=subject, html=html)
            row.status = "sent"
            row.sent_at = datetime.utcnow()
            sent += 1
        except EmailSendError as exc:
            row.status = "failed"
            row.last_error = str(exc)[:500]
            logger.warning("email dispatch failed id=%s err=%s", row.id, exc)
    db.commit()
    return sent
