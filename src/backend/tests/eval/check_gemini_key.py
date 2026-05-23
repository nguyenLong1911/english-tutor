"""Probe the current Gemini credential for both LLM and embedding access.

This script is intentionally small and explicit:

1. Exercise the app's current Gemini LLM path using ``GeminiLLMClient``.
2. Probe the configured embedding model on the Gemini Developer API
   (``embedContent``).
3. Probe the same embedding model on Vertex AI's ``:predict`` endpoint.

Run inside the backend container so it picks up the live env::

    docker compose exec backend python -m tests.eval.check_gemini_key
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import dotenv
import httpx

from app.core.config import get_settings
from app.utils.llm import GeminiLLMClient


def _load_env() -> None:
    for candidate in [Path.cwd(), *Path(__file__).resolve().parents]:
        root_env = candidate / ".env"
        src_env = candidate / "src" / ".env"
        if root_env.exists():
            dotenv.load_dotenv(dotenv_path=root_env)
            return
        if src_env.exists():
            dotenv.load_dotenv(dotenv_path=src_env)
            return
    dotenv.load_dotenv()


def _pick_key(settings) -> str:
    if settings.GOOGLE_API_KEY and settings.GOOGLE_API_KEY.startswith("AQ."):
        return settings.GOOGLE_API_KEY
    return settings.GEMINI_API_KEY or settings.GOOGLE_API_KEY or ""


def _mask(secret: str) -> str:
    if not secret:
        return "<unset>"
    if len(secret) <= 12:
        return secret[:4] + "..."
    return f"{secret[:6]}…{secret[-4:]}"


def _key_kind(secret: str) -> str:
    if secret.startswith("AQ."):
        return "vertex-express"
    if secret.startswith("AIza"):
        return "ai-studio"
    return "unknown"


def _print_header(settings, api_key: str) -> None:
    print("=" * 96)
    print("Gemini key probe")
    print(f"  key                 = {_mask(api_key)} ({_key_kind(api_key)})")
    print(f"  GOOGLE_GENAI_USE_VERTEXAI = {os.getenv('GOOGLE_GENAI_USE_VERTEXAI', '<unset>')}")
    print(f"  GOOGLE_CLOUD_PROJECT      = {os.getenv('GOOGLE_CLOUD_PROJECT', '<unset>')}")
    print(f"  GOOGLE_CLOUD_LOCATION     = {os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')}")
    print(f"  LLM_MODEL           = {settings.LLM_MODEL}")
    print(f"  EMBEDDING_MODEL     = {settings.EMBEDDING_MODEL}")
    print("=" * 96)


def _probe_llm(settings, api_key: str) -> tuple[bool, dict[str, Any]]:
    client = GeminiLLMClient(api_key=api_key, model=settings.LLM_MODEL)
    messages = [{"role": "user", "content": "Reply with exactly OK."}]
    try:
        text = client._request_once(messages, temperature=0.0, max_tokens=16)
        return True, {
            "provider": "app-gemini-client",
            "route": "vertex-first-then-legacy-fallback",
            "model": client.last_model,
            "reply": text,
            "prompt_tokens": client.last_usage.get("prompt_tokens", 0),
            "completion_tokens": client.last_usage.get("completion_tokens", 0),
        }
    except Exception as exc:  # noqa: BLE001
        return False, {
            "provider": "app-gemini-client",
            "route": "vertex-first-then-legacy-fallback",
            "model": settings.LLM_MODEL,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _probe_embed_dev_api(settings, api_key: str) -> tuple[bool, dict[str, Any]]:
    model = settings.EMBEDDING_MODEL
    path = model if model.startswith("models/") else f"models/{model}"
    url = f"https://generativelanguage.googleapis.com/v1beta/{path}:embedContent"
    payload = {
        "model": path,
        "content": {"parts": [{"text": "hello world"}]},
    }
    try:
        with httpx.Client(timeout=30) as http:
            resp = http.post(url, params={"key": api_key}, json=payload)
        if resp.status_code != 200:
            return False, {
                "provider": "developer-api",
                "model": model,
                "status_code": resp.status_code,
                "error": resp.text[:500],
            }
        body = resp.json()
        values = ((body.get("embedding") or {}).get("values") or [])
        return True, {
            "provider": "developer-api",
            "model": model,
            "dimension": len(values),
        }
    except Exception as exc:  # noqa: BLE001
        return False, {
            "provider": "developer-api",
            "model": model,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def _vertex_host() -> str:
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip() or "us-central1"
    if location == "global":
        return "https://aiplatform.googleapis.com"
    return f"https://{location}-aiplatform.googleapis.com"


def _vertex_model_path(model: str) -> str:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1").strip() or "us-central1"
    if project:
        return f"projects/{project}/locations/{location}/publishers/google/models/{model}"
    return f"publishers/google/models/{model}"


def _vertex_embed_payload(model: str) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "instances": [{"content": "hello world", "task_type": "RETRIEVAL_DOCUMENT"}]
    }
    if model.startswith("gemini-embedding"):
        payload["parameters"] = {"outputDimensionality": 1536}
    return payload


def _probe_embed_vertex(settings, api_key: str) -> tuple[bool, dict[str, Any]]:
    model = settings.EMBEDDING_MODEL
    url = f"{_vertex_host()}/v1/{_vertex_model_path(model)}:predict"
    try:
        with httpx.Client(timeout=30) as http:
            resp = http.post(url, params={"key": api_key}, json=_vertex_embed_payload(model))
        if resp.status_code != 200:
            return False, {
                "provider": "vertex-predict",
                "model": model,
                "status_code": resp.status_code,
                "error": resp.text[:500],
            }
        body = resp.json()
        predictions = body.get("predictions") or []
        first = predictions[0] if predictions else {}
        values = (
            ((first.get("embeddings") or {}).get("values"))
            or ((first.get("embedding") or {}).get("values"))
            or []
        )
        return True, {
            "provider": "vertex-predict",
            "model": model,
            "dimension": len(values),
        }
    except Exception as exc:  # noqa: BLE001
        return False, {
            "provider": "vertex-predict",
            "model": model,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def main() -> int:
    _load_env()
    settings = get_settings()
    api_key = _pick_key(settings)
    if not api_key:
        print("ERROR: GEMINI_API_KEY / GOOGLE_API_KEY is not set", file=sys.stderr)
        return 2

    _print_header(settings, api_key)

    results = [
        ("llm",) + _probe_llm(settings, api_key),
        ("embed_dev_api",) + _probe_embed_dev_api(settings, api_key),
        ("embed_vertex",) + _probe_embed_vertex(settings, api_key),
    ]

    for name, ok, payload in results:
        print(f"[{name}] {'OK' if ok else 'FAIL'}")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        print("-" * 96)

    llm_ok = results[0][1]
    embed_ok = results[1][1] or results[2][1]

    if llm_ok and embed_ok:
        print("SUMMARY: key can generate text and can embed on at least one endpoint.")
        return 0
    if llm_ok:
        print("SUMMARY: LLM works, but embedding failed on every probed endpoint.")
        return 1
    if embed_ok:
        print("SUMMARY: embedding works, but LLM generation failed.")
        return 1
    print("SUMMARY: both LLM and embedding failed.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
