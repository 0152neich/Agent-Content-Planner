from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace

from app.services.auth_service import (
    AuthService,
    LoginInput,
    RefreshInput,
    ValidateAccessTokenInput,
)
from infra.database.pg.schemas import RefreshToken, User


class FakeDB:
    def __init__(self, user: User | None) -> None:
        self._user = user
        self.refresh_tokens: dict[str, RefreshToken] = {}

    @contextmanager
    def get_session(self):
        yield self

    def get_users(self, session, filter=None, order_by=None, limit=None):  # noqa: A002
        if self._user is None:
            return None
        if filter is None:
            return [self._user]
        if "email" in filter and self._user.email == filter["email"]:
            return [self._user]
        if "user_name" in filter and self._user.user_name == filter["user_name"]:
            return [self._user]
        return None

    def get_user_by_id(self, session, id: str):  # noqa: A002
        if self._user is None:
            return None
        return self._user if self._user.id == id else None

    def insert_refresh_token(self, session, model: RefreshToken) -> RefreshToken:
        self.refresh_tokens[str(model.id)] = model
        return model

    def get_refresh_token_by_id(self, session, id: str):  # noqa: A002
        return self.refresh_tokens.get(id)

    def get_refresh_tokens(self, session, filter=None, order_by=None, limit=None):  # noqa: A002
        rows = list(self.refresh_tokens.values())
        if filter and "user_id" in filter:
            rows = [row for row in rows if row.user_id == filter["user_id"]]
        return rows or None

    def update_refresh_token(self, session, model: RefreshToken):
        self.refresh_tokens[str(model.id)] = model
        return model


def _build_service_with_fake_db(
    *, is_active: bool = True, has_user: bool = True
) -> tuple[AuthService, FakeDB]:
    user = None
    if has_user:
        user = User(
            id="u-1",
            user_name="alice",
            email="alice@example.com",
            password_hash=AuthService.hash_password("VeryStrongPassword@123"),
            is_active=is_active,
            email_verified=True,
            role="user",
            full_name="Alice",
            phone=None,
            avatar_url=None,
            createdAt=datetime.now(timezone.utc),
            updatedAt=None,
            deletedAt=None,
        )

    fake_db = FakeDB(user=user)
    service = AuthService.model_construct()
    object.__setattr__(
        service,
        "_settings",
        SimpleNamespace(
            auth=SimpleNamespace(
                jwt_secret_key="unit-test-secret",
                jwt_algorithm="HS256",
                access_token_ttl_minutes=15,
                refresh_token_ttl_days=30,
                refresh_cookie_name="refresh_token",
                refresh_cookie_path="/api/v1/auth",
                refresh_cookie_samesite="strict",
                refresh_cookie_secure=True,
            )
        ),
    )
    object.__setattr__(service, "_db", fake_db)
    return service, fake_db


def test_login_success_returns_access_and_refresh_tokens() -> None:
    service, fake_db = _build_service_with_fake_db()

    result = service.login(
        LoginInput(identifier="alice@example.com", password="VeryStrongPassword@123")
    )

    assert result.status is True
    assert result.code == 200
    assert result.data is not None
    assert "access_token" in result.data
    assert "refresh_token" in result.data
    assert len(fake_db.refresh_tokens) == 1
    token_row = next(iter(fake_db.refresh_tokens.values()))
    assert token_row.token_hash != result.data["refresh_token"]


def test_login_invalid_credentials_returns_401() -> None:
    service, _ = _build_service_with_fake_db()

    result = service.login(
        LoginInput(identifier="alice@example.com", password="wrong-password")
    )

    assert result.status is False
    assert result.code == 401
    assert result.error == "username or password is invalid"


def test_login_inactive_user_returns_423() -> None:
    service, _ = _build_service_with_fake_db(is_active=False)

    result = service.login(
        LoginInput(identifier="alice@example.com", password="VeryStrongPassword@123")
    )

    assert result.status is False
    assert result.code == 423


def test_refresh_rotates_token_and_revokes_previous_token() -> None:
    service, fake_db = _build_service_with_fake_db()
    login_result = service.login(
        LoginInput(identifier="alice@example.com", password="VeryStrongPassword@123")
    )
    assert login_result.data is not None
    old_refresh_token = login_result.data["refresh_token"]

    refresh_result = service.refresh(RefreshInput(refresh_token=old_refresh_token))

    assert refresh_result.status is True
    assert refresh_result.code == 200
    assert refresh_result.data is not None
    assert refresh_result.data["refresh_token"] != old_refresh_token
    assert len(fake_db.refresh_tokens) == 2
    old_row = next(
        row
        for row in fake_db.refresh_tokens.values()
        if row.token_hash == service._hash_refresh_token(old_refresh_token)
    )
    assert old_row.revoked_at is not None
    assert old_row.replaced_by_jti is not None


def test_refresh_reuse_detection_revokes_active_tokens() -> None:
    service, fake_db = _build_service_with_fake_db()
    login_result = service.login(
        LoginInput(identifier="alice@example.com", password="VeryStrongPassword@123")
    )
    assert login_result.data is not None
    old_refresh_token = login_result.data["refresh_token"]
    _ = service.refresh(RefreshInput(refresh_token=old_refresh_token))

    reused_result = service.refresh(RefreshInput(refresh_token=old_refresh_token))

    assert reused_result.status is False
    assert reused_result.code == 401
    rows = list(fake_db.refresh_tokens.values())
    assert all(row.revoked_at is not None for row in rows)


def test_validate_access_token_invalid_returns_401() -> None:
    service, _ = _build_service_with_fake_db()

    result = service.validate_access_token(
        ValidateAccessTokenInput(access_token="invalid-token")
    )

    assert result.status is False
    assert result.code == 401
