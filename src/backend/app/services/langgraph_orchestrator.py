from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
from datetime import datetime, timedelta
from typing import Any, Literal, TypedDict

from langgraph.graph import END, StateGraph

from ..core.config import get_settings
from ..core.mem0_client import get_memory
from ..utils.llm import get_llm_client  # kept for existing tests/extensions that monkeypatch this module
from .guardrails import input_guard, output_guard
from .scaffolding_engine import scaffolding_engine
from .system_prompt import build_messages_with_persona

logger = logging.getLogger(__name__)
_LANGGRAPH_TRACE_ENABLED = os.getenv("LANGGRAPH_TRACE_ENABLED", "true").strip().lower() == "true"
_SLOW_LANGGRAPH_NODE_MS = int(os.getenv("SLOW_LANGGRAPH_NODE_MS", "750"))


class ChatState(TypedDict, total=False):
    trace_id: str
    user_id: str
    user_input: str
    command: str
    type: str
    intent: Literal["ENGLISH_RAG", "CONTEXT_INJECT", "MORNING_BRIEF"]
    memory: list[dict[str, Any]]
    response: str
    hint_count: int
    new_facts: list[dict[str, Any]]
    turns: list[dict[str, Any]]
    last_practice_input: str
    user_profile: dict[str, Any]
    personal_error_context: list[dict[str, Any]]
    db: Any
    # 6-node target additions
    mood_state: str | None
    mood_config: dict[str, Any]
    pasted_context: str | None
    extracted_terms: list[str]
    cefr_step: int  # +1 = bump up, -1 = bump down, 0 = hold
    dna_delta: dict[str, int]
    recommended_review: list[dict[str, Any]]
    learning_intent: Literal[
        "NONE",
        "START_LEARNING",
        "READ_LESSON",
        "LESSON_PRACTICE",
        "LESSON_FLASHCARD",
        "NEXT_LESSON",
        "LESSON_STATUS",
    ]
    learning_state: dict[str, Any]
    active_lesson: dict[str, Any] | None
    agent_message: str
    ui_directive: dict[str, Any] | None
    suggested_actions: list[dict[str, str]]
    learning_action_result: dict[str, Any]
    learning_error: str
    memory_degraded: bool
    practice_assessment: dict[str, Any]
    # Guardrail signalling (set by input_guard / output_guard nodes)
    guardrail_blocked: bool
    guardrail_reason: str
    guardrail_output_action: str


def _truncate(value: Any, limit: int = 160) -> str:
    text = str(value or "").replace("\n", "\\n")
    if len(text) <= limit:
        return text
    return f"{text[:limit]}..."


def _state_snapshot(state: ChatState) -> dict[str, Any]:
    learning_state = state.get("learning_state") or {}
    ui_directive = state.get("ui_directive") or {}
    return {
        "trace_id": state.get("trace_id"),
        "user_id": state.get("user_id"),
        "user_input": _truncate(state.get("user_input", "")),
        "intent": state.get("intent"),
        "learning_intent": state.get("learning_intent"),
        "current_step": learning_state.get("current_step"),
        "ui_screen": ui_directive.get("screen"),
        "response": _truncate(state.get("response", "")),
        "hint_count": state.get("hint_count", 0),
        "memory_count": len(state.get("memory") or []),
        "new_facts_count": len(state.get("new_facts") or []),
        "pending_facts_count": len(state.get("pending_facts") or []),
        "suggested_actions_count": len(state.get("suggested_actions") or []),
        "recommended_review_count": len(state.get("recommended_review") or []),
        "extracted_terms_count": len(state.get("extracted_terms") or []),
        "guardrail_blocked": bool(state.get("guardrail_blocked")),
        "guardrail_reason": state.get("guardrail_reason"),
        "learning_error": _truncate(state.get("learning_error", ""), 120),
    }


def _log_graph_event(event: str, **payload: Any) -> None:
    if not _LANGGRAPH_TRACE_ENABLED:
        return
    logger.info("langgraph.%s %s", event, json.dumps(payload, ensure_ascii=False, default=str, sort_keys=True))


