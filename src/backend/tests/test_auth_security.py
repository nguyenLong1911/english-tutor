"""Unit tests for app.core.security (bcrypt + JWT helpers)."""
from __future__ import annotations

import time

from app.core import security
from app.core.config import get_settings


def test_password_hash_roundtrip():
    h = security.hash_password("Pa55word!")
    assert h != "Pa55word!"
    assert h.startswith("$2")  # bcrypt prefix
    assert security.verify_password("Pa55word!", h) is True
    assert security.verify_password("wrong", h) is False
    assert security.verify_password("Pa55word!", None) is False
    assert security.verify_password("Pa55word!", "not-a-hash") is False


def test_session_token_roundtrip():
    token = security.create_session_token("11111111-2222-3333-4444-555555555555")
    assert isinstance(token, str) and token.count(".") == 2
    sub = security.decode_session_token(token)
    assert sub == "11111111-2222-3333-4444-555555555555"


def test_decode_rejects_garbage_and_empty():
    assert security.decode_session_token("") is None
    assert security.decode_session_token("not-a-jwt") is None


def test_decode_rejects_wrong_signature(monkeypatch):
    token = security.create_session_token("u1")
    # Re-sign with a different secret -> our decode must reject it.
    settings = get_settings()
    monkeypatch.setattr(settings, "JWT_SECRET", "different-secret-value")
    # Reset lru_cache so decode_session_token re-reads (we're patching the
    # cached object's attribute directly, which is enough).
    assert security.decode_session_token(token) is None


def test_token_carries_session_type_marker():
    import jwt as pyjwt

    settings = get_settings()
    bad = pyjwt.encode({"sub": "u1", "type": "refresh"}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)
    assert security.decode_session_token(bad) is None
