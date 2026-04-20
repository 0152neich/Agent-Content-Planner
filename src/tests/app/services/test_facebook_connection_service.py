from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests

from app.services.facebook_connection_service import (
    FacebookConnectionService,
    FacebookOAuthCallbackInput,
)
from infra.database.pg.schemas import SocialConnection, User


class _FakeContextManager:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeResponse:
    def __init__(self, *, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


def _fake_user() -> User:
    return User(
        id="user-1",
        user_name="tester",
        email="tester@example.com",
        password_hash=None,
        full_name="Tester",
        phone=None,
        avatar_url=None,
        is_active=True,
        email_verified=True,
        role="user",
        createdAt=datetime.now(timezone.utc),
        updatedAt=None,
        deletedAt=None,
    )


def _build_service(
    connection: SocialConnection | None = None,
) -> FacebookConnectionService:
    service = FacebookConnectionService.model_construct()
    settings = SimpleNamespace(
        auth=SimpleNamespace(
            facebook_enabled=True,
            facebook_client_id="fb-client",
            facebook_client_secret="fb-secret",
            facebook_redirect_uri="http://localhost:8000/api/v1/social/facebook/callback",
            facebook_scope="pages_show_list pages_read_engagement pages_manage_posts",
            facebook_state_ttl_seconds=300,
            jwt_secret_key="jwt-secret",
            jwt_algorithm="HS256",
        )
    )
    object.__setattr__(service, "_settings", settings)
    object.__setattr__(
        service,
        "_db",
        SimpleNamespace(
            get_session=lambda: _FakeContextManager(),
            get_social_connections=lambda **_kwargs: [connection]
            if connection
            else None,
            insert_social_connection=lambda **_kwargs: _kwargs["model"],
            update_social_connection=lambda **_kwargs: _kwargs["model"],
        ),
    )
    object.__setattr__(
        service,
        "_cipher",
        SimpleNamespace(
            encrypt=lambda v: f"enc:{v}", decrypt=lambda v: "fb-access-token"
        ),
    )
    return service


def _valid_connection() -> SocialConnection:
    return SocialConnection(
        id="conn-1",
        user_id="user-1",
        provider="facebook",
        access_token_encrypted="enc:token",
        refresh_token_encrypted=None,
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        provider_account_id="fb-user",
        provider_account_name="FB User",
        revoked_at=None,
    )


def test_build_connect_url_success() -> None:
    service = _build_service()
    result = service.build_connect_url(_fake_user(), return_to="/profile")
    assert result.status is True
    assert isinstance(result.data, dict)
    assert "facebook.com" in str(result.data.get("authorize_url"))


def test_handle_callback_success(monkeypatch) -> None:
    service = _build_service()
    state = service._encode_state(user_id="user-1", return_to="/profile")

    def _fake_get(url: str, **_kwargs):
        if "oauth/access_token" in url:
            return _FakeResponse(
                status_code=200,
                payload={"access_token": "fb-access-token", "expires_in": 3600},
            )
        return _FakeResponse(
            status_code=200, payload={"id": "fb-user", "name": "FB User"}
        )

    monkeypatch.setattr(requests, "get", _fake_get)
    result = service.handle_callback(
        FacebookOAuthCallbackInput(code="code-1", state=state)
    )
    assert result.status is True
    assert isinstance(result.data, dict)
    assert result.data["provider"] == "facebook"


def test_handle_callback_invalid_state() -> None:
    service = _build_service()
    result = service.handle_callback(
        FacebookOAuthCallbackInput(code="code-1", state="invalid-state")
    )
    assert result.status is False
    assert result.error_code == "SOCIAL_INVALID_STATE"


def test_list_pages_success(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection())

    def _fake_get(url: str, **_kwargs):
        assert url.endswith("/me/accounts")
        return _FakeResponse(
            status_code=200,
            payload={
                "data": [
                    {
                        "id": "123",
                        "name": "Page 1",
                        "tasks": ["CREATE_CONTENT"],
                        "perms": ["CREATE_CONTENT"],
                        "access_token": "page-token",
                    }
                ]
            },
        )

    monkeypatch.setattr(requests, "get", _fake_get)
    result = service.list_pages(_fake_user())
    assert result.status is True
    assert isinstance(result.data, list)
    assert result.data[0]["id"] == "123"
