from __future__ import annotations

import json
import logging
import re
from typing import Any

from ..utils.llm import get_llm_client
from .system_prompt import build_messages_with_persona

logger = logging.getLogger(__name__)


def _mood_config(state: dict[str, Any]) -> dict[str, Any]:
    profile = state.get("user_profile") or {}
    cfg = state.get("mood_config") or profile.get("mood_config") or {}
    return cfg if isinstance(cfg, dict) else {}


def _mood_instruction(cfg: dict[str, Any]) -> str:
    tone = str(cfg.get("tone") or "neutral")
    length = str(cfg.get("length") or "medium")
    difficulty = str(cfg.get("difficulty") or "normal")
    modality = str(cfg.get("modality") or "balanced")
    parts = [
        f"Session mood adaptation: tone={tone}, length={length}, difficulty={difficulty}, modality={modality}.",
    ]
    if length == "short":
        parts.append("Keep the Vietnamese response very brief, ideally 1-3 short sentences.")
    elif length == "long":
        parts.append("You may include a slightly richer explanation or a short follow-up challenge.")
    if difficulty == "easy":
        parts.append("Reduce cognitive load: prefer review, simple wording, and no new advanced concepts unless necessary.")
    elif difficulty in {"hard", "stretch"}:
        parts.append("Increase challenge appropriately: ask for a stronger rewrite or more precise expression when useful.")
    if modality == "vocab":
        parts.append("Prefer vocabulary review or recognition-style practice over introducing brand-new material.")
    elif modality == "writing":
        parts.append("Prefer productive writing practice and invite the learner to rewrite the sentence.")
    elif modality == "speaking":
        parts.append("Prefer text-based conversational role-play prompts; do not imply voice recording or pronunciation assessment.")
    if tone == "gentle":
        parts.append("Use a gentle, low-pressure tone.")
    elif tone in {"energetic", "challenge"}:
        parts.append("Use an encouraging, high-energy tone without being harsh.")
    elif tone == "warm":
        parts.append("Use a warm and supportive tone.")
    return " ".join(parts)


def _max_tokens_for_mood(cfg: dict[str, Any], default: int) -> int:
    length = str(cfg.get("length") or "medium")
    if length == "short":
        return min(default, 220)
    if length == "long":
        return max(default, 460)
    return default


def _format_list(values: Any) -> str:
    if not values:
        return ""
    if isinstance(values, str):
        return values.strip()
    if isinstance(values, (list, tuple, set)):
        return ", ".join(str(item).strip() for item in values if str(item).strip())
    return str(values).strip()


def _format_personal_errors_fallback(items: list[dict[str, Any]]) -> str:
    rows: list[str] = []
    for item in items:
        pattern = str(item.get("error_pattern") or item.get("error_type") or "").strip()
        if not pattern:
            continue
        corrected = str(item.get("corrected_text") or "").strip()
        explanation = str(item.get("explanation_vi") or "").strip()
        row = pattern
        if corrected:
            row += f" | corrected: {corrected}"
        if explanation:
            row += f" | note: {explanation}"
        rows.append(row)
    return "\n".join(f"- {row}" for row in rows) or "- none"


def _format_progress_context(summary: dict[str, Any], state: dict[str, Any]) -> str:
    profile = summary.get("profile") or {}
    vocabulary = summary.get("vocabulary") or {}
    recent_errors = summary.get("recent_errors") or []
    trend = summary.get("accuracy_trend") or []
    recent_scores = [item.get("accuracy") for item in trend[-7:] if item.get("accuracy") is not None]
    latest_accuracy = round(sum(recent_scores) / len(recent_scores), 1) if recent_scores else None
    learning_state = state.get("learning_state") or {}
    lesson_id = learning_state.get("active_lesson_id") or "none"
    current_step = learning_state.get("current_step") or "NONE"
    recommended_review = state.get("recommended_review") or []
    review_text = ", ".join(str(item.get("word") or "").strip() for item in recommended_review if str(item.get("word") or "").strip()) or "none"
    recent_errors_text = ", ".join(
        str(item.get("error_pattern") or item.get("error_type") or "").strip()
        for item in recent_errors[:3]
        if str(item.get("error_pattern") or item.get("error_type") or "").strip()
    ) or "none"
    accuracy_text = f"{latest_accuracy}%" if latest_accuracy is not None else "unknown"
    return (
        f"- CEFR: {profile.get('cefr_level') or 'unknown'}\n"
        f"- Industry: {profile.get('industry') or 'unknown'}\n"
        f"- Active lesson: {lesson_id}\n"
        f"- Current learning step: {current_step}\n"
        f"- Vocabulary learned/mastered/reviews: {vocabulary.get('total_learned', 0)}/{vocabulary.get('mastered', 0)}/{vocabulary.get('total_reviews', 0)}\n"
        f"- Recent accuracy: {accuracy_text}\n"
        f"- Recent errors: {recent_errors_text}\n"
        f"- Recommended review words: {review_text}"
    )


