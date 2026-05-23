from __future__ import annotations

from typing import Any


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _display_name(profile: dict[str, Any]) -> str:
    name = _clean_text(profile.get("display_name"))
    if "@" in name:
        return ""
    return name[:60]


def _industry_phrase(industry: str) -> str:
    lowered = industry.lower()
    if not lowered or lowered == "general":
        return "đang xây nền tảng tiếng Anh theo nhu cầu thực tế của riêng bạn"
    return f"đang tập trung vào bối cảnh {industry}"


def _goals_phrase(goals: list[str]) -> str:
    cleaned = [_clean_text(goal) for goal in goals if _clean_text(goal)]
    if not cleaned:
        return "giao tiếp tự tin và dùng tiếng Anh tự nhiên hơn mỗi ngày"
    preview = cleaned[:2]
    if len(preview) == 1:
        return preview[0]
    return f"{preview[0]} và {preview[1]}"


def _weak_points_phrase(weak_points: list[str]) -> str:
    cleaned = [_clean_text(point) for point in weak_points if _clean_text(point)]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return f"- Mình sẽ để ý thêm điểm bạn hay vướng là {cleaned[0]}."
    preview = ", ".join(cleaned[:2])
    return f"- Mình sẽ để ý thêm các điểm bạn hay vướng như {preview}."


def _study_time_phrase(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    return f"Thời lượng học bạn chọn hiện tại là {text} mỗi phiên."


def build_welcome_message(profile: dict[str, Any] | None) -> str:
    profile = profile or {}
    name = _display_name(profile)
    cefr_level = _clean_text(profile.get("cefr_level")) or "trình độ hiện tại"
    industry = _clean_text(profile.get("industry")) or "môi trường học tập của bạn"
    goals = profile.get("learning_goals") or []
    weak_points = profile.get("weak_points") or []
    preferred_study_time = profile.get("preferred_study_time")

    salutation = f"Xin chào {name}, mình là Luna." if name else "Xin chào, mình là Luna."
    learner_line = (
        f"Mình biết bạn đang ở mức {cefr_level} và {_industry_phrase(industry)}. "
        f"Mục tiêu hiện tại là {_goals_phrase(goals)}. Hãy cùng nhau cố gắng để đạt được nhé."
    )
    process_lines = [
        "Quy trình học của chúng ta sẽ gồm:",
        "- Mở Bài giảng ở khung bên phải để nắm ý chính của bài học.",
        "- Chuyển sang Ôn tập để làm câu hỏi và kiểm tra mức hiểu bài.",
        "- Mở Flashcard để ghi nhớ từ vựng và cấu trúc quan trọng.",
        "- Khi hoàn thành, mình sẽ đưa bạn sang bài giảng mới tiếp theo.",
        "Bạn có thể nhắn theo các mẫu sau:",
        '- "Mở bài giảng đầu tiên" hoặc "Chuyển tôi tới bài giảng mới".',
        '- "Mở ôn tập cho bài này".',
        '- "Mở flashcard cho bài này".',
    ]
    weak_point_line = _weak_points_phrase(weak_points)
    if weak_point_line:
        process_lines.append(weak_point_line)
    study_time_line = _study_time_phrase(preferred_study_time)
    question_line = "Bạn cũng có thể hỏi mình bất cứ câu hỏi nào ngay dưới khung chat."
    encouragement_line = "Cứ bắt đầu bằng một câu tiếng Anh hoặc một tình huống bạn sắp gặp, mình sẽ cùng bạn cải thiện từng bước."
    sections = [
        salutation,
        learner_line,
        "\n".join(process_lines),
    ]
    if study_time_line:
        sections.append(study_time_line)
    sections.extend([question_line, encouragement_line])
    return "\n\n".join(sections)


def needs_welcome_message_refresh(message: str | None) -> bool:
    text = _clean_text(message)
    if not text:
        return True
    legacy_markers = (
        "Quy trình học của chúng ta sẽ gồm quan sát câu bạn viết",
        "Bạn không cần viết thật hoàn hảo ngay từ đầu",
        "- Luyện câu theo đúng bối cảnh và mục tiêu của bạn.",
    )
    required_markers = (
        "Bài giảng",
        "Ôn tập",
        "Flashcard",
        "Mở bài giảng đầu tiên",
        "Mở ôn tập cho bài này",
        "Mở flashcard cho bài này",
    )
    return (
        any(marker in text for marker in legacy_markers)
        or any(marker not in text for marker in required_markers)
        or "\n\n" not in str(message or "")
    )
