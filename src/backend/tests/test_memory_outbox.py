from __future__ import annotations

import uuid

from app.services.memory_outbox import enqueue_memory_facts, normalize_memory_fact


def test_normalize_memory_fact_scrubs_pii_and_adds_prd_metadata():
    normalized = normalize_memory_fact(
        "My boss email is jane@example.com and phone +84 912 345 678.",
        {"fact_type": "goal", "importance_score": "0.9"},
        source="chat",
        source_session="session-1",
    )

    assert normalized is not None
    content, metadata = normalized
    assert "jane@example.com" not in content
    assert "+84 912 345 678" not in content
    assert "[EMAIL]" in content
    assert "[PHONE]" in content
    assert metadata["fact_type"] == "goal"
    assert metadata["source"] == "chat"
    assert metadata["source_session"] == "session-1"
    assert metadata["importance_score"] == 0.9
    assert metadata["review_count"] == 0
    assert metadata["last_updated"]


class _FakeSession:
    def __init__(self) -> None:
        self.rows = []
        self.committed = False

    def add(self, row) -> None:
        self.rows.append(row)

    def commit(self) -> None:
        self.committed = True


def test_enqueue_memory_facts_dedupes_by_type_and_content():
    user_id = uuid.uuid4()
    db_session = _FakeSession()

    facts = [
        {"content": "Learner goal: write emails.", "metadata": {"fact_type": "goal"}},
        {"content": "Learner goal: write emails.", "metadata": {"fact_type": "goal"}},
        {"content": "Learner confuses affect and effect.", "metadata": {"fact_type": "error_pattern"}},
    ]

    added = enqueue_memory_facts(db_session, user_id=user_id, facts=facts, source="test", commit=True)

    assert added == 2
    assert db_session.committed is True
    assert len(db_session.rows) == 2
    assert {row.fact_metadata["fact_type"] for row in db_session.rows} == {"goal", "error_pattern"}
