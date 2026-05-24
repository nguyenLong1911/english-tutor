"""Google OAuth 2.0 sign-in.

Flow (matches the user's Google Cloud Console config where the registered
authorized redirect URI is the SPA root: ``http://localhost:5173``):

1. Browser hits ``GET /api/v1/auth/google/start`` → 302 redirect to Google
   with ``redirect_uri = settings.GOOGLE_REDIRECT_URI`` and a CSRF
   ``state`` value persisted in a short-lived httpOnly cookie.
2. User consents on Google → Google redirects the browser back to the SPA
   root with ``?code=...&state=...``.
3. The SPA's HomePage detects those params and POSTs them to
   ``POST /api/v1/auth/google/callback``. We verify state, exchange the
   code for an access token, fetch the user's email/profile, find or
   create the user, set the regular ``a20_session`` cookie, and return
   ``UserOut`` so the SPA can route to /chat.
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import create_session_token
from ...models.processed_dataset_schemas import UserOut
from ...models.user import User


router = APIRouter(prefix="/auth/google", tags=["auth"])
logger = logging.getLogger(__name__)

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"

OAUTH_STATE_COOKIE = "a20_oauth_state"
OAUTH_STATE_TTL = 600  # 10 minutes


class GoogleCallbackBody(BaseModel):
    code: str
    state: str


def _set_session_cookie(response: Response, user_id: str) -> None:
    settings = get_settings()
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=create_session_token(user_id),
        max_age=settings.JWT_TTL_DAYS * 24 * 3600,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


@router.get("/start")
def google_start() -> RedirectResponse:
    settings = get_settings()
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_REDIRECT_URI):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the server",
        )

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "access_type": "online",
        "prompt": "select_account",
        "include_granted_scopes": "true",
    }
    response = RedirectResponse(
        url=f"{GOOGLE_AUTH_URL}?{urlencode(params)}",
        status_code=status.HTTP_302_FOUND,
    )
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=state,
        max_age=OAUTH_STATE_TTL,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    return response


@router.post("/callback", response_model=UserOut)
async def google_callback(
    body: GoogleCallbackBody,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    settings = get_settings()
    if not (settings.GOOGLE_CLIENT_ID and settings.GOOGLE_CLIENT_SECRET and settings.GOOGLE_REDIRECT_URI):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google OAuth is not configured on the server",
        )

    expected_state = request.cookies.get(OAUTH_STATE_COOKIE)
    if not expected_state or not secrets.compare_digest(expected_state, body.state):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid oauth state")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            token_resp = await client.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": body.code,
                    "client_id": settings.GOOGLE_CLIENT_ID,
                    "client_secret": settings.GOOGLE_CLIENT_SECRET,
                    "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
                headers={"Accept": "application/json"},
            )
            if token_resp.status_code != 200:
                logger.warning("google token exchange failed: %s %s", token_resp.status_code, token_resp.text[:300])
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="token exchange failed")
            access_token = token_resp.json().get("access_token")
            if not access_token:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="no access_token from google")

            ui_resp = await client.get(
                GOOGLE_USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if ui_resp.status_code != 200:
                logger.warning("google userinfo failed: %s %s", ui_resp.status_code, ui_resp.text[:300])
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="userinfo failed")
            userinfo = ui_resp.json()
    except httpx.HTTPError as e:
        logger.exception("google oauth network error")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="google oauth unavailable") from e

    email = (userinfo.get("email") or "").strip().lower()
    if not email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="google account has no email")
    if userinfo.get("email_verified") is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="email not verified by google")
    display_name = userinfo.get("name") or userinfo.get("given_name")

    user = db.query(User).filter(User.email == email).first()
    if user is None:
        # New Google user — seed a minimal profile so cefr_level / industry
        # NOT-NULL constraints are satisfied. The user can refine these in
        # Settings or by re-running the onboarding wizard.
        user = User(
            email=email,
            display_name=display_name,
            cefr_level="A2",
            industry="general",
            learning_goals=[],
            password_hash=None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        logger.info("auth.google.signup email=%s user_id=%s", email, user.user_id)
    else:
        # Existing user: keep their profile, just refresh display_name if empty
        if not user.display_name and display_name:
            user.display_name = display_name
            user.agent_opening_message = None
            db.commit()
            db.refresh(user)
        logger.info("auth.google.signin email=%s user_id=%s", email, user.user_id)

    _set_session_cookie(response, str(user.user_id))
    # one-shot state cookie — burn after use
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        path="/",
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        httponly=True,
    )
    return user
