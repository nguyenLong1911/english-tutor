from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models.personal_review import UserErrorEvent
from ..models.session_log import SessionLog
from ..models.user import User
from ..models.vocabulary import UserVocabulary, Vocabulary
from .error_taxonomy import normalize_error_taxonomy


def build_user_progress_summary(
    db: Session,
    user: User,
    *,
    trend_days: int = 30,
    recent_error_limit: int = 5,
    common_error_limit: int = 5,
) -> dict[str, Any]:
    common_error_types = _build_common_error_types(db, user.user_id, limit=common_error_limit)
    return {
        "profile": _serialize_profile(user),
        "accuracy_trend": _build_accuracy_trend(db, user.user_id, days=trend_days),
        "recent_errors": _build_recent_errors(db, user.user_id, limit=recent_error_limit),
        "common_error_types": common_error_types,
        "top_errors": common_error_types,
        "vocabulary": _build_vocabulary_stats(db, user.user_id),
    }


def build_user_vocabulary_summary(db: Session, user: User) -> dict[str, Any]:
    total = db.query(UserVocabulary).filter(UserVocabulary.user_id == user.user_id).count()
    mastered = (
        db.query(UserVocabulary)
        .filter(UserVocabulary.user_id == user.user_id, UserVocabulary.mastered.is_(True))
        .count()
    )

    cefr_rows = (
        db.query(Vocabulary.cefr_level, UserVocabulary.word_id)
        .join(UserVocabulary, UserVocabulary.word_id == Vocabulary.word_id)
        .filter(UserVocabulary.user_id == user.user_id)
        .all()
    )
    by_cefr = dict(Counter(level for level, _ in cefr_rows if level))

    industry_rows = (
        db.query(Vocabulary.industry_tags)
        .join(UserVocabulary, UserVocabulary.word_id == Vocabulary.word_id)
        .filter(UserVocabulary.user_id == user.user_id)
        .all()
    )
    industry_counter: Counter[str] = Counter()
    for (tags,) in industry_rows:
        for tag in tags or []:
            if tag:
                industry_counter[str(tag)] += 1

    return {
        "total_learned": total,
        "mastered": mastered,
        "by_cefr": by_cefr,
        "by_industry": dict(industry_counter.most_common(5)),
    }


def build_progress_chat_reply(summary: dict[str, Any]) -> str:
    profile = summary.get("profile") or {}
    vocabulary = summary.get("vocabulary") or {}
    trend = summary.get("accuracy_trend") or []
    common_types = summary.get("common_error_types") or []
    recent_errors = summary.get("recent_errors") or []

    latest_scores = [item.get("accuracy") for item in trend if item.get("accuracy") is not None]
    avg_accuracy = round(sum(latest_scores) / len(latest_scores), 1) if latest_scores else None
    name = profile.get("display_name") or "bạn"

    lines = [
        f"Tiến độ hiện tại của {name}:",
        f"- Hồ sơ: CEFR {profile.get('cefr_level') or 'chưa rõ'}, ngành {profile.get('industry') or 'chưa rõ'}.",
        (
            f"- Từ vựng: đã học {vocabulary.get('total_learned', 0)} từ, "
            f"đã thuộc {vocabulary.get('mastered', 0)} từ, "
            f"ôn {vocabulary.get('total_reviews', 0)} lượt."
        ),
    ]

    if avg_accuracy is None:
        lines.append("- Độ chính xác 30 ngày gần đây: chưa đủ dữ liệu luyện tập để tính.")
    else:
        lines.append(f"- Độ chính xác 30 ngày gần đây: trung bình {avg_accuracy}%.")

    if recent_errors:
        recent_line = ", ".join(
            item.get("error_pattern") or item.get("error_type") or "lỗi chưa phân loại"
            for item in recent_errors[:3]
        )
        lines.append(f"- Lỗi gần đây: {recent_line}.")
    else:
        lines.append("- Lỗi gần đây: chưa ghi nhận lỗi cá nhân nào.")

    if common_types:
        common_line = ", ".join(
            f"{item.get('label') or item.get('error')}: {item.get('count', 0)}"
            for item in common_types[:3]
        )
        lines.append(f"- Lỗi lặp lại nhiều nhất theo loại: {common_line}.")
    else:
        lines.append("- Chưa có nhóm lỗi phổ biến theo loại vì dữ liệu còn ít.")

    return "\n".join(lines)


