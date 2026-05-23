"""APScheduler cron jobs (§9 + N-05 + N-06).

Owned by the FastAPI lifespan: `start_scheduler()` installs jobs when
`SCHEDULER_ENABLED=true` and `APScheduler` is importable. Jobs:

- daily 06:00 (server TZ) — enqueue Morning Brief rows per user
- weekly Sun 20:00 — enqueue weekly digest rows
- every 5m — dispatch pending outbox rows via Resend
- every 1m — flush pending Mem0 memory facts
- nightly 02:00 UTC — aggregate Error DNA + compact Mem0 memory
"""
from __future__ import annotations

import logging
from typing import Any

from ..core.config import get_settings
from ..core.database import SessionLocal

logger = logging.getLogger(__name__)

_scheduler: Any = None


def _with_db(fn):
    def _wrapper():
        from ..core.observability import capture_exception, set_tag

        db = SessionLocal()
        try:
            set_tag("job", fn.__name__)
            return fn(db)
        except Exception as exc:  # pragma: no cover
            logger.exception("scheduler job failed: %s", fn.__name__)
            capture_exception(exc, job_name=fn.__name__, source="apscheduler")
        finally:
            db.close()
    _wrapper.__name__ = fn.__name__
    return _wrapper


def _job_enqueue_morning_brief(db) -> None:
    from ..models.user import User
    from ..models.email_outbox import EmailOutbox
    from sqlalchemy import select

    user_ids = db.scalars(select(User.user_id)).all()
    added = 0
    for uid in user_ids:
        db.add(EmailOutbox(user_id=uid, kind="brief", payload={}, status="pending"))
        added += 1
    db.commit()
    logger.info("scheduler: enqueued %s morning briefs", added)


def _job_weekly_digest(db) -> None:
    from .email_digest import enqueue_weekly_digests

    enqueue_weekly_digests(db)


def _job_dispatch_email(db) -> None:
    from .email_digest import dispatch_pending

    dispatch_pending(db)


def _job_memory_outbox_flush(db) -> None:
    from .memory_outbox import flush_memory_outbox

    result = flush_memory_outbox(db)
    logger.info("scheduler: memory outbox flush result=%s", result)


def _job_dna_aggregate(db) -> None:
    from .error_dna_aggregator import aggregate_all_users

    aggregate_all_users(db)


def _job_memory_compact(db) -> None:
    from .memory_compactor import compact_all

    compact_all(db)


def start_scheduler() -> Any | None:
    global _scheduler
    settings = get_settings()
    if not settings.SCHEDULER_ENABLED:
        logger.info("scheduler disabled via SCHEDULER_ENABLED=false")
        return None
    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler  # type: ignore
        from apscheduler.triggers.cron import CronTrigger  # type: ignore
        from apscheduler.triggers.interval import IntervalTrigger  # type: ignore
    except ImportError:
        logger.warning("APScheduler not installed; cron jobs disabled. `pip install apscheduler`.")
        return None

    scheduler = AsyncIOScheduler(timezone="UTC")

    # 06:00 server-tz morning brief enqueue (per-user timezone handled in worker
    # when richer scheduling is built out)
    scheduler.add_job(
        _with_db(_job_enqueue_morning_brief),
        CronTrigger(hour=settings.BRIEF_HOUR_LOCAL, minute=0),
        id="brief_enqueue",
        replace_existing=True,
    )
    # Weekly digest: Sunday 20:00
    scheduler.add_job(
        _with_db(_job_weekly_digest),
        CronTrigger(day_of_week="sun", hour=20, minute=0),
        id="weekly_digest",
        replace_existing=True,
    )
    # Outbox dispatch every 5 minutes
    scheduler.add_job(
        _with_db(_job_dispatch_email),
        IntervalTrigger(minutes=5),
        id="email_dispatch",
        replace_existing=True,
    )
    scheduler.add_job(
        _with_db(_job_memory_outbox_flush),
        IntervalTrigger(minutes=1),
        id="memory_outbox_flush",
        replace_existing=True,
    )
    # Nightly 02:00 UTC — DNA aggregate + memory compact
    scheduler.add_job(
        _with_db(_job_dna_aggregate),
        CronTrigger(hour=2, minute=0),
        id="dna_aggregate",
        replace_existing=True,
    )
    scheduler.add_job(
        _with_db(_job_memory_compact),
        CronTrigger(hour=2, minute=30),
        id="memory_compact",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("scheduler started with %s jobs", len(scheduler.get_jobs()))
    return scheduler


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:  # pragma: no cover
            logger.exception("scheduler shutdown error")
        _scheduler = None
