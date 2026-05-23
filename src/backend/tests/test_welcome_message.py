from app.services.welcome_message import build_welcome_message


def test_build_welcome_message_uses_profile_fields():
    message = build_welcome_message(
        {
            "display_name": "Mai",
            "cefr_level": "A2",
            "industry": "IT",
            "learning_goals": ["giao tiếp trong công việc", "viết email"],
            "weak_points": ["articles", "preposition"],
            "preferred_study_time": "20 phút",
        }
    )

    assert "Xin chào Mai" in message
    assert "A2" in message
    assert "IT" in message
    assert "giao tiếp trong công việc" in message
    assert "viết email" in message
    assert "articles" in message
    assert "Bài giảng" in message
    assert "Ôn tập" in message
    assert "Flashcard" in message
    assert "Mở bài giảng đầu tiên" in message
    assert "Mở ôn tập cho bài này" in message
    assert "Mở flashcard cho bài này" in message
    assert "20 phút" in message


def test_build_welcome_message_handles_missing_profile_data():
    message = build_welcome_message({})

    assert "mình là Luna" in message
    assert "Quy trình học của chúng ta sẽ gồm" in message
    assert "Bài giảng" in message
    assert "Mở bài giảng đầu tiên" in message
    assert "khung chat" in message
