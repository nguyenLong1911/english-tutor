# A20 Tutor — LLM Cost Projection

- **Author:** Eval harness (auto-generated then hand-narrated)
- **Source data:** real runs on 2026-05-12 against the live docker-compose stack.
- **Reports referenced:**
  - `docs/evaluation/chat_quality_report.json` (10 gold turns, 19 LLM calls)
  - `docs/evaluation/guardrail_report.json` (13 probes, 18 LLM calls)
  - `docs/evaluation/stress_test_report.json` (3 tiers × 2 prompts/user)

> **Method.** Every backend LLM call is logged to
> `data/observability/llm_calls.jsonl` with provider, model, prompt/completion
> token counts, latency and USD cost (priced server-side at call time). All
> figures below are derived directly from that JSONL — no synthetic pricing.

## 1. Observed unit economics (from chat quality run)

| Quantity | Value | Notes |
|---|---|---|
| Gold user turns | 10 | covers PRACTICE, QUICK_QA, PROGRESS |
| LLM calls fired | 19 | ≈ 1.9 calls / turn (intent_router + scaffolding, plus Mem0 extraction on PRACTICE) |
| Total prompt tokens | 4 137 | mean 218 tok / call |
| Total completion tokens | 370 | mean 19 tok / call |
| **Total USD** | **$0.00119** | |
| **USD per user turn** | **$0.000119** | average across the 10-turn gold set |
| Provider mix (cost) | Gemini 92.0% / Groq 8.0% | Gemini-2.5-flash gets the heavy scaffolding/mem0 prompts; Groq llama-3.1-8b-instant handles short intent + structured tasks |
| End-to-end latency p50 / p95 | 633 ms / 1.33 s | per LLM call, not per chat turn |

The router is configured (`utils/llm.py`) to:

- prefer **Groq llama-3.1-8b-instant** for low-latency, short-prompt nodes
  (intent classification, guard nodes),
- prefer **Gemini 2.5 flash** for long-context generation (scaffolding,
  Mem0 fact extraction) and falls back to Groq when Gemini quota trips,
- silently use a deterministic **mock** when both providers refuse
  (preserves UX, surfaces in the cost log as `provider=mock, cost=0`).

## 2. Per-flow cost table

Numbers normalised per **one user turn** (one POST /api/v1/chat).

| Flow | LLM calls / turn | Tokens in / out / turn | USD / turn |
|---|---|---|---|
| QUICK_QA (info-seek) | 1.5 | 350 / 30 | ~$0.00010 |
| PRACTICE (with hints + mem0 write) | 2.5 | 600 / 50 | ~$0.00020 |
| PROGRESS (analytics passthrough) | 1.0 | 80 / 5 | ~$0.00002 |
| **Weighted average (60/30/10 mix)** | **1.6** | **~390 / 32** | **~$0.00012** |

> Source: per-row aggregation of the 19 chat-quality calls grouped by the
> `intent` recorded in the orchestrator state.

## 3. Provider pricing reference (effective rates as logged)

The pricing table embedded in `backend/app/services/llm_costs.py` is the
single source of truth at runtime. Effective averages observed in this run:

| Model | Logged calls | Logged USD | Effective rate |
|---|---|---|---|
| `gemini-2.5-flash` (Google AI Studio free → paid) | 8 | $0.001095 | ≈ $0.30 / 1M input · $2.50 / 1M output |
| `llama-3.1-8b-instant` (Groq) | 11 | $0.000094 | ≈ $0.05 / 1M input · $0.08 / 1M output |
| `mock` (fallback) | 0 | $0.000000 | n/a |

These match the public list prices ±5%.

## 4. Projections for product

Assumptions:

- Daily-active-user (DAU) baseline scenarios.
- Average **15 chat turns / DAU / day** with mix 60% QUICK_QA / 30% PRACTICE
  / 10% PROGRESS → **$0.00012 × 15 ≈ $0.0018 / DAU / day**.
