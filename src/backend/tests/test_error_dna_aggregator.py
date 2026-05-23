from __future__ import annotations

from datetime import date, datetime, timedelta
from types import SimpleNamespace

from app.services.error_dna_aggregator import _dimension_for_row, _weight_for_row


def test_dimension_for_row_uses_explicit_dimension():
    row = SimpleNamespace(
        error_type="preposition",
        error_dimension="preposition",
        error_subtype="preposition_choice",
        error_pattern="in -> on",
        explanation_vi="",
    )
    assert _dimension_for_row(row) == "preposition"


def test_dimension_for_row_falls_back_to_taxonomy_inference():
    row = SimpleNamespace(
        error_type="grammar",
        error_dimension="",
        error_subtype="",
        error_pattern="a -> an",
        explanation_vi="Sai article",
    )
    assert _dimension_for_row(row) == "grammar"


def test_weight_for_row_boosts_review_failures_and_recency():
    now = datetime(2026, 5, 14, 23, 0, 0)
    chat_row = SimpleNamespace(
        confidence=0.8,
        source="chat",
        created_at=datetime.combine(date(2026, 5, 14), datetime.min.time()),
    )
    review_row = SimpleNamespace(
        confidence=0.8,
        source="review",
        created_at=datetime.combine(date(2026, 5, 14), datetime.min.time()),
    )
    old_row = SimpleNamespace(
        confidence=0.8,
        source="chat",
        created_at=datetime.combine(date(2026, 5, 7), datetime.min.time()) - timedelta(days=1),
    )

    assert _weight_for_row(review_row, now=now) > _weight_for_row(chat_row, now=now)
    assert _weight_for_row(chat_row, now=now) > _weight_for_row(old_row, now=now)
