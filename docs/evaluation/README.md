# Evaluation Layout

Evaluation assets are split by responsibility:

- Code: `src/evaluations`
- Data, gold labels, and machine-readable run artifacts: `data/evaluation`
- Documentation and Markdown reports: `docs/evaluation`

Run the English error-span suite from the repository root:

```powershell
$env:PYTHONPATH='src;src\backend'
python -m evaluations.runner --suite english_error_span_delta --gold-delta data\evaluation\error_eval\gold_delta.jsonl --sample-size 100 --backend http://localhost:8000 --requests-per-user 45
```

By default, JSON/JSONL/CSV run artifacts are written under
`data/evaluation/runs/<run_id>`, while the human-readable report is written to
`docs/evaluation/runs/<run_id>/report.md`.

Before running a live system evaluation, verify that chat can call a real LLM:

```powershell
cd src
$env:PYTHONPATH='backend'
python check_llm_status.py
```

Proceed only when at least one provider reports `SUCCESS` and the backend
`data/observability/llm_calls.jsonl` rows for `/api/v1/chat` show a real
provider such as `gemini` or `groq`, not `mock`.

The runner also enforces this automatically for the error-span suite: before
scoring, it sends a small `EVAL_ERROR_SPANS` preflight request. If the backend
falls back to `mock` before or during the run, the evaluation is marked
`blocked` and no detection-rate score is produced.
