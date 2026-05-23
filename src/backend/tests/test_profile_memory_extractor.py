from __future__ import annotations

from app.services.profile_memory_extractor import extract_profile_facts


def test_extract_profile_facts_captures_exam_preference_and_study_habit():
    facts = extract_profile_facts(
        "Tôi sắp thi IELTS vào ngày 20/06. Tôi thích học nhiều ví dụ thực tế. Mỗi ngày tôi học 2 tiếng vào buổi tối.",
        intent="ENGLISH_RAG",
        learning_intent="NONE",
    )

    fact_types = [(fact["metadata"]["fact_type"], fact["content"]) for fact in facts]

    assert any(kind == "exam_target" and "20/06" in content for kind, content in fact_types)
    assert any(kind == "study_preference" and "ví dụ thực tế" in content for kind, content in fact_types)
    assert any(kind == "study_habit" and "2 tiếng" in content for kind, content in fact_types)


def test_extract_profile_facts_skips_learning_navigation_messages():
    facts = extract_profile_facts(
        "Tôi muốn mở bài giảng mới",
        intent="ENGLISH_RAG",
        learning_intent="NEXT_LESSON",
    )

    assert facts == []
