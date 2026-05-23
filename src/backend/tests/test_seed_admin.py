from app.core.security import verify_password
from app.models.user import User
from app.seeders.seed_admin import build_admin_registration, ensure_admin_user


class _Query:
    def __init__(self, user):
        self.user = user

    def filter(self, *_args, **_kwargs):
        return self

    def first(self):
        return self.user


class _Db:
    def __init__(self, user=None):
        self.user = user
        self.added = None

    def query(self, _model):
        return _Query(self.user)

    def add(self, user):
        self.added = user


def test_admin_registration_uses_normal_validation_and_defaults():
    payload = build_admin_registration(" ADMIN@Example.COM ", "valid-password")

    assert payload.email == "admin@example.com"
    assert payload.display_name == "Admin"
    assert payload.cefr_level == "B1"
    assert payload.industry == "admin"
    assert payload.learning_goals == ["administration"]


def test_ensure_admin_user_creates_admin_with_hashed_password():
    db = _Db()

    status, user = ensure_admin_user(db, "admin@example.com", "valid-password")

    assert status == "created"
    assert db.added is user
    assert user.email == "admin@example.com"
    assert user.role == "admin"
    assert user.password_hash != "valid-password"
    assert verify_password("valid-password", user.password_hash)


def test_ensure_admin_user_promotes_existing_user_and_syncs_password():
    user = User(
        email="admin@example.com",
        password_hash="not-a-valid-hash",
        cefr_level="A2",
        industry="sales",
        learning_goals=["speaking"],
        role="user",
    )
    db = _Db(user=user)

    status, updated = ensure_admin_user(db, "admin@example.com", "valid-password")

    assert status == "updated"
    assert updated is user
    assert user.role == "admin"
    assert verify_password("valid-password", user.password_hash)
