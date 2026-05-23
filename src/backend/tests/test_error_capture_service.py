from __future__ import annotations

import uuid

from app.services import error_capture_service
from app.services.error_capture_service import normalize_error_payload, normalize_error_pattern


def test_normalize_error_pattern_stable_key():
    assert normalize_error_pattern("  Responsible ABOUT -> responsible for!  ") == "responsible about -> responsible for"


def test_normalize_error_payload_rejects_empty_pattern():
    assert normalize_error_payload({"corrected_text": "I went home."}, original_text="I go home.") is None


def test_normalize_error_payload_accepts_rule_based_shape():
    payload = normalize_error_payload(
        {"wrong_word": "then", "correct_word": "than", "confidence": 0.7},
        original_text="This is better then that.",
    )

    assert payload is not None
    assert payload["error_pattern"] == "then -> than"
    assert payload["normalized_error_pattern"] == "then -> than"
    assert payload["confidence"] == 0.7
    assert payload["error_dimension"] == "vocab"
    assert payload["error_subtype"] == "word_choice"


def test_normalize_error_payload_prefers_explicit_taxonomy():
    payload = normalize_error_payload(
        {
            "error_pattern": "in -> on",
            "error_type": "preposition",
            "error_dimension": "preposition",
            "error_subtype": "preposition_choice",
            "confidence": 0.92,
        },
        original_text="I am in Monday.",
    )

    assert payload is not None
    assert payload["error_dimension"] == "preposition"
    assert payload["error_subtype"] == "preposition_choice"


def test_normalize_error_payload_infers_article_taxonomy():
    payload = normalize_error_payload(
        {
            "error_pattern": "a -> an",
            "error_type": "grammar",
            "explanation_vi": "Sai article truoc nguyen am.",
            "confidence": 0.88,
        },
        original_text="a apple",
    )

    assert payload is not None
    assert payload["error_dimension"] == "grammar"
    assert payload["error_subtype"] == "article"


def test_write_memory_fact_respects_hotpath_flag(monkeypatch):
    called = False

    class _Memory:
        def add_memory(self, *args, **kwargs):  # pragma: no cover
            nonlocal called
            called = True

    monkeypatch.setenv("MEMORY_HOTPATH_ENABLED", "false")
    monkeypatch.setattr(error_capture_service, "get_memory", lambda: _Memory())

    error_capture_service._write_memory_fact(
        user_id=uuid.uuid4(),
        normalized={"error_pattern": "then -> than", "confidence": 0.95, "error_type": "vocab"},
        duplicate_recent=True,
        source="chat",
    )

    assert called is False