def _build_progress_summary_for_rag(state: dict[str, Any]) -> dict[str, Any] | None:
    db = state.get("db")
    user_id = state.get("user_id")
    if db is None or not user_id:
        return None
    try:
        from ..models.user import User
        from .progress_analytics import build_user_progress_summary

        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            return None
        return build_user_progress_summary(db, user)
    except Exception:
        logger.exception("Failed to build progress summary for ENGLISH_RAG")
        return None


def _build_personal_context_items(state: dict[str, Any], *, max_items: int = 10) -> list[str]:
    items: list[str] = []
    for error in list(state.get("personal_error_context") or [])[:max_items]:
        pattern = str(error.get("error_pattern") or error.get("error_type") or "").strip()
        if not pattern:
            continue
        corrected = str(error.get("corrected_text") or "").strip()
        explanation = str(error.get("explanation_vi") or "").strip()
        detail = f"[personal_error] {pattern}"
        if corrected:
            detail += f" | corrected: {corrected}"
        if explanation:
            detail += f" | note: {explanation}"
        items.append(detail)

    remaining = max_items - len(items)
    if remaining > 0:
        for memory_item in list(state.get("memory") or []):
            content = str(memory_item.get("content") or memory_item.get("memory") or memory_item.get("text") or "").strip()
            if not content:
                continue
            items.append(f"[memory] {content}")
            if len(items) >= max_items:
                break
    return items[:max_items]


def _build_english_rag_prompt(state: dict[str, Any], user_input: str, progress_summary: dict[str, Any] | None) -> list[dict[str, str]]:
    profile = state.get("user_profile") or {}
    profile_context = (
        f"- display_name: {profile.get('display_name') or 'unknown'}\n"
        f"- cefr_level: {profile.get('cefr_level') or 'unknown'}\n"
        f"- industry: {profile.get('industry') or 'general'}\n"
        f"- learning_goals: {_format_list(profile.get('learning_goals')) or 'none'}\n"
        f"- preferred_study_time: {profile.get('preferred_study_time') or 'unknown'}"
    )
    progress_context = _format_progress_context(progress_summary or {}, state) if progress_summary else "- unavailable"
    personal_context = "\n".join(f"- {item}" for item in _build_personal_context_items(state)) or "- none"
    try:
        from .personal_error_context import format_personal_errors_for_prompt

        recurring_errors = format_personal_errors_for_prompt(state.get("personal_error_context") or []) or "- none"
    except Exception:
        recurring_errors = _format_personal_errors_fallback(state.get("personal_error_context") or [])
    mood_instruction = _mood_instruction(_mood_config(state))
    user_prompt = (
        "Trả lời bằng tiếng Việt cho người học tiếng Anh Việt Nam.\n"
        "Chỉ dùng tiếng Anh trong ví dụ, câu mẫu, từ vựng hoặc phần cần sửa.\n"
        "Giữ trọng tâm trong phạm vi học tiếng Anh, nhưng với các câu hỏi điều hướng như người học nên hỏi gì tiếp, nên học phần nào trước, hoặc bạn có thể giúp gì, hãy trả lời linh hoạt như một gia sư.\n"
        "Nếu câu hỏi thực sự lệch phạm vi, đừng trả lời trực tiếp nội dung ngoài phạm vi; chỉ từ chối ngắn gọn và kéo người học về một lựa chọn học tiếng Anh phù hợp.\n"
        "Nếu người học hỏi bạn biết/nhớ gì về họ, hãy trả lời dựa trên Profile context, Progress context, Personal recurring errors và Personal context bên dưới; đây là câu hỏi trong phạm vi học tập.\n"
        "Nếu người học đưa ra một câu, đoạn, hoặc ví dụ tiếng Anh cần kiểm tra, hãy tự đánh giá và sửa trực tiếp thay vì yêu cầu họ gửi lại theo mẫu khác.\n"
        "Nếu người học hỏi về từ vựng, ngữ pháp, cách dùng từ, hoặc sự khác biệt giữa các từ như affect/effect, hãy giải thích thẳng vào câu hỏi đó.\n"
        "Dùng context dưới đây để cá nhân hóa; không bịa dữ kiện mới.\n\n"
        f"{mood_instruction}\n\n"
        f"Profile context:\n{profile_context}\n\n"
        f"Progress context:\n{progress_context}\n\n"
        f"Personal recurring errors:\n{recurring_errors}\n\n"
        f"Personal context:\n{personal_context}\n\n"
        f"Learner question:\n{user_input}"
    )
    return build_messages_with_persona(user_prompt, turns=state.get("turns"))


