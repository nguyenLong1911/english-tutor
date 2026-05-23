from __future__ import annotations

import json
import logging
import uuid

import pytest
from fastapi.testclient import TestClient

from app.api.v1 import learning as learning_module
from app.main import app


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_learning_store():
    learning_module.learning_store = learning_module.InMemoryLearningStore()
    yield


def _user_id() -> str:
    return f"learning-test-{uuid.uuid4().hex}"


def _start(user_id: str) -> dict:
    response = client.post("/api/v1/learning/start", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return response.json()


def _questions(user_id: str, lesson_id: str) -> dict:
    response = client.post(f"/api/v1/learning/{lesson_id}/questions", json={"user_id": user_id})
    assert response.status_code == 200, response.text
    return response.json()


def _correct_answers(questions: list[dict]) -> list[dict[str, str]]:
    answers = []
    for question in questions:
        answer = question["correct_answer"]
        if question["type"] == "write_sentence":
            answer = f"I use {answer} at work today"
        answers.append({"question_id": question["question_id"], "answer": answer})
    return answers


def _latest_logged_payload(caplog, event: str) -> dict:
    prefix = f"frontend_payload.{event} "
    messages = [record.getMessage() for record in caplog.records if record.getMessage().startswith(prefix)]
    assert messages
    return json.loads(messages[-1].removeprefix(prefix))


def test_start_learning_starts_and_resumes_lesson():
    user_id = _user_id()

    first = _start(user_id)
    second = client.post("/api/v1/learning/start", json={"user_id": user_id})

    assert second.status_code == 200, second.text
    resumed = second.json()
    assert resumed["lesson"]["lesson_id"] == first["lesson"]["lesson_id"]
    assert resumed["state"]["current_step"] == "LESSON_READING"
    assert resumed["ui_directive"]["screen"] == "LESSON_READER"
    assert "agent_message" in resumed


def test_current_learning_state_returns_active_lesson():
    user_id = _user_id()
    started = _start(user_id)

    response = client.get(f"/api/v1/learning/current?user_id={user_id}")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"]["active_lesson_id"] == started["lesson"]["lesson_id"]
    assert data["lesson"]["markdown"]
    assert data["ui_directive"]["screen"] == "LESSON_READER"
    assert "agent_message" in data


def test_current_learning_state_info_log_uses_lesson_metadata(caplog):
    user_id = _user_id()
    started = _start(user_id)

    with caplog.at_level(logging.INFO, logger=learning_module.logger.name):
        response = client.get(f"/api/v1/learning/current?user_id={user_id}")

    assert response.status_code == 200, response.text
    logged_payload = _latest_logged_payload(caplog, "learning.current.lesson")
    assert logged_payload["lesson"]["lesson_id"] == started["lesson"]["lesson_id"]
    assert logged_payload["lesson"]["markdown_chars"] > 0
    assert "markdown" not in logged_payload["lesson"]
    assert logged_payload["state"]["current_step"] == "LESSON_READING"
    assert logged_payload["ui_directive"]["screen"] == "LESSON_READER"


def test_questions_endpoint_returns_twelve_questions():
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]

    data = _questions(user_id, lesson_id)

    assert data["lesson_id"] == lesson_id
    assert data["total_questions"] == 12
    assert len(data["questions"]) == 12
    assert data["question_counts"] == {
        "multiple_choice_abcd": 5,
        "write_sentence": 3,
        "vocab_answer": 2,
        "quick_definition": 2,
    }
    assert data["ui_directive"]["screen"] == "PRACTICE_RUNNER"
    assert "agent_message" in data


def test_questions_endpoint_info_log_uses_question_metadata(caplog):
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]

    with caplog.at_level(logging.INFO, logger=learning_module.logger.name):
        data = _questions(user_id, lesson_id)

    assert data["total_questions"] == 12
    logged_payload = _latest_logged_payload(caplog, "learning.questions")
    assert logged_payload["lesson_id"] == lesson_id
    assert logged_payload["practice_set_id"] == data["practice_set_id"]
    assert logged_payload["total_questions"] == 12
    assert logged_payload["question_counts"] == data["question_counts"]
    assert len(logged_payload["question_types"]) == 12
    assert logged_payload["question_types"][0] == {
        "question_id": data["questions"][0]["question_id"],
        "type": data["questions"][0]["type"],
    }
    assert "questions" not in logged_payload
    assert logged_payload["ui_directive"]["screen"] == "PRACTICE_RUNNER"


def test_submit_endpoint_returns_score_and_practice_result_directive():
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]
    practice = _questions(user_id, lesson_id)

    response = client.post(
        f"/api/v1/learning/{lesson_id}/questions/submit",
        json={
            "user_id": user_id,
            "practice_set_id": practice["practice_set_id"],
            "answers": _correct_answers(practice["questions"]),
        },
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["score"] == 12
    assert data["total"] == 12
    assert data["accuracy"] == 1.0
    assert data["passed"] is True
    assert data["ui_directive"]["screen"] == "PRACTICE_RESULT"
    assert data["suggested_actions"] == [
        {"label": "Mở flashcard", "intent": "LESSON_FLASHCARD"},
        {"label": "Ôn tập lại", "intent": "LESSON_PRACTICE"},
        {"label": "Đọc lại bài", "intent": "READ_LESSON"},
    ]


def test_flashcards_endpoint_returns_five_cards():
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]

    response = client.get(f"/api/v1/learning/{lesson_id}/flashcards?user_id={user_id}")

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["lesson_id"] == lesson_id
    assert data["total_cards"] == 5
    assert len(data["cards"]) == 5
    assert data["ui_directive"]["screen"] == "FLASHCARD_RUNNER"
    assert "agent_message" in data


def test_flashcards_endpoint_info_log_uses_card_metadata(caplog):
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]

    with caplog.at_level(logging.INFO, logger=learning_module.logger.name):
        response = client.get(f"/api/v1/learning/{lesson_id}/flashcards?user_id={user_id}")

    assert response.status_code == 200, response.text
    data = response.json()
    logged_payload = _latest_logged_payload(caplog, "learning.vocabulary.flashcards")
    assert logged_payload["lesson_id"] == lesson_id
    assert logged_payload["total_cards"] == 5
    assert len(logged_payload["card_metadata"]) == 5
    assert logged_payload["card_metadata"][0] == {
        "card_id": data["cards"][0]["card_id"],
        "lesson_id": data["cards"][0]["lesson_id"],
        "pos": data["cards"][0]["pos"],
        "source": data["cards"][0]["source"],
    }
    assert "cards" not in logged_payload
    assert logged_payload["ui_directive"]["screen"] == "FLASHCARD_RUNNER"


def test_complete_endpoint_marks_lesson_complete_and_returns_next_lesson():
    user_id = _user_id()
    lesson_id = _start(user_id)["lesson"]["lesson_id"]
    client.get(f"/api/v1/learning/{lesson_id}/flashcards?user_id={user_id}")

    response = client.post(f"/api/v1/learning/{lesson_id}/complete", json={"user_id": user_id})

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["completed_lesson_id"] == lesson_id
    assert data["learning_state"]["current_step"] == "LESSON_COMPLETE"
    assert lesson_id in data["learning_state"]["completed_lessons"]
    assert data["next_lesson_id"]
    assert data["next_lesson"]["lesson_id"] == data["next_lesson_id"]
    assert data["ui_directive"]["screen"] == "LESSON_COMPLETE"
    assert data["ui_directive"]["next_lesson_id"] == data["next_lesson_id"]