def _wrap_node(name: str, fn):
    async def _wrapped(state: ChatState) -> ChatState:
        before = _state_snapshot(state)
        _log_graph_event("node.start", node=name, state=before)
        started_at = time.perf_counter()
        try:
            result = await fn(state)
        except Exception as exc:
            duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
            _log_graph_event("node.error", node=name, state=before, error=repr(exc), duration_ms=duration_ms)
            raise

        after = _state_snapshot(result)
        changed = {
            key: after[key]
            for key in after
            if before.get(key) != after.get(key)
        }
        duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
        _log_graph_event("node.end", node=name, changed=changed, state=after, duration_ms=duration_ms)
        if duration_ms >= _SLOW_LANGGRAPH_NODE_MS:
            logger.warning(
                "langgraph.slow_node trace_id=%s node=%s duration_ms=%.1f intent=%s learning_intent=%s",
                state.get("trace_id"),
                name,
                duration_ms,
                after.get("intent"),
                after.get("learning_intent"),
            )
        return result

    return _wrapped


def _fallback_intent(text: str) -> str:
    _ = text
    return "ENGLISH_RAG"


async def intent_router(state: ChatState) -> ChatState:
    state["intent"] = "ENGLISH_RAG"  # type: ignore[assignment]
    logger.info("intent_router: Pass-through ENGLISH_RAG")
    return state
    
def _normalize_learning_text(text: str) -> str:
    normalized = text.lower().strip().replace("đ", "d")
    decomposed = unicodedata.normalize("NFD", normalized)
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


_START_LEARNING_PHRASES = (
    "let's start learning",
    "lets start learning",
    "start learning",
    "start lesson",
    "open the first lesson",
    "open first lesson",
    "open first lecture",
    "first lesson",
    "hoc bai",
    "hoc bai moi",
    "bat dau hoc",
    "mo bai giang dau tien",
    "mở bài giảng đầu tiên",
    "mo bai hoc dau tien",
    "mở bài học đầu tiên",
)

_LESSON_STATUS_PHRASES = (
    "where am i",
    "current lesson",
    "lesson status",
    "learning status",
    "learning progress in this lesson",
    "tien do bai",
    "dang hoc bai nao",
)

_FLASHCARD_PHRASES = (
    "flashcard",
    "flash card",
    "flashcards",
    "open flashcard",
    "open flashcards",
    "mo flashcard",
    "mở flashcard",
    "mở flashcards",
    "review vocab",
    "review vocabulary",
    "on tu vung",
    "ôn tu vung",
)

_NEXT_LESSON_PHRASES = (
    "next lesson",
    "new lesson",
    "open new lesson",
    "open next lecture",
    "open next lesson",
    "bai tiep theo",
    "bai giang moi",
    "bai moi",
    "continue to next lesson",
    "mo bai giang moi",
    "mở bài giảng mới",
    "mo bai tiep theo",
    "mở bài tiếp theo",
    "chuyen toi bai moi",
    "chuyển tới bài mới",
)

_READ_LESSON_PHRASES = (
    "show me the lesson",
    "read lesson",
    "open lesson",
    "open the lesson",
    "show lesson",
    "open lecture",
    "read this lesson",
    "doc bai",
    "mo bai hoc",
    "bai giang",
    "mo bai giang",
    "mở bài giảng",
    "xem bai giang",
    "xem bài giảng",
)

_LESSON_PRACTICE_PHRASES = (
    "open review",
    "open review tab",
    "review this lesson",
    "review tab",
    "give me exercises",
    "give me exercise",
    "lesson exercises",
    "lesson exercise",
    "bai tap bai",
    "lam bai tap",
    "on tap",
    "ôn tập",
    "on bai",
    "ôn bài",
    "che do on tap",
    "chế độ ôn tập",
    "vao che do on tap",
    "vào chế độ ôn tập",
    "mo che do on tap",
    "mở chế độ ôn tập",
    "mo on tap",
    "mở ôn tập",
    "mo tab on tap",
    "mở tab ôn tập",
)

