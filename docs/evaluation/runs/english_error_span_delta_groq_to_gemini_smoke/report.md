# English Error Span Delta Evaluation

## Scope

This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.

## Run Metadata

| Field | Value |
|---|---|
| run_id | english_error_span_delta_groq_to_gemini_smoke |
| started_at | 2026-05-15T13:43:23+00:00 |
| ended_at | 2026-05-15T13:43:27+00:00 |
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
| format_compliance_rate | 1.0 |
| span_precision | 1.0 |
| span_recall | 0.125 |
| span_f1 | 0.2222 |
| average_error_detection_rate_per_sentence | 0.125 |
| mean_sentence_span_recall | 0.125 |
| mean_sentence_span_precision | 1.0 |
| mean_sentence_span_f1 | 0.2222 |
| matched_spans | 1 |
| gold_spans | 8 |
| system_spans | 1 |
| sentence_full_match_rate | 0.0 |
| latency_ms | {'p50': 625.0, 'p95': 625.0} |

## Top Missed Spans

| Span | Count |
|---|---:|
| considers | 1 |
| uk exit | 1 |
| you're | 1 |
| the 4k | 1 |
| you'd | 1 |
| holding | 1 |
| then dumping | 1 |

## Sample Results

| Dataset index | Status | Gold spans | System spans | Recall | Precision |
|---|---|---|---|---:|---:|
| 0 | ok | ["considers", "UK exit", "banking Right, but", "you're", "the 4k", "you'd", "holding", "then dumping"] | ["Right,"] | 0.12 | 1.00 |