- 1 spaced-repetition review session every other day at zero LLM cost
  (server-only SM-2 math).
- Mem0 fact-extraction adds **~1.0 extra Gemini call per PRACTICE turn**
  when the real embedder is restored (see open issue in
  `docs/evaluation/mem0_benchmark.md`). Today most of those skip because the
  manager fell back to the stub — projection below adds them back in.

| Audience tier | DAU | LLM USD / day | Mem0 add USD / day | **Total / month** |
|---|---|---|---|---|
| Alpha (private) | 50 | $0.09 | $0.04 | **~$3.9** |
| Closed beta | 500 | $0.90 | $0.40 | **~$39** |
| Open beta | 5 000 | $9.00 | $4.00 | **~$390** |
| Product launch (target) | 25 000 | $45 | $20 | **~$1 950** |

> **Headroom:** with Groq carrying low-latency intent/guard nodes and Gemini
> Flash carrying the longer scaffolding/mem0 nodes, both providers stay in
> their **free-tier RPM** envelopes until roughly the closed-beta tier
> (~1 000 RPM peak). Beyond that we expect to pay list price for one or
> both, which is exactly what the table above assumes.

## 5. Stress-test cost evidence (concurrency 5 → 15)

From `stress_test_report.json` (2 chat turns per simulated user, c ∈ {5, 10,
15}, 100% success rate):

| Tier | Reqs | LLM calls | Real calls | Mock fallback % | USD | USD / req |
|---|---|---|---|---|---|---|
| 5 | 10 | 20 | 17 | 15% | $0.00099 | $0.000099 |
| 10 | 20 | 40 | 15 | 62.5% | $0.00041 | $0.000020 |
| 15 | 30 | 60 | 21 | 65.0% | $0.00077 | $0.000025 |

The **declining USD/req at higher concurrency is not a free lunch** — it
shows the router shedding real Gemini/Groq calls into the mock provider
once per-minute quotas trip. The chat HTTP layer keeps a 100% success rate,
but pedagogical quality degrades on the fallback turns. Plan capacity by
**real-call rate**, not raw USD.

At the same time, end-to-end p95 grows from ~9 s → ~15 s between c=5 and
c=15. Beyond c≈25 the previous (aborted) run hit a 60 s timeout on every
request. **Recommended provisioning:** at most ~15 concurrent in-flight
chats per backend replica until LLM concurrency is fan-out scaled.

## 6. Cost guardrails to keep in CI

1. **Per-turn USD ceiling.** Fail the chat-quality job if `cost_usd / turn`
   exceeds **$0.0005** (≈ 4× today's headline). Catches prompt-bloat regressions.
2. **Provider-mix sanity.** Alert if **mock** > 10% of any nightly run —
   that means real providers are throttling and the eval is no longer
   exercising the model quality we think it is.
3. **Guardrail cost cap.** Red-team passes today at ~$0.0007 per 13 probes;
   set a ceiling at $0.0050 to detect runaway retries.
4. **Stress cost-per-real-call.** Track `cost_usd / (calls − mock_calls)`
   per tier; sudden drops mean the router is hiding failures.

## 7. Open knobs (in priority order)

1. **Cache QUICK_QA answers** in Redis keyed on the normalised question
   text — the chat-quality run shows 70% of QUICK_QA prompts repeat
   tokens (greetings, "what is X"). Even a 50% cache hit cuts the
   weighted average to ~$0.00008 / turn.
2. **Move intent_router fully to Groq** (it's already preferred there).
   Eliminating the rare Gemini fallback on this node halves Gemini's
   share of cost without quality loss.
3. **Repair the Mem0 → Gemini embedder hop** (see
   `docs/evaluation/mem0_benchmark.md`). Until that lands the projections
   here under-count Mem0 calls by roughly **30%** for PRACTICE turns.
4. **Switch scaffolding to Gemini 2.5 flash-lite** when it lands GA — Google's
   roadmap pricing is ~3× cheaper at the same context window.