def _extract_json_object(text: str) -> dict[str, Any] | None:
    cleaned = str(text or "").strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _should_assess_practice(state: dict[str, Any], user_input: str) -> bool:
    if state.get("intent", "ENGLISH_RAG") != "ENGLISH_RAG":
        return False
    message_type = str(state.get("type") or "").strip().upper()
    command = str(state.get("command") or "").strip().upper()
    if message_type == "SYSTEM_COMMAND" or command in {"REVEAL_ANSWER", "SYSTEM_COMMAND"}:
        return False
    return bool(str(user_input or "").strip())


def _build_practice_assessment_prompt(
    state: dict[str, Any],
    user_input: str,
    progress_summary: dict[str, Any] | None,
) -> list[dict[str, str]]:
    base = _build_english_rag_prompt(state, user_input, progress_summary)
    assessment_contract = (
        "\n\nAssess the latest learner message as English practice.\n"
        "Return only valid JSON with keys: status, response_vi, corrected_text, error_pattern, "
        "wrong_word, correct_word, error_type, error_dimension, error_subtype, explanation_vi, confidence.\n"
        "Allowed status values: correct, needs_revision, unclear, unavailable.\n"
        "- Use needs_revision only when there is a concrete English error.\n"
        "- For needs_revision, include a natural full corrected_text, an error_pattern like \"wrong -> correct\", "
        "a concise Vietnamese explanation_vi, and confidence from 0 to 1.\n"
        "- For correct, unclear, or unavailable, keep error_pattern, wrong_word, and correct_word empty and confidence below 0.65.\n"
        "- If the learner asks what you know or remember about them, answer from the learner profile/progress/personal context and return status unavailable with empty error fields.\n"
        "- response_vi is the learner-facing Vietnamese reply; include the correction when relevant.\n"
        f"\nLatest learner message:\n{user_input}"
    )
    base[-1]["content"] = f"{base[-1]['content']}{assessment_contract}"
    return base


async def scaffolding_engine(state: dict[str, Any]) -> dict[str, Any]:
    llm = get_llm_client()
    user_input = state["user_input"]
    cfg = _mood_config(state)
    progress_summary = _build_progress_summary_for_rag(state)

    logger.debug("scaffolding_engine: user_input=%s, llm=%s", user_input, type(llm).__name__)

    assessment_mode = _should_assess_practice(state, user_input)
    messages = (
        _build_practice_assessment_prompt(state, user_input, progress_summary)
        if assessment_mode
        else _build_english_rag_prompt(state, user_input, progress_summary)
    )
    answer = await llm.generate_chat_completion(
        messages,
        temperature=0.2,
        max_tokens=_max_tokens_for_mood(cfg, 3200),
    )
    logger.info(
        "english_rag_llm user_id=%s provider=%s model=%s prompt_tokens=%s completion_tokens=%s",
        state.get("user_id"),
        getattr(llm, "last_provider", "unknown"),
        getattr(llm, "last_model", None) or getattr(llm, "model", None),
        getattr(llm, "last_usage", {}).get("prompt_tokens", 0),
        getattr(llm, "last_usage", {}).get("completion_tokens", 0),
    )

    assessment = _extract_json_object(answer) if assessment_mode else None
    if assessment is not None:
        state["response"] = str(assessment.get("response_vi") or "").strip() or "Mình đã kiểm tra câu này cho bạn."
        state["practice_assessment"] = assessment
    elif getattr(llm, "last_provider", "mock") == "mock":
        state["response"] = f"Mình đã nhận câu hỏi tiếng Anh của bạn: {user_input}"
        state.pop("practice_assessment", None)
    else:
        state["response"] = answer
        state.pop("practice_assessment", None)

    state["hint_count"] = 0
    state["new_facts"] = []
    return state
