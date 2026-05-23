"""List + probe Vertex AI embedding models reachable with the project's
Express-Mode API key (the ``AQ.…`` token, **not** an AI-Studio ``AIza…`` key).

Why this exists:

* ``tests.eval.list_gemini_models`` talks to the **AI Studio Developer API**
  (`generativelanguage.googleapis.com`). That endpoint silently refuses keys
  that were issued in Vertex Express Mode and refuses *any* key for
  ``embedContent`` once the project has been migrated to Vertex.
* Mem0's Gemini embedder block routes through the same Developer API, so
  it 404s in that case — exactly what we see in
  ``docs/evaluation/mem0_benchmark.md``.

This script:

1. Resolves the right Vertex publisher-model REST path for the project +
   region in env (`GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`).
2. POSTs ``:predict`` for each candidate embedding model with the
   ``AQ.…`` Express key as ``?key=…``.
3. Prints status + native vector dim per model so you can pick one.

Run inside the backend container so env vars are picked up::

    docker compose exec backend python -m tests.eval.list_vertex_models
"""
from __future__ import annotations

import os
import sys
from typing import Any

import httpx

API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or ""
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

if not API_KEY:
    print("ERROR: GOOGLE_API_KEY / GEMINI_API_KEY not set", file=sys.stderr)
    raise SystemExit(2)

# Vertex AI Express Mode resolves "global" to us-central1 transparently;
# explicit endpoints below mirror what google-genai 1.x does internally.
if LOCATION in ("", "global"):
    HOST = "https://aiplatform.googleapis.com"
else:
    HOST = f"https://{LOCATION}-aiplatform.googleapis.com"


# Models worth probing. Native dims (from Vertex docs) shown for reference;
# the script also prints the *actually returned* dim which is the source
# of truth for the Mem0 + Qdrant config.
CANDIDATES: list[tuple[str, int]] = [
    ("text-embedding-004", 768),
    ("text-embedding-005", 768),
    ("text-multilingual-embedding-002", 768),
    ("gemini-embedding-001", 3072),  # output_dimensionality configurable 768/1536/3072
]


def _publisher_model_path(model_id: str) -> str:
    # Vertex Express-Mode keys also accept the project-less publisher URL,
    # but the project-scoped form is what google-genai uses, so we mirror it.
    if PROJECT:
        return f"projects/{PROJECT}/locations/{LOCATION or 'us-central1'}/publishers/google/models/{model_id}"
    return f"publishers/google/models/{model_id}"


def _build_payload(model_id: str) -> dict[str, Any]:
    body: dict[str, Any] = {"instances": [{"content": "hello world", "task_type": "RETRIEVAL_DOCUMENT"}]}
    # gemini-embedding-001 lets you pick the output dim explicitly.
    if model_id.startswith("gemini-embedding"):
        body["parameters"] = {"outputDimensionality": 1536}
    return body


def main() -> int:
    print("=" * 96)
    print("Vertex AI embedding probe")
    print(f"  project  = {PROJECT or '<unset>'}")
    print(f"  location = {LOCATION or '<unset>'}")
    print(f"  host     = {HOST}")
    print(f"  key      = {API_KEY[:6]}…{API_KEY[-4:]}  ({'Express AQ.' if API_KEY.startswith('AQ.') else 'AI Studio AIza' if API_KEY.startswith('AIza') else 'unknown'})")
    print("=" * 96)
    print(f"{'model':<38} {'status':<10} {'dim':>5}  notes")
    print("-" * 96)
    with httpx.Client(timeout=30) as http:
        for model_id, doc_dim in CANDIDATES:
            url = f"{HOST}/v1/{_publisher_model_path(model_id)}:predict"
            try:
                resp = http.post(url, params={"key": API_KEY}, json=_build_payload(model_id))
            except Exception as exc:  # noqa: BLE001
                print(f"{model_id:<38} {'EXC':<10} {'-':>5}  {str(exc)[:60]}")
                continue
            if resp.status_code != 200:
                snippet = resp.text.replace("\n", " ")[:60]
                print(f"{model_id:<38} HTTP_{resp.status_code:<5} {doc_dim:>5}  {snippet}")
                continue
            preds = resp.json().get("predictions", [])
            if not preds:
                print(f"{model_id:<38} {'EMPTY':<10} {'-':>5}  no predictions in response")
                continue
            vec = preds[0].get("embeddings", {}).get("values") or preds[0].get("embedding", {}).get("values") or []
            print(f"{model_id:<38} {'OK':<10} {len(vec):>5}  doc-dim={doc_dim}")

    print()
    print("Mem0 wiring (after picking a working model from the table above):")
    print(" 1. src/backend/app/core/config.py:")
    print("      EMBEDDING_MODEL = '<the model id you picked>'   # bare name")
    print(" 2. src/backend/app/core/mem0_client.py → _base_mem0_config():")
    print("      change embedder.provider to 'vertexai' if Mem0 supports it on")
    print("      your installed version (>=0.1.40); else keep 'gemini' AND")
    print("      flip the SDK env: unset GOOGLE_GENAI_USE_VERTEXAI for the")
    print("      embedder call path only.")
    print(" 3. set embedding_dims = <the dim printed for the OK row>.")
    print(" 4. drop the Qdrant collection so it's recreated with the right dim:")
    print("      curl -X DELETE http://qdrant:6333/collections/tutor_memory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
