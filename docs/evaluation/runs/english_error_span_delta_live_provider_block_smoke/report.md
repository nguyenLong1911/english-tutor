# English Error Span Delta Evaluation

## Scope

This run compares Gemini-generated gold incorrect spans against spans returned by the live chat system.

## Run Metadata

| Field | Value |
|---|---|
| run_id | english_error_span_delta_live_provider_block_smoke |
| started_at | 2026-05-15T13:40:04+00:00 |
| ended_at | 2026-05-15T13:40:06+00:00 |
| backend_url | http://localhost:8000 |
| suite | english_error_span_delta |
| dataset | D:\porjects\A20-App-134\data\raw\huggingface\reddit_multigec\reddit_multi_gec_english.csv |
| sample_size | 1 |
| gold_model | gemini-2.5-pro |

## Metrics

| Metric | Value |
|---|---:|
| total_cases | 1 |
| ok_cases | 0 |
| failed_requests | 0 |
| gold_failed | 0 |
| decision | blocked |
| blocker | Live LLM preflight failed: HTTP 503 {"error":"Request failed","detail":"Evaluation requires a live LLM provider, got mock","trace_id":"english_error_span_delta_live_provider_block_smoke.preflight_live_llm"} |

## Top Missed Spans

No missed spans.

## Sample Results

| Dataset index | Status | Gold spans | System spans | Recall | Precision |
|---|---|---|---|---:|---:|
