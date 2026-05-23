from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

from app.services.personal_error_context import format_personal_errors_for_prompt, rank_personal_errors


def _row(
    pattern: str,
    *,
    source: str = "chat",
    created_at: datetime | None = None,
    normalized: str | None = None,
):
    return SimpleNamespace(
        error_type="grammar",
        error_pattern=pattern,
        normalized_error_pattern=normalized or pattern.lower(),
        corrected_text="This is better than that.",
        original_text="This is better then that.",
        explanation_vi="Dung than khi so sanh.",
        source=source,
        created_at=created_at or datetime.utcnow(),
    )


def test_rank_personal_errors_returns_empty_for_no_rows():
    assert rank_personal_errors([]) == []


def test_rank_personal_errors_groups_and_prioritizes_review_failures():
    now = datetime.utcnow()
    contexts = rank_personal_errors(
        [
            _row("article error", created_at=now - timedelta(days=1), normalized="article error"),
            _row("then -> than", created_at=now - timedelta(days=3), normalized="then -> than"),
            _row("then -> than", source="review", created_at=now, normalized="then -> than"),
        ]
    )

    assert contexts[0].normalized_error_pattern == "then -> than"
    assert contexts[0].recent_count == 2
    assert contexts[0].review_failure_count == 1


def test_format_personal_errors_for_prompt_is_compact():
    text = format_personal_errors_for_prompt(
        [
            {
                "error_type": "grammar",
                "error_pattern": "then -> than",
                "corrected_text": "This is better than that.",
                "explanation_vi": "Dung than khi so sanh.",
                "recent_count": 2,
            }
        ]
    )

    assert "then -> than" in text
    assert "recent_count=2" in text
    assert "This is better than that." in text