_ACTIVE_LESSON_PRACTICE_PHRASES = (
    "on tap",
    "ôn tập",
    "on bai",
    "ôn bài",
    "review",
    "review tab",
)

_LEARNING_CONTEXT_PHRASES = (
    "bai hoc",
    "bài học",
    "bai nay",
    "bài này",
    "lesson",
    "hoc bai",
    "học bài",
    "bai giang",
    "bài giảng",
)

def _learning_screen_for_step(step: str) -> str:
    return {
        "LESSON_READING": "LESSON_READER",
        "PRACTICE": "PRACTICE_RUNNER",
        "FLASHCARD": "FLASHCARD_RUNNER",
        "LESSON_COMPLETE": "LESSON_COMPLETE",
    }.get(step, "CHAT")


def _explicit_skip_requested(text: str) -> bool:
    return _contains_any(
        text,
        (
            "skip",
            "skip this lesson",
            "skip lesson",
            "bo qua",
            "bo qua bai",
            "chuyen bai",
            "bai tiep theo luon",
        ),
    )


async def learning_intent_router(state: ChatState) -> ChatState:
    """Classify lesson-flow requests without changing the existing chat intent."""
    text = _normalize_learning_text(state.get("user_input", ""))
    user_id = state.get("user_id") or "mock-user"
    active_state = None
    try:
        from ..api.v1 import learning as learning_api

        active_state = await learning_api.learning_store.get_state(user_id)
    except Exception:  # pragma: no cover - learning flow must not break chat
        logger.exception("learning_intent_router failed to read learning state")

    has_active_lesson = bool(active_state and active_state.active_lesson_id)
    learning_intent = "NONE"

    if _contains_any(text, _START_LEARNING_PHRASES):
        learning_intent = "START_LEARNING"
    elif _contains_any(text, _LESSON_STATUS_PHRASES):
        learning_intent = "LESSON_STATUS"
    elif _contains_any(text, _FLASHCARD_PHRASES):
        learning_intent = "LESSON_FLASHCARD"
    elif _contains_any(text, _NEXT_LESSON_PHRASES) or (
        has_active_lesson and text in {"continue", "next"}
    ):
        learning_intent = "NEXT_LESSON"
    elif _contains_any(text, _READ_LESSON_PHRASES):
        learning_intent = "READ_LESSON"
    elif _contains_any(text, _LESSON_PRACTICE_PHRASES):
        learning_intent = "LESSON_PRACTICE"
    elif has_active_lesson and _contains_any(text, _ACTIVE_LESSON_PRACTICE_PHRASES):
        learning_intent = "LESSON_PRACTICE"

    state["learning_intent"] = learning_intent  # type: ignore[assignment]
    return state


async def learning_state_loader(state: ChatState) -> ChatState:
    if state.get("learning_intent") == "NONE":
        state["ui_directive"] = None
        state["suggested_actions"] = []
        return state

    user_id = state.get("user_id") or "mock-user"
    try:
        from ..api.v1 import learning as learning_api

        learning_state = await learning_api.learning_store.get_state(user_id)
        if learning_state is not None:
            state["learning_state"] = learning_state.model_dump(mode="json")
            state["active_lesson"] = learning_api._active_lesson_payload(learning_state)
        else:
            state["learning_state"] = {"current_step": "NONE"}
            state["active_lesson"] = None
    except Exception:  # pragma: no cover - learning flow must not break chat
        logger.exception("learning_state_loader failed")
        state["learning_intent"] = "NONE"  # type: ignore[assignment]
        state["ui_directive"] = None
        state["suggested_actions"] = []
    return state


