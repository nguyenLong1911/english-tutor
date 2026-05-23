"""List Gemini models available for the current API key and probe each
*embedding* model with a 1-line input so you can pick one that actually
works for Mem0.

Why this exists: the Mem0 wrapper silently falls back to an in-memory stub
when the configured embedder model returns 404. Run this once whenever you
suspect the embedder hop is broken to see (a) which models the key can
reach and (b) the **native** embedding dimension each model returns — Mem0
must be configured with that exact dimension or Qdrant will reject inserts.

Run::

    docker compose exec backend python -m tests.eval.list_gemini_models

Or, with no Docker, from a venv that has ``google-genai``::

    GOOGLE_API_KEY=... python -m backend.tests.eval.list_gemini_models
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import dotenv
import httpx


def _load_env() -> None:
    repo_root = Path(__file__).resolve().parents[4]
    root_env = repo_root / ".env"
    src_env = repo_root / "src" / ".env"
    if root_env.exists():
        dotenv.load_dotenv(dotenv_path=root_env)
    elif src_env.exists():
        dotenv.load_dotenv(dotenv_path=src_env)
    else:
        dotenv.load_dotenv()


_load_env()

API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: set GOOGLE_API_KEY or GEMINI_API_KEY in env.", file=sys.stderr)
    raise SystemExit(2)

# Why REST: ``google-genai``'s ``client.models.list()`` resolves to Vertex's
# ListPublisherModels which rejects API keys (needs OAuth2). The Gemini
# *Developer* API (generativelanguage.googleapis.com) does support API
# keys and exposes both ``models.list`` and ``models:embedContent``.
GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


KNOWN_EMBED_MODELS = [
    # Order matters: try the names Mem0 itself defaults to first.
    "models/gemini-embedding-001",
    "models/text-embedding-004",
    "models/embedding-001",
    "gemini-embedding-001",
    "text-embedding-004",
    "embedding-001",
]


def main() -> int:
    print("=" * 92)
    print("Trying ListModels on Gemini Developer API ...")
    print("=" * 92)
    embed_candidates: list[str] = []
    with httpx.Client(timeout=30) as http:
        r = http.get(f"{GEMINI_API_BASE}/models", params={"key": API_KEY})
        if r.status_code == 200:
            for m in r.json().get("models", []):
                methods = m.get("supportedGenerationMethods", [])
                print(f"  {m['name']:<50} {','.join(methods)}")
                if "embedContent" in methods:
                    embed_candidates.append(m["name"])
        else:
            print(
                f"  ListModels blocked ({r.status_code}); falling back to known-name probe list."
            )
            embed_candidates = KNOWN_EMBED_MODELS[:]

    print()
    print("=" * 92)
    print("EMBEDDING-CAPABLE MODELS — probe with 'hello world'")
    print("=" * 92)
    print(f"{'model':<50} {'status':<10} {'dim':>6}  notes")
    print("-" * 92)
    with httpx.Client(timeout=30) as http:
        for name in embed_candidates:
            path = name if name.startswith("models/") else f"models/{name}"
            try:
                resp = http.post(
                    f"{GEMINI_API_BASE}/{path}:embedContent",
                    params={"key": API_KEY},
                    json={
                        "model": path,
                        "content": {"parts": [{"text": "hello world"}]},
                    },
                )
                if resp.status_code != 200:
                    msg = resp.text[:80]
                    print(
                        f"{name:<50} {'HTTP_'+str(resp.status_code):<10} {'-':>6}  {msg}"
                    )
                    continue
                vec = resp.json()["embedding"]["values"]
                dim = len(vec)
                print(f"{name:<50} {'OK':<10} {dim:>6}")
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)[:80]
                print(f"{name:<50} {'ERROR':<10} {'-':>6}  {msg}")

    print()
    print("How to read this report")
    print("-" * 92)
    print(
        " * If any row says OK → copy that exact model name (drop the 'models/' prefix)"
    )
    print("   into EMBEDDING_MODEL in src/backend/app/core/config.py AND set")
    print("   embedding_dims in mem0_client.py to the printed `dim`.")
    print(" * If every row is HTTP_403 with 'Requests to this API ... are blocked',")
    print("   the API key is restricted to generation endpoints only. Two options:")
    print("     (a) issue a new key in AI Studio with no method restriction;")
    print("     (b) switch the embedder to a key-less local model — see")
    print("         docs/evaluation/mem0_benchmark.md §Action items.")
    print(" * If a row says HTTP_429 → quota; wait or upgrade tier.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
