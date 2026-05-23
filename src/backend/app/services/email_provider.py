"""Email provider abstraction.

Primary: Resend (https://resend.com) — free tier 100 emails/day. Falls back
to logging the payload when `RESEND_API_KEY` is blank so dev/tests don't
require external credentials.
"""
from __future__ import annotations

import logging
from typing import Any

import requests

from ..core.config import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(RuntimeError):
    pass


def send_email(*, to: str, subject: str, html: str, text: str | None = None) -> dict[str, Any]:
    """Send a single transactional email. Returns provider response or a stub dict.

    Raises `EmailSendError` on 4xx/5xx when a provider key is configured; in
    blank-key (dev) mode it just logs and returns ``{"status": "stubbed"}``.
    """
    settings = get_settings()

    if not settings.RESEND_API_KEY:
        logger.info("[email:stub] to=%s subject=%r (RESEND_API_KEY not set)", to, subject)
        return {"status": "stubbed", "to": to, "subject": subject}

    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "html": html,
                **({"text": text} if text else {}),
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        raise EmailSendError(f"network error: {exc}") from exc

    if response.status_code >= 400:
        raise EmailSendError(f"resend {response.status_code}: {response.text[:500]}")

    return response.json()