async def _start_or_resume_learning(user_id: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    return await learning_api.start_learning(learning_api.LearningStartRequest(user_id=user_id))


async def _open_active_or_start_lesson(user_id: str, reason: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    learning_state = await learning_api.learning_store.get_state(user_id)
    if not learning_state or not learning_state.active_lesson_id:
        return await _start_or_resume_learning(user_id)

    lesson = learning_api._active_lesson_payload(learning_state)
    if learning_state.current_step != "LESSON_READING":
        active_lesson = learning_api._require_lesson(learning_state.active_lesson_id)
        learning_state = learning_api._state_for_lesson(learning_state, active_lesson, "LESSON_READING", reason)
        await learning_api.learning_store.save_state(user_id, learning_state)
        lesson = active_lesson.model_dump(mode="json")

    return learning_api._learning_response(
        agent_message="Bạn đang đọc bài học này. Khi sẵn sàng, mình có thể mở tab Ôn tập cho bài này.",
        state=learning_state,
        lesson=lesson,
        ui_directive=learning_api.UIDirective(
            screen="LESSON_READER",
            action="OPEN",
            lesson_id=learning_state.active_lesson_id,
            reason=reason,
        ),
        suggested_actions=learning_api._reading_actions(),
    )


async def _practice_active_lesson(user_id: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    learning_state = await learning_api.learning_store.get_state(user_id)
    if not learning_state or not learning_state.active_lesson_id:
        await _start_or_resume_learning(user_id)
        learning_state = await learning_api.learning_store.get_state(user_id)
    if not learning_state or not learning_state.active_lesson_id:
        raise RuntimeError("No active lesson available for practice")
    return await learning_api.lesson_questions(
        learning_state.active_lesson_id,
        payload=learning_api.LearningUserRequest(user_id=user_id),
        user_id=None,
    )


async def _flashcards_for_active_lesson(user_id: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    learning_state = await learning_api.learning_store.get_state(user_id)
    if not learning_state or not learning_state.active_lesson_id:
        await _start_or_resume_learning(user_id)
        learning_state = await learning_api.learning_store.get_state(user_id)
    if not learning_state or not learning_state.active_lesson_id:
        raise RuntimeError("No active lesson available for flashcards")
    return await learning_api.lesson_flashcards(learning_state.active_lesson_id, user_id=user_id)


async def _current_learning_status(user_id: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    return await learning_api.current_learning_state(user_id=user_id)


async def _friendly_next_lesson_block_message(
    *,
    user_text: str,
    lesson_title: str | None,
    current_step: str,
) -> str:
    fallback = "Bài hiện tại chưa hoàn thành. Nếu muốn chuyển bài, hãy nói rõ là bạn muốn bỏ qua bài này."
    llm = get_llm_client()
    if not getattr(llm, "enabled", False):
        return fallback

    lesson_label = (lesson_title or "bài hiện tại").strip()
    prompt = (
        "Write one short, friendly Vietnamese reply for an English-learning app.\n"
        "Situation:\n"
        f"- Learner asked: {user_text or '(empty)'}\n"
        f"- Current lesson: {lesson_label}\n"
        f"- Current step: {current_step}\n"
        "- The learner cannot move to the next lesson yet because the current lesson is unfinished.\n"
        "- Ask them to continue the current lesson, or explicitly say 'bỏ qua bài này' if they really want to skip.\n"
        "- Keep it natural, warm, and concise.\n"
        "- Do not mention policy, system, UI directive, or technical details.\n"
        "- Return only the final learner-facing message."
    )
    try:
        return (
            await llm.generate_chat_completion(
                build_messages_with_persona(prompt),
                temperature=0.4,
                max_tokens=90,
            )
        ).strip() or fallback
    except Exception:
        logger.exception("friendly_next_lesson_block_message failed")
        return fallback


async def _next_lesson(user_id: str, user_text: str) -> dict[str, Any]:
    from ..api.v1 import learning as learning_api

    learner = learning_api.get_learner_profile(user_id)
    learning_state = await learning_api.learning_store.get_state(user_id)
    normalized_text = _normalize_learning_text(user_text)
    if not learning_state or not learning_state.active_lesson_id:
        return await _start_or_resume_learning(user_id)

    if learning_state.current_step != "LESSON_COMPLETE" and not _explicit_skip_requested(normalized_text):
        lesson_payload = learning_api._active_lesson_payload(learning_state)
        return learning_api._learning_response(
            agent_message=await _friendly_next_lesson_block_message(
                user_text=user_text,
                lesson_title=(lesson_payload or {}).get("title"),
                current_step=learning_state.current_step,
            ),
            state=learning_state,
            lesson=lesson_payload,
            ui_directive=learning_api.UIDirective(
                screen=_learning_screen_for_step(learning_state.current_step),
                action="OPEN",
                lesson_id=learning_state.active_lesson_id,
                practice_set_id=learning_state.practice_set_id,
                reason="next_lesson_blocked",
            ),
            suggested_actions=learning_api._suggested_actions_for_step(learning_state.current_step),
        )

    if _explicit_skip_requested(normalized_text) and learning_state.active_lesson_id not in learning_state.completed_lessons:
        learning_state.completed_lessons.append(learning_state.active_lesson_id)
        await learning_api.learning_store.save_state(user_id, learning_state)

    next_lesson_id = learning_api._first_incomplete_lesson_id(learner, learning_state)
    return await learning_api.start_learning(
        learning_api.LearningStartRequest(user_id=user_id, lesson_id=next_lesson_id)
    )


async def learning_action_router(state: ChatState) -> ChatState:
    learning_intent = state.get("learning_intent", "NONE")
    if learning_intent == "NONE":
        return state

    user_id = state.get("user_id") or "mock-user"
    user_text = state.get("user_input", "")
    try:
        if learning_intent == "START_LEARNING":
            payload = await _start_or_resume_learning(user_id)
        elif learning_intent == "READ_LESSON":
            payload = await _open_active_or_start_lesson(user_id, "read_lesson")
        elif learning_intent == "LESSON_PRACTICE":
            payload = await _practice_active_lesson(user_id)
        elif learning_intent == "LESSON_FLASHCARD":
            payload = await _flashcards_for_active_lesson(user_id)
        elif learning_intent == "NEXT_LESSON":
            payload = await _next_lesson(user_id, user_text)
        elif learning_intent == "LESSON_STATUS":
            payload = await _current_learning_status(user_id)
        else:
            payload = {}
        state["learning_action_result"] = payload
    except Exception as exc:  # pragma: no cover - defensive fallback
        logger.exception("learning_action_router failed")
        state["learning_intent"] = "NONE"  # type: ignore[assignment]
        state["ui_directive"] = None
        state["suggested_actions"] = []
        state["response"] = ""
        state["learning_error"] = str(exc)
    return state


async def learning_response_composer(state: ChatState) -> ChatState:
    if state.get("learning_intent") == "NONE":
        state["ui_directive"] = None
        state.setdefault("suggested_actions", [])
        return state

    payload = state.get("learning_action_result") or {}
    agent_message = str(payload.get("agent_message") or "Mình đã cập nhật luồng học cho bài hiện tại.")
    learning_state = payload.get("learning_state") or payload.get("state") or state.get("learning_state") or {}

    state["agent_message"] = agent_message
    state["response"] = agent_message
    state["learning_state"] = learning_state
    state["active_lesson"] = payload.get("lesson") or state.get("active_lesson")
    state["ui_directive"] = payload.get("ui_directive")
    state["suggested_actions"] = payload.get("suggested_actions") or []
    state["hint_count"] = 0
    state["new_facts"] = []
    return state


async def memory_retrieval(state: ChatState) -> ChatState:
    if state.get("guardrail_blocked"):
        state["memory"] = []
        return state
    if os.getenv("MEMORY_HOTPATH_ENABLED", "true").lower() != "true":
        state["memory"] = []
        return state
    if state.get("memory_degraded"):
        state["memory"] = []
        logger.warning(
            "memory_retrieval skipped because profile memory is degraded trace_id=%s user_id=%s",
            state.get("trace_id"),
            state.get("user_id"),
        )
        return state

    limit = 10 if state.get("intent") == "ENGLISH_RAG" else 0
    if not limit:
        state["memory"] = []
        return state

    memory = get_memory()
    state["memory"] = memory.search_memory(state["user_id"], state["user_input"], limit=limit) if limit else []

    # Optional corpus (vocab / error / prompt / ielts) retrieval. Feature-
    # flagged off by default so nothing changes until ops has run the
    # ``ingest_corpus_to_qdrant`` seeder and set
    # ``CORPUS_RETRIEVAL_ENABLED=true``. Kept inside a best-effort block
    # because semantic retrieval must never break the chat turn — if the
    # corpus collection is missing or the embedder key is bad, the chat
    # keeps running with Mem0 + SQL fallbacks.
    try:
        from . import corpus_retrieval as _cr
        if _cr.is_enabled() and limit:
            kinds = ("vocab", "prompt", "error", "ielts")
            corpus_hits = _cr.search_many(
                query=state["user_input"],
                kinds=kinds,
                top_k_per_kind=3,
            )
            # Attach flat + grouped forms; downstream prompt builder
            # picks whichever is cheaper to format.
            state["corpus_hits"] = corpus_hits
            state["corpus_flat"] = [
                h for arr in corpus_hits.values() for h in arr
            ]
    except Exception:  # noqa: BLE001 — retrieval must never break chat
        logger.exception("corpus retrieval failed (non-fatal)")

    return state


async def scaffolding_node(state: ChatState) -> ChatState:
    return await scaffolding_engine(state)


async def memory_writer(state: ChatState) -> ChatState:
    # Pending facts are flushed on a debounce schedule by the chat endpoint.
    # The graph only needs to carry extracted facts forward.
    state.setdefault("pending_facts", [])
    state["pending_facts"].extend(state.get("new_facts", []))
    return state


# --------------------------------------------------------------------------
# Target-architecture additions: mood_adapter / context_analyzer /
# difficulty_tuner. Each is a pure function that mutates ChatState; they
# wrap or extend the existing 4-node graph rather than replacing it.
# --------------------------------------------------------------------------


def _derive_mood_config(mood: str | None) -> dict[str, Any]:
    table = {
        "sleepy":  {"length": "short",  "difficulty": "easy",   "modality": "vocab",    "tone": "gentle"},
        "neutral": {"length": "medium", "difficulty": "normal", "modality": "balanced", "tone": "neutral"},
        "ok":      {"length": "medium", "difficulty": "normal", "modality": "balanced", "tone": "warm"},
        "happy":   {"length": "long",   "difficulty": "stretch","modality": "speaking", "tone": "energetic"},
        "fire":    {"length": "long",   "difficulty": "hard",   "modality": "writing",  "tone": "challenge"},
    }
    return table.get((mood or "").lower(), table["neutral"])


async def mood_adapter(state: ChatState) -> ChatState:
    """Pre-graph node: resolve session config from `mood_state`.

    The cfg is added to `user_profile` so downstream nodes (scaffolding,
    intent classification) can read tone/length/difficulty without caring
    about mood semantics.
    """
    mood = state.get("mood_state")
    cfg = _derive_mood_config(mood)
    previous_mood = (state.get("user_profile") or {}).get("mood")
    state["mood_config"] = cfg
    profile = dict(state.get("user_profile") or {})
    profile["mood"] = mood
    profile["mood_config"] = cfg
    state["user_profile"] = profile
    if mood and mood != previous_mood:
        facts = list(state.get("new_facts") or [])
        facts.append(
            {
                "content": f"Current session mood is {mood}; adapt with {cfg.get('tone')} tone, {cfg.get('difficulty')} difficulty, {cfg.get('length')} length, and {cfg.get('modality')} modality.",
                "metadata": {
                    "type": "mood_pattern",
                    "mood": mood,
                    "tone": cfg.get("tone"),
                    "difficulty": cfg.get("difficulty"),
                    "length": cfg.get("length"),
                    "modality": cfg.get("modality"),
                },
            }
        )
        state["new_facts"] = facts
    logger.debug("mood_adapter mood=%s cfg=%s", mood, cfg)
    return state


async def context_analyzer(state: ChatState) -> ChatState:
    """If the request carries `pasted_context`, classify it as
    CONTEXT_INJECT and harvest candidate terms (heuristic only — the
    detailed mini-lesson lives in the /context/analyze endpoint).
    """
    pasted = (state.get("pasted_context") or "").strip()
    if not pasted:
        return state

    import re
    tokens = re.findall(r"[A-Za-z][A-Za-z\-']{4,}", pasted)
    seen, terms = set(), []
    for t in tokens:
        low = t.lower()
        if low in seen:
            continue
        seen.add(low)
        terms.append(t)
        if len(terms) >= 8:
            break
    state["extracted_terms"] = terms

    # Inject the paste into memory so scaffolding can reference industry vocab.
    memory_items = list(state.get("memory") or [])
    memory_items.append({"content": f"[pasted context] {pasted[:1000]}", "metadata": {"type": "context_artifact"}})
    state["memory"] = memory_items
    logger.info("context_analyzer extracted %s terms", len(terms))
    return state


async def difficulty_tuner(state: ChatState) -> ChatState:
    """Post-scaffolding node: adjust learner difficulty.

    Reads the last 3 SessionLog rows for this user (if `db` is wired) and
    decides whether to bump CEFR up/down. The decision is *not* persisted
    here — it's surfaced as `cefr_step` so the caller (chat router) can
    decide whether to update `user_profile.cefr_level`.
    """
    db = state.get("db")
    user_id = state.get("user_id")
    settings = get_settings()
    state.setdefault("cefr_step", 0)
    state.setdefault("dna_delta", {})
    state.setdefault("recommended_review", [])

    if db is None or not user_id:
        return state

    try:
        from sqlalchemy import select
        from ..models.session_log import SessionLog

        rows = db.execute(
            select(SessionLog.was_correct)
            .where(
                SessionLog.user_id == user_id,
                (SessionLog.intent == "PRACTICE")
                | ((SessionLog.intent == "ENGLISH_RAG") & (SessionLog.was_correct.is_not(None))),
            )
            .order_by(SessionLog.created_at.desc())
            .limit(settings.DIFFICULTY_MIN_SESSIONS)
        ).all()
        observed = [r[0] for r in rows if r[0] is not None]
        if len(observed) >= settings.DIFFICULTY_MIN_SESSIONS:
            accuracy = sum(1 for v in observed if v) / len(observed)
            if accuracy >= settings.DIFFICULTY_UP_THRESHOLD:
                state["cefr_step"] = 1
            elif accuracy <= settings.DIFFICULTY_DOWN_THRESHOLD:
                state["cefr_step"] = -1

        # Naive DNA delta: if scaffolding flagged an error, count a grammar hit.
        if state.get("hint_count", 0) > 0:
            state["dna_delta"] = {"grammar": 1}

        # Recommend top-3 due review words (lightweight; full SM-2 lives in /review)
        from ..models.vocabulary import UserVocabulary, Vocabulary
        from datetime import date as _date

        review_rows = db.execute(
            select(Vocabulary.word_id, Vocabulary.word)
            .join(UserVocabulary, UserVocabulary.word_id == Vocabulary.word_id)
            .where(UserVocabulary.user_id == user_id, UserVocabulary.next_review <= _date.today())
            .limit(3)
        ).all()
        state["recommended_review"] = [{"word_id": int(r[0]), "word": r[1]} for r in review_rows]
    except Exception:  # pragma: no cover - defensive
        logger.exception("difficulty_tuner failed")
    return state


def _route_after_input_guard(state: ChatState) -> str:
    """If the input guard tripped, skip every LLM/Mem0 node and jump
    straight to ``output_guard`` — the safe canned reply is already in
    ``state["response"]`` so we just need to honour the output sweep
    (which is a no-op on the canned message)."""
    route = "blocked" if state.get("guardrail_blocked") else "ok"
    _log_graph_event(
        "route",
        router="after_input_guard",
        decision=route,
        trace_id=state.get("trace_id"),
        intent=state.get("intent"),
        guardrail_blocked=bool(state.get("guardrail_blocked")),
    )
    return route


def _route_after_learning_response(state: ChatState) -> str:
    route = "learning" if state.get("learning_intent") != "NONE" else "chat"
    _log_graph_event(
        "route",
        router="after_learning_response",
        decision=route,
        trace_id=state.get("trace_id"),
        intent=state.get("intent"),
        learning_intent=state.get("learning_intent"),
        ui_screen=(state.get("ui_directive") or {}).get("screen"),
    )
    return route


workflow = StateGraph(ChatState)
workflow.add_node("mood_adapter", _wrap_node("mood_adapter", mood_adapter))
workflow.add_node("input_guard", _wrap_node("input_guard", input_guard))
workflow.add_node("intent_router", _wrap_node("intent_router", intent_router))
workflow.add_node("learning_intent_router", _wrap_node("learning_intent_router", learning_intent_router))
workflow.add_node("learning_state_loader", _wrap_node("learning_state_loader", learning_state_loader))
workflow.add_node("learning_action_router", _wrap_node("learning_action_router", learning_action_router))
workflow.add_node("learning_response_composer", _wrap_node("learning_response_composer", learning_response_composer))
workflow.add_node("memory_retrieval", _wrap_node("memory_retrieval", memory_retrieval))
workflow.add_node("context_analyzer", _wrap_node("context_analyzer", context_analyzer))
workflow.add_node("scaffolding", _wrap_node("scaffolding", scaffolding_node))
workflow.add_node("difficulty_tuner", _wrap_node("difficulty_tuner", difficulty_tuner))
workflow.add_node("memory_writer", _wrap_node("memory_writer", memory_writer))
workflow.add_node("output_guard", _wrap_node("output_guard", output_guard))

workflow.set_entry_point("mood_adapter")
workflow.add_edge("mood_adapter", "input_guard")
workflow.add_conditional_edges(
    "input_guard",
    _route_after_input_guard,
    {"ok": "intent_router", "blocked": "output_guard"},
)
workflow.add_edge("intent_router", "learning_intent_router")
workflow.add_edge("learning_intent_router", "learning_state_loader")
workflow.add_edge("learning_state_loader", "learning_action_router")
workflow.add_edge("learning_action_router", "learning_response_composer")
workflow.add_conditional_edges(
    "learning_response_composer",
    _route_after_learning_response,
    {"chat": "memory_retrieval", "learning": "memory_writer"},
)
workflow.add_edge("memory_retrieval", "context_analyzer")
workflow.add_edge("context_analyzer", "scaffolding")
workflow.add_edge("scaffolding", "difficulty_tuner")
workflow.add_edge("difficulty_tuner", "memory_writer")
workflow.add_edge("memory_writer", "output_guard")
workflow.add_edge("output_guard", END)

graph = workflow.compile()


async def run_chat_pipeline(state: ChatState) -> ChatState:
    started_at = time.perf_counter()
    _log_graph_event("pipeline.start", state=_state_snapshot(state))
    result = await graph.ainvoke(state)
    duration_ms = round((time.perf_counter() - started_at) * 1000.0, 1)
    _log_graph_event("pipeline.end", state=_state_snapshot(result), duration_ms=duration_ms)
    if duration_ms >= _SLOW_LANGGRAPH_NODE_MS:
        logger.warning(
            "langgraph.slow_pipeline trace_id=%s duration_ms=%.1f intent=%s learning_intent=%s",
            state.get("trace_id"),
            duration_ms,
            result.get("intent"),
            result.get("learning_intent"),
        )
    return result
