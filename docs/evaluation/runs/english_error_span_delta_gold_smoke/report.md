# English Error Span Delta Evaluation

## Scope

This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.

## Run Metadata

| Field | Value |
|---|---|
| run_id | english_error_span_delta_gold_smoke |
| started_at | 2026-05-15T11:56:35+00:00 |
| ended_at | 2026-05-15T11:56:40+00:00 |
| backend_url | http://localhost:8000 |
| suite | english_error_span_delta |
| dataset | D:\porjects\A20-App-134\data\raw\huggingface\reddit_multigec\reddit_multi_gec_english.csv |
| sample_size | 1 |
| gold_model | gemini-2.5-pro |

## Metrics

| Metric | Value |
|---|---:|
| total_cases | 1 |
| ok_cases | 1 |
| failed_requests | 0 |
| gold_failed | 0 |
| span_precision | 1.0 |
| span_recall | 0.25 |
| span_f1 | 0.4 |
| average_error_detection_rate_per_sentence | 0.25 |
| mean_sentence_span_recall | 0.25 |
| mean_sentence_span_precision | 1.0 |
| mean_sentence_span_f1 | 0.4 |
| matched_spans | 2 |
| gold_spans | 8 |
| system_spans | 2 |
| sentence_full_match_rate | 0.0 |
| latency_ms | {'p50': 3773.0, 'p95': 3773.0} |

## Top Missed Spans

| Span | Count |
|---|---:|
| considers | 1 |
| uk exit | 1 |
| you're | 1 |
| you'd | 1 |
| holding | 1 |
| then dumping | 1 |

## Sample Results

| Dataset index | Status | Gold spans | System spans | Recall | Precision |
|---|---|---|---|---:|---:|
| 0 | ok | ["considers", "UK exit", "banking Right, but", "you're", "the 4k", "you'd", "holding", "then dumping"] | ["Right,", "the 4k"] | 0.25 | 1.00 |