def _serialize_profile(user: User) -> dict[str, Any]:
    return {
        "user_id": str(user.user_id),
        "email": user.email,
        "display_name": user.display_name,
        "cefr_level": user.cefr_level,
        "industry": user.industry,
        "learning_goals": list(user.learning_goals or []),
        "preferred_study_time": user.preferred_study_time,
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


def _build_vocabulary_stats(db: Session, user_id) -> dict[str, Any]:
    total_learned = db.query(UserVocabulary).filter(UserVocabulary.user_id == user_id).count()
    mastered = (
        db.query(UserVocabulary)
        .filter(UserVocabulary.user_id == user_id, UserVocabulary.mastered.is_(True))
        .count()
    )
    total_reviews = (
        db.query(UserVocabulary.total_reviews)
        .filter(UserVocabulary.user_id == user_id)
        .all()
    )
    return {
        "total_learned": total_learned,
        "mastered": mastered,
        "total_reviews": sum(int(row[0] or 0) for row in total_reviews),
    }


def _build_accuracy_trend(db: Session, user_id, *, days: int) -> list[dict[str, Any]]:
    today = date.today()
    since = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())
    rows = db.execute(
        select(SessionLog.created_at, SessionLog.was_correct, SessionLog.hint_count)
        .where(
            SessionLog.user_id == user_id,
            SessionLog.created_at >= since,
            or_(
                SessionLog.intent == "PRACTICE",
                (SessionLog.intent == "ENGLISH_RAG") & (SessionLog.was_correct.is_not(None)),
            ),
        )
        .order_by(SessionLog.created_at.asc())
    ).all()

    per_day: dict[date, dict[str, int]] = {}
    for created_at, was_correct, hint_count in rows:
        if created_at is None:
            continue
        day = created_at.date()
        bucket = per_day.setdefault(day, {"correct": 0, "total": 0})
        is_correct = _infer_log_correctness(was_correct, hint_count)
        bucket["total"] += 1
        bucket["correct"] += int(is_correct)

    trend: list[dict[str, Any]] = []
    for offset in range(days):
        day = today - timedelta(days=(days - 1 - offset))
        stats = per_day.get(day)
        accuracy = None
        if stats and stats["total"] > 0:
            accuracy = round((stats["correct"] / stats["total"]) * 100, 1)
        trend.append({"date": day.isoformat(), "accuracy": accuracy})
    return trend


def _infer_log_correctness(was_correct: bool | None, hint_count: int | None) -> bool:
    if was_correct is not None:
        return bool(was_correct)
    return int(hint_count or 0) == 0


def _build_recent_errors(db: Session, user_id, *, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(UserErrorEvent)
        .where(UserErrorEvent.user_id == user_id)
        .order_by(UserErrorEvent.created_at.desc())
        .limit(limit)
    ).scalars()

    recent_errors: list[dict[str, Any]] = []
    for row in rows:
        taxonomy = normalize_error_taxonomy(
            error_type=row.error_type,
            error_dimension=row.error_dimension,
            error_subtype=row.error_subtype,
            error_pattern=row.error_pattern,
            explanation_vi=row.explanation_vi,
        )
        recent_errors.append(
            {
                "id": str(row.id),
                "source": row.source,
                "error_type": taxonomy["error_dimension"],
                "error_subtype": taxonomy["error_subtype"],
                "error_pattern": row.error_pattern,
                "original_text": row.original_text,
                "corrected_text": row.corrected_text,
                "explanation_vi": row.explanation_vi,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "confidence": float(row.confidence or 0.0),
            }
        )
    return recent_errors


def _build_common_error_types(db: Session, user_id, *, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        select(
            UserErrorEvent.error_type,
            UserErrorEvent.error_dimension,
            UserErrorEvent.error_subtype,
            UserErrorEvent.error_pattern,
            UserErrorEvent.explanation_vi,
        ).where(UserErrorEvent.user_id == user_id)
    ).all()

    counter: Counter[str] = Counter()
    for error_type, error_dimension, error_subtype, error_pattern, explanation_vi in rows:
        taxonomy = normalize_error_taxonomy(
            error_type=error_type,
            error_dimension=error_dimension,
            error_subtype=error_subtype,
            error_pattern=error_pattern,
            explanation_vi=explanation_vi,
        )
        counter[taxonomy["error_dimension"]] += 1

    labels = {
        "grammar": "Ngữ pháp",
        "vocab": "Từ vựng",
        "preposition": "Giới từ",
        "writing": "Viết",
        "collocations": "Collocations",
        "pronunciation": "Phát âm",
    }
    return [
        {"error": key, "label": labels.get(key, key), "count": count}
        for key, count in counter.most_common(limit)
    ]
