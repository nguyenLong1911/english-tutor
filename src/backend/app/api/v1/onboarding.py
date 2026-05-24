from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...core.database import get_db
from ...core.security import create_session_token
from ...models.processed_dataset_schemas import OnboardingCreate, UserOut
from ...models.user import User
from ...services.personalization import seed_onboarding_memory


router = APIRouter(tags=["onboarding"])


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


def _create_user(db: Session, payload: OnboardingCreate) -> User:
    user = User(
        cefr_level=payload.cefr_level,
        industry=payload.industry,
        learning_goals=payload.learning_goals,
        preferred_study_time=payload.preferred_study_time,
        email=payload.email,
        display_name=payload.display_name,
    )
    db.add(user)
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already registered")
    db.refresh(user)
    return user


@router.post("/onboarding", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def complete_onboarding(
    payload: OnboardingCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> User:
    user = _create_user(db, payload)
    seed_onboarding_memory(
        str(user.user_id),
        cefr_level=user.cefr_level,
        industry=user.industry,
        learning_goals=list(user.learning_goals or []),
        db=db,
    )
    _set_session_cookie(response, str(user.user_id))
    return user


@router.post("/onboarding/demo", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_demo_user(response: Response, db: Session = Depends(get_db)) -> User:
    demo_payload = OnboardingCreate(
        email=None,
        display_name="Demo Learner",
        cefr_level="B1",
        industry="marketing",
        learning_goals=["Giao tiếp công việc", "Viết email chuyên nghiệp"],
    )
    user = _create_user(db, demo_payload)
    seed_onboarding_memory(
        str(user.user_id),
        cefr_level=user.cefr_level,
        industry=user.industry,
        learning_goals=list(user.learning_goals or []),
        db=db,
    )
    # Demo accounts also get a session cookie so the SPA's /auth/me-based
    # ProtectedRoute keeps working. They simply have no password set and
    # cannot log in via /auth/login until the user upgrades them.
    _set_session_cookie(response, str(user.user_id))
    return user


@router.get("/user/{user_id}", response_model=UserOut)
def get_user(user_id: UUID, db: Session = Depends(get_db)) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user
