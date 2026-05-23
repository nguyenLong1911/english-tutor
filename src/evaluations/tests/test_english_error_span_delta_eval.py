from __future__ import annotations

import json

from evaluations.english_error_span_delta import build_summary, load_gold_delta_rows


def test_load_gold_delta_rows_uses_text_and_dedupes_by_dataset_index(tmp_path):
    path = tmp_path / "gold_delta.jsonl"
    rows = [
        {"dataset_index": 1, "text": "My name are Long", "correction": "My name is Long", "gold_spans": ["are"], "gold_status": "ok"},
        {"dataset_index": 1, "text": "My name are Long", "correction": "My name is Long", "gold_spans": [], "gold_status": "error"},
        {"dataset_index": 2, "text": "She go home", "correction": "She goes home", "gold_spans": ["go"], "gold_status": "ok"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")

    loaded = load_gold_delta_rows(path)

    assert [row["dataset_index"] for row in loaded] == [1, 2]
    assert loaded[0]["text"] == "My name are Long"
    assert loaded[0]["gold_spans"] == ["are"]


def test_build_summary_reports_average_error_detection_rate_per_sentence():
    results = [
        {
            "status": "ok",
            "gold_status": "ok",
            "latency_ms": 10,
            "score": {
                "gold_spans": 2,
                "system_spans": 1,
                "matched_spans": 1,
                "span_precision": 1.0,
                "span_recall": 0.5,
                "span_f1": 0.6667,
                "sentence_full_match": False,
                "missed_spans": ["are"],
            },
        },
        {
            "status": "ok",
            "gold_status": "ok",
            "latency_ms": 20,
            "score": {
                "gold_spans": 1,
                "system_spans": 1,
                "matched_spans": 1,
                "span_precision": 1.0,
                "span_recall": 1.0,
                "span_f1": 1.0,
                "sentence_full_match": True,
                "missed_spans": [],
            },
        },
    ]

    summary = build_summary(results)

    assert summary["span_recall"] == 0.6667
    assert summary["average_error_detection_rate_per_sentence"] == 0.75
    assert summary["mean_sentence_span_recall"] == 0.75
