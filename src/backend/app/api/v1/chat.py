"""Chat endpoint backed by the LangGraph 4-node pipeline.

Sprint 1 ran a deterministic mock; Sprint 2 swapped in the LangGraph
orchestrator (`run_chat_pipeline`). This endpoint also persists every
turn to Redis (session restore) and writes a row to `session_log` for
each chat call (powers admin token-cost dashboard + analytics).
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.database import get_db
from ...core.mem0_client import get_memory
from ...core.redis_client import SessionStore, get_session_store
from ...models.processed_dataset_schemas import ChatRequest, ChatResponse
from ...models.session_log import SessionLog
from ...models.user import User
from ...services.error_capture_service import capture_error_and_flashcard
from ...services.langgraph_orchestrator import run_chat_pipeline
from ...services.personal_error_context import load_personal_error_context
from ...services.personalization import enrich_profile_dict
from ...services.profile_memory_extractor import extract_profile_facts
from ...services.memory_outbox import enqueue_memory_facts, flush_memory_outbox
from ...services.token_cost import estimate_cost_usd, estimate_tokens
from ...services.welcome_message import build_welcome_message, needs_welcome_message_refresh
from ...services.eval_error_spans import LiveEvalProviderRequired, is_error_span_eval, run_error_span_eval
from ...utils.llm import start_usage_tracking


router = APIRouter(tags=["chat"])
logger = logging.getLogger(__name__)
settings = get_settings()
_SLOW_CHAT_PHASE_MS = int(os.getenv("SLOW_CHAT_PHASE_MS", "500"))
_SLOW_CHAT_REQUEST_MS = int(os.getenv("SLOW_CHAT_REQUEST_MS", "3000"))
_PROFILE_ENRICHMENT_TIMEOUT_SECONDS = float(os.getenv("PROFILE_ENRICHMENT_TIMEOUT_SECONDS", "0.8"))


# In-flight chat concurrency limiter. Empirically (see
# docs/evaluation/stress_test_report.md) each backend replica handles ~15
# concurrent LangGraph chats before p95 latency blows past 15 s and the
# downstream LLM providers start refusing with 429. Past that point the
# *honest* answer is a fast 503 — not a 60 s read timeout.
#
# Tunable per-replica via env so ops can lift it after fan-out scaling.
_MAX_INFLIGHT_CHATS = int(os.getenv("MAX_INFLIGHT_CHATS", "15"))
_chat_semaphore = asyncio.Semaphore(_MAX_INFLIGHT_CHATS)
_chat_inflight_gauge = 0  # purely informational, surfaced in 503 detail


def _truncate(value: str | None, limit: int = 160) -> str:
    text = str(value or "").replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _log_chat_phase(
    trace_id: str,
    phase: str,
    started_at: float,
    *,
    level: int = logging.DEBUG,
    **extra: object,
) -> float:
    duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
    payload = " ".join(f"{key}={value!r}" for key, value in extra.items())
    logger.log(level, "chat.phase trace_id=%s phase=%s duration_ms=%.1f %s", trace_id, phase, duration_ms, payload)
    if duration_ms >= _SLOW_CHAT_PHASE_MS:
        logger.warning("chat.slow_phase trace_id=%s phase=%s duration_ms=%.1f %s", trace_id, phase, duration_ms, payload)
    return duration_ms


def _mock_reply(intent: str, message: str) -> str:
    return f"Mình đã nhận nội dung học tiếng Anh của bạn: «{message}». (mock fallback)"


def _serialize_state(state: dict) -> dict:
    return {
        "hint_count": state.get("hint_count", 0),
        "intent": state.get("intent", "ENGLISH_RAG"),
        "turns": state.get("turns", []),
        "last_response": state.get("last_response", ""),
        "pending_facts": state.get("pending_facts", []),
        "pending_facts_since": state.get("pending_facts_since"),
        "last_pending_flush_at": state.get("last_pending_flush_at"),
        "last_practice_input": state.get("last_practice_input", ""),
    }


def _profile_payload(user: User) -> dict[str, object]:
    return {
        "display_name": user.display_name,
        "cefr_level": user.cefr_level,
        "industry": user.industry,
        "learning_goals": user.learning_goals,
        "preferred_study_time": user.preferred_study_time,
    }


async def _safe_enrich_profile_dict(
    user_id: str,
    profile: dict[str, object],
    *,
    query: str,
    trace_id: str,
) -> dict[str, object]:
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(enrich_profile_dict, user_id, profile, query=query),
            timeout=_PROFILE_ENRICHMENT_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        logger.warning(
            "profile_enrichment_timeout trace_id=%s user_id=%s timeout_seconds=%.2f",
            trace_id,
            user_id,
            _PROFILE_ENRICHMENT_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.exception("profile_enrichment_failed trace_id=%s user_id=%s", trace_id, user_id)

    degraded = dict(profile)
    degraded["memory_degraded"] = True
    return degraded


def _bootstrap_opening_state(message: str) -> dict[str, object]:
    timestamp = datetime.utcnow().isoformat()
    return {
        "hint_count": 0,
        "intent": "ENGLISH_RAG",
        "turns": [
            {
                "role": "assistant",
                "content": message,
                "timestamp": timestamp,
            }
        ],
        "last_response": message,
        "pending_facts": [],
        "pending_facts_since": None,
        "last_pending_flush_at": None,
        "last_practice_input": "",
    }


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _merge_facts(*fact_groups: list[dict] | tuple[dict, ...]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []
    for group in fact_groups:
        for fact in group:
            content = str(fact.get("content", "")).strip()
            metadata = fact.get("metadata") or {}
            fact_type = str(metadata.get("fact_type") or metadata.get("type") or "").strip().lower()
            key = (fact_type, content.lower())
            if not content or key in seen:
                continue
            seen.add(key)
            merged.append(fact)
    return merged


async def _flush_pending_facts(
    user_id: str,
    state: dict,
    *,
    db: Session | None = None,
    force: bool = False,
) -> int:
    if os.getenv("MEMORY_HOTPATH_ENABLED", "true").lower() != "true" and not force:
        state["pending_facts"] = []
        state["pending_facts_since"] = None
        return 0

    pending_facts = list(state.get("pending_facts", []))
    if not pending_facts:
        state.pop("pending_facts_since", None)
        return 0

    queued_at = _parse_iso_timestamp(state.get("pending_facts_since"))
    if not force:
        if queued_at is None:
            state["pending_facts_since"] = datetime.utcnow().isoformat()
            return 0
        if datetime.utcnow() - queued_at < timedelta(seconds=30):
            return 0

    if db is not None and os.getenv("MEMORY_WRITE_MODE", "queued").strip().lower() == "queued":
        flushed = enqueue_memory_facts(
            db,
            user_id=user_id,
            facts=pending_facts,
            source="chat",
            source_session=str(state.get("session_id") or ""),
            commit=True,
        )
        if settings.MEMORY_OPPORTUNISTIC_FLUSH_ENABLED:
            try:
                flush_memory_outbox(db)
            except Exception:
                logger.exception("chat: opportunistic memory outbox flush failed")
    else:
        memory = get_memory()
        flushed = 0
        for fact in pending_facts:
            content = str(fact.get("content", "")).strip()
            if not content:
                continue
            memory.add_memory(user_id, content, fact.get("metadata", {}))
            flushed += 1

    state["pending_facts"] = []
    state["pending_facts_since"] = None
    state["last_pending_flush_at"] = datetime.utcnow().isoformat()
    return flushed


def _persist_session_log(
    *,
    db: Session,
    user_id,
    intent: str,
    usage_bucket: dict,
    latency_ms: int,
    hint_count: int,
    message: str,
    reply: str,
    was_correct: bool | None = None,
) -> None:
    """Write a single SessionLog row summarising the chat call.

    Failures here must NOT break the user-facing response (so we wrap the
    commit in try/except). Token counts come from the contextvar bucket
    populated by the LLM clients; if a provider didn't return usage
    metadata we fall back to a length-based estimate so cost is still
    bounded above zero.
    """
    provider = usage_bucket.get("provider") or "mock"
    model = usage_bucket.get("model")
    tokens_in = int(usage_bucket.get("prompt_tokens", 0) or 0)
    tokens_out = int(usage_bucket.get("completion_tokens", 0) or 0)
    if tokens_in == 0 and tokens_out == 0 and provider != "mock":
        # Provider didn't return usage; fall back to character-based estimate.
        tokens_in = estimate_tokens(message)
        tokens_out = estimate_tokens(reply)

    cost = estimate_cost_usd(model, tokens_in, tokens_out)

    try:
        log_row = SessionLog(
            id=uuid.uuid4(),
            user_id=user_id,
            intent=intent,
            provider=provider,
            model=model,
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            cost_usd=round(cost, 6),
            latency_ms=latency_ms,
            was_correct=was_correct,
            hint_count=hint_count,
        )
        db.add(log_row)
        db.commit()
    except Exception:  # pragma: no cover - observability must never break chat
        logger.exception("Failed to persist SessionLog (non-fatal)")
        db.rollback()


async def _enforce_daily_rate_limit(user_id: str, sessions: SessionStore) -> None:
    key = f"ratelimit:{user_id}:{date.today().isoformat()}"
    used = await sessions.redis.incr(key)
    if used == 1:
        await sessions.redis.expire(key, 86400)
    if used > settings.RATE_LIMIT_PER_DAY:
        raise HTTPException(status_code=429, detail="Daily rate limit exceeded")


@router.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    request: Request,
    db: Session = Depends(get_db),
    sessions: SessionStore = Depends(get_session_store),
) -> ChatResponse:
    global _chat_inflight_gauge
    # Fail fast with 503 instead of letting clients sit on a 60 s read
    # timeout when the replica is saturated. See module-level comment.
    if _chat_semaphore.locked() and _chat_inflight_gauge >= _MAX_INFLIGHT_CHATS:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Chat backend at capacity ({_chat_inflight_gauge}/"
                f"{_MAX_INFLIGHT_CHATS} in-flight). Retry shortly."
            ),
            headers={"Retry-After": "5"},
        )
    async with _chat_semaphore:
        _chat_inflight_gauge += 1
        try:
            return await _chat_impl(payload, db, sessions, request=request)
        finally:
            _chat_inflight_gauge -= 1


async def _chat_impl(
    payload: ChatRequest,
    db: Session,
    sessions: SessionStore,
    request: Request | None = None,
) -> ChatResponse:
    request_started_at = time.perf_counter()
    if payload.user_id is None:
        raise HTTPException(status_code=400, detail="user_id is required")

    user = db.get(User, payload.user_id)
    if is_error_span_eval(payload):
        if user is None:
            raise HTTPException(status_code=404, detail="eval user not found")
        try:
            return await run_error_span_eval(payload, request=request)
        except LiveEvalProviderRequired as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    if user is None:
        # Soft-fail to keep mock dev flow simple
        intent = "ENGLISH_RAG"
        reply = _mock_reply(intent, payload.message)
        return ChatResponse(response=reply, hint_count=0, intent=intent, session_id=None)

    trace_id = str(getattr(getattr(request, "state", None), "trace_id", "") or uuid.uuid4())
    rate_limit_started_at = time.perf_counter()
    await _enforce_daily_rate_limit(str(payload.user_id), sessions)
    _log_chat_phase(trace_id, "rate_limit", rate_limit_started_at, user_id=str(payload.user_id))

    restore_started_at = time.perf_counter()
    state = await sessions.restore(str(payload.user_id)) or {"hint_count": 0, "turns": []}
    _log_chat_phase(trace_id, "session_restore", restore_started_at, user_id=str(payload.user_id), restored=bool(state.get("turns")))
    session_id = f"session:{payload.user_id}:latest"
    state["session_id"] = session_id

    profile_started_at = time.perf_counter()
    base_profile = _profile_payload(user)
    user_profile = await _safe_enrich_profile_dict(
        str(payload.user_id),
        base_profile,
        query=payload.message or "learner profile",
        trace_id=trace_id,
    )
    _log_chat_phase(
        trace_id,
        "profile_enrichment",
        profile_started_at,
        user_id=str(payload.user_id),
        degraded=bool(user_profile.get("memory_degraded")),
    )

    personal_error_started_at = time.perf_counter()
    try:
        personal_error_context = load_personal_error_context(
            db,
            user_id=payload.user_id,
            limit=5,
        )
    except Exception:
        logger.exception("Failed to load personal error context (non-fatal)")
        personal_error_context = []
    _log_chat_phase(
        trace_id,
        "personal_error_context",
        personal_error_started_at,
        user_id=str(payload.user_id),
        errors_loaded=len(personal_error_context),
    )

    # Start a fresh per-request usage accumulator. Every LLM call inside
    # `run_chat_pipeline` adds to it; we read the totals after the pipeline
    # to write a single SessionLog row (powers admin dashboard + analytics).
    usage_bucket = start_usage_tracking()
    pipeline_started_at = time.perf_counter()

    # Resolve current mood (request override → most recent mood_log within 24h)
    mood_state = payload.mood_state
    if mood_state is None:
        try:
            from datetime import timedelta as _td
            from sqlalchemy import select as _select
            from ...models.mood import MoodLog as _MoodLog
            recent = db.scalar(
                _select(_MoodLog)
                .where(_MoodLog.user_id == payload.user_id, _MoodLog.created_at >= datetime.utcnow() - _td(hours=24))
                .order_by(_MoodLog.created_at.desc())
            )
            mood_state = recent.mood if recent else None
        except Exception:
            mood_state = None

    graph_state = {
        "trace_id": trace_id,
        "user_id": str(payload.user_id),
        "user_input": payload.message,
        "command": payload.command,
        "type": payload.type,
        "intent": state.get("intent", "ENGLISH_RAG"),
        "memory": state.get("memory", []),
        "response": "",
        "hint_count": state.get("hint_count", 0),
        "new_facts": [],
        "turns": state.get("turns", []),
        "last_practice_input": state.get("last_practice_input", ""),
        "user_profile": user_profile,
        "memory_degraded": bool(user_profile.get("memory_degraded")),
        "personal_error_context": personal_error_context,
        "db": db,
        "mood_state": mood_state,
        "pasted_context": payload.pasted_context,
    }
    logger.info(
        "chat_turn_start trace_id=%s user_id=%s session_id=%s message=%r prior_intent=%s command=%s type=%s mood_state=%s",
        trace_id,
        payload.user_id,
        session_id,
        _truncate(payload.message),
        graph_state.get("intent"),
        payload.command,
        payload.type,
        mood_state,
    )

    try:
        result = await run_chat_pipeline(graph_state)
        _log_chat_phase(
            trace_id,
            "run_chat_pipeline",
            pipeline_started_at,
            user_id=str(payload.user_id),
            prior_intent=graph_state.get("intent"),
        )
        intent = result.get("intent", graph_state["intent"])
        reply = result.get("response") or _mock_reply(intent, payload.message)
        hint_count = result.get("hint_count", graph_state["hint_count"])
        pending_facts = result.get("new_facts", [])
        dna_delta = result.get("dna_delta") or {}
        recommended_review = result.get("recommended_review") or []
        cefr_step = int(result.get("cefr_step", 0) or 0)
        agent_message = result.get("agent_message")
        learning_state = result.get("learning_state")
        ui_directive = result.get("ui_directive")
        suggested_actions = result.get("suggested_actions") or []
        practice_assessment = result.get("practice_assessment") or {}
        profile_facts = extract_profile_facts(
            payload.message,
            intent=intent,
            learning_intent=result.get("learning_intent"),
            command=payload.command,
            message_type=payload.type,
        )
        pending_facts = _merge_facts(list(pending_facts), profile_facts)

    except Exception as e:  # pragma: no cover - defensive fallback
        print(f"ERROR in run_chat_pipeline: {e}", flush=True)
        logger.exception("Gemini chat pipeline failed, falling back to mock reply")
        # Explicitly report to Sentry with pipeline context — logger.exception
        # already forwards via LoggingIntegration, this adds richer extras.
        try:
            from ...core.llm_call_observability import capture_exception
            capture_exception(
                e,
                pipeline_stage="run_chat_pipeline",
                user_id=str(payload.user_id),
                intent_hint=graph_state.get("intent"),
                mood_state=graph_state.get("mood_state"),
                has_pasted_context=bool(payload.pasted_context),
            )
        except Exception:
            pass
        intent = "ENGLISH_RAG"
        reply = _mock_reply(intent, payload.message)
        hint_count = state.get("hint_count", 0)
        pending_facts = []
        dna_delta = {}
        recommended_review = []
        cefr_step = 0
        agent_message = None
        learning_state = None
        ui_directive = None
        suggested_actions = []
        practice_assessment = {}
        profile_facts = extract_profile_facts(
            payload.message,
            intent=intent,
            learning_intent="NONE",
            command=payload.command,
            message_type=payload.type,
        )
        pending_facts = _merge_facts(profile_facts)

    latency_ms = int((time.perf_counter() - pipeline_started_at) * 1000)
    if not usage_bucket.get("provider") and practice_assessment:
        usage_bucket["provider"] = "local_rule"
        usage_bucket["model"] = "rule-based-scaffolding"
    logger.info(
        "chat_turn_complete trace_id=%s user_id=%s session_id=%s intent=%s provider=%s model=%s llm_calls=%s latency_ms=%s hint_count=%s reply_chars=%s reply=%r ui_screen=%s learning_intent=%s",
        trace_id,
        payload.user_id,
        session_id,
        intent,
        usage_bucket.get("provider") or "mock",
        usage_bucket.get("model") or "",
        usage_bucket.get("calls", 0),
        latency_ms,
        hint_count,
        len(reply or ""),
        _truncate(reply),
        (ui_directive or {}).get("screen") if ui_directive else None,
        (result.get("learning_intent") if "result" in locals() and isinstance(result, dict) else None),
    )
    persist_log_started_at = time.perf_counter()
    was_correct = None
    if intent == "ENGLISH_RAG":
        practice_status = str(practice_assessment.get("status", "") or "").strip().lower()
        if practice_status == "correct":
            was_correct = True
        elif practice_status in {"needs_revision", "unclear", "unavailable"}:
            was_correct = False
    _persist_session_log(
        db=db,
        user_id=payload.user_id,
        intent=intent,
        usage_bucket=usage_bucket,
        latency_ms=latency_ms,
        hint_count=hint_count,
        message=payload.message,
        reply=reply,
        was_correct=was_correct,
    )
    _log_chat_phase(trace_id, "persist_session_log", persist_log_started_at, user_id=str(payload.user_id))

    if intent == "ENGLISH_RAG" and practice_assessment:
        capture_error_started_at = time.perf_counter()
        try:
            captured = capture_error_and_flashcard(
                db,
                user_id=payload.user_id,
                original_text=payload.message,
                payload=practice_assessment,
                source="chat",
                cefr_level=user.cefr_level,
                industry=user.industry,
                source_metadata={
                    "session_id": session_id,
                    "status": practice_assessment.get("status"),
                    "provider": usage_bucket.get("provider") or "mock",
                    "model": usage_bucket.get("model"),
                },
            )
            if captured.flashcard is not None:
                recommended_review = [
                    *recommended_review,
                    {
                        "card_kind": "error",
                        "flashcard_id": str(captured.flashcard.id),
                        "error_type": captured.flashcard.error_type,
                        "front": captured.flashcard.front,
                    },
                ]
        except Exception:
            logger.exception("Failed to persist personal error review artefacts (non-fatal)")
            db.rollback()
        _log_chat_phase(
            trace_id,
            "capture_error_and_flashcard",
            capture_error_started_at,
            user_id=str(payload.user_id),
            reviews=len(recommended_review),
        )

    timestamp = datetime.utcnow().isoformat()
    state["turns"] = state.get("turns", []) + [
        {"role": "user", "content": payload.message, "timestamp": timestamp},
        {"role": "assistant", "content": reply, "timestamp": timestamp},
    ]
    state["hint_count"] = hint_count
    state["intent"] = intent
    state["last_response"] = reply
    state["pending_facts"] = _merge_facts(list(state.get("pending_facts", [])), list(pending_facts))
    if state["pending_facts"] and not state.get("pending_facts_since"):
        state["pending_facts_since"] = timestamp
    if intent == "ENGLISH_RAG" and practice_assessment:
        state["last_practice_input"] = payload.message

    flush_started_at = time.perf_counter()
    flushed_facts = await _flush_pending_facts(str(payload.user_id), state, db=db)
    _log_chat_phase(
        trace_id,
        "flush_pending_facts",
        flush_started_at,
        user_id=str(payload.user_id),
        flushed=flushed_facts,
        pending_remaining=len(state.get("pending_facts", [])),
    )

    save_started_at = time.perf_counter()
    await sessions.save(str(payload.user_id), _serialize_state(state))
    _log_chat_phase(
        trace_id,
        "session_save",
        save_started_at,
        user_id=str(payload.user_id),
        turns=len(state.get("turns", [])),
    )

    total_duration_ms = round((time.perf_counter() - request_started_at) * 1000.0, 1)
    logger.info(
        "chat.request_timing trace_id=%s total_duration_ms=%.1f llm_calls=%s provider=%s mem_hits=%s pending_facts=%s",
        trace_id,
        total_duration_ms,
        usage_bucket.get("calls", 0),
        usage_bucket.get("provider") or "mock",
        len(graph_state.get("memory") or []),
        len(state.get("pending_facts", [])),
    )
    if total_duration_ms >= _SLOW_CHAT_REQUEST_MS:
        logger.warning(
            "chat.slow_request trace_id=%s total_duration_ms=%.1f intent=%s provider=%s model=%s llm_calls=%s hint_count=%s",
            trace_id,
            total_duration_ms,
            intent,
            usage_bucket.get("provider") or "mock",
            usage_bucket.get("model") or "",
            usage_bucket.get("calls", 0),
            hint_count,
        )

    return ChatResponse(
        response=reply,
        hint_count=hint_count,
        intent=intent,
        session_id=session_id,
        dna_delta=dna_delta or None,
        recommended_review=recommended_review or None,
        cefr_step=cefr_step,
        agent_message=agent_message,
        learning_state=learning_state,
        ui_directive=ui_directive,
        suggested_actions=suggested_actions or None,
    )


@router.get("/session/restore")
async def restore_session(
    user_id: str = Query(...),
    sessions: SessionStore = Depends(get_session_store),
    db: Session = Depends(get_db),
) -> dict:
    state = await sessions.restore(user_id)
    user = db.query(User).filter(User.user_id == user_id).first()
    opening_message = None
    if user is not None:
        opening_message = (user.agent_opening_message or "").strip()
        if needs_welcome_message_refresh(opening_message):
            profile = enrich_profile_dict(
                user_id,
                _profile_payload(user),
                query="learner profile welcome introduction goals",
            )
            opening_message = build_welcome_message(profile)
            user.agent_opening_message = opening_message
            db.commit()
            db.refresh(user)

    if state is None:
        if user is None:
            return {"user_id": user_id, "session": None, "initial_message": None}
        state = _bootstrap_opening_state(opening_message)
        await sessions.save(user_id, _serialize_state(state))
    elif (
        opening_message
        and len(state.get("turns", [])) == 1
        and state["turns"][0].get("role") == "assistant"
        and needs_welcome_message_refresh(state["turns"][0].get("content"))
    ):
        state = _bootstrap_opening_state(opening_message)
        await sessions.save(user_id, _serialize_state(state))

    turns = state.get("turns", [])
    messages = [
        {
            "role": turn.get("role", "assistant"),
            "content": turn.get("content", ""),
            "timestamp": turn.get("timestamp"),
        }
        for turn in turns
    ]
    return {
        "user_id": user_id,
        "session": {
            "messages": messages,
            "hint_count": state.get("hint_count", 0),
            "intent": state.get("intent", "ENGLISH_RAG"),
            "last_response": state.get("last_response", ""),
            "pending_facts": state.get("pending_facts", []),
        },
        "initial_message": state.get("last_response") if len(messages) == 1 and messages[0].get("role") == "assistant" else None,
    }


@router.delete("/session/{user_id}")
async def delete_session(
    user_id: str,
    sessions: SessionStore = Depends(get_session_store),
) -> dict[str, str]:
    state = await sessions.restore(user_id) or {}
    await _flush_pending_facts(user_id, state, force=True)
    await sessions.delete(user_id)
    return {"status": "deleted", "user_id": user_id}


@router.get("/debug/config")
async def debug_config() -> dict:
    """Debug endpoint to verify configuration and LLM client setup."""
    from ...core.config import get_settings
    from ...utils.llm import GeminiLLMClient, GroqLLMClient
    
    settings = get_settings()
    gemini_client = GeminiLLMClient()
    groq_client = GroqLLMClient()
    
    return {
        "GEMINI_API_KEY_SET": bool(settings.GEMINI_API_KEY),
        "GEMINI_API_KEY_LENGTH": len(settings.GEMINI_API_KEY) if settings.GEMINI_API_KEY else 0,
        "GROQ_API_KEY_SET": bool(settings.GROQ_API_KEY),
        "GROQ_API_KEY_LENGTH": len(settings.GROQ_API_KEY) if settings.GROQ_API_KEY else 0,
        "GEMINI_CLIENT_ENABLED": gemini_client.enabled,
        "GROQ_CLIENT_ENABLED": groq_client.enabled,
        "LLM_MODEL": settings.LLM_MODEL,
    }
