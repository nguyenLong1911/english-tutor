from datetime import datetime, timezone

from app.services.metrics_collector import build_metrics_payload


def test_build_metrics_payload_normalizes_counts():
    payload = build_metrics_payload(
        total_users=4,
        total_reviews=10,
        mastered_words=3,
        vocabulary_size=25,
        avg_token_per_session=120,
        cost_today=1.234,
        p95_latency_ms=47.556,
        captured_at=datetime(2026, 5, 5, 8, 30, tzinfo=timezone.utc),
    )

    assert payload["total_users"] == 4
    assert payload["total_reviews"] == 10
    assert payload["avg_reviews_per_user"] == 2.5
    assert payload["mastered_words"] == 3
    assert payload["vocabulary_size"] == 25
    assert payload["avg_token_per_session"] == 120
    assert payload["cost_today"] == 1.23
    assert payload["p95_latency_ms"] == 47.56
    assert payload["last_snapshot_at"] == "2026-05-05T08:30:00+00:00"