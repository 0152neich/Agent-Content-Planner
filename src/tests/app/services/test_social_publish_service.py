from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import requests

from app.services.social_publish_service import SocialPublishInput, SocialPublishService
from infra.database.pg.schemas import SocialConnection


class _FakeResponse:
    def __init__(
        self,
        *,
        status_code: int,
        payload: dict | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {}

    def json(self) -> dict:
        if self._payload is None:
            raise ValueError("No JSON payload")
        return self._payload


def _build_service(connection: SocialConnection | None) -> SocialPublishService:
    service = SocialPublishService.model_construct()
    object.__setattr__(service, "_timeout_seconds", 20)
    object.__setattr__(
        service,
        "_db",
        SimpleNamespace(
            get_session=lambda: _FakeContextManager(),
            get_social_connections=lambda **_kwargs: [connection]
            if connection
            else None,
        ),
    )
    object.__setattr__(
        service,
        "_cipher",
        SimpleNamespace(decrypt=lambda _value: "provider-access-token"),
    )
    return service


class _FakeContextManager:
    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


def _valid_connection(provider: str = "linkedin") -> SocialConnection:
    return SocialConnection(
        id="conn-1",
        user_id="user-1",
        provider=provider,
        access_token_encrypted="encrypted-token",
        refresh_token_encrypted=None,
        token_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        provider_account_id="urn:li:person:abc123"
        if provider == "linkedin"
        else "fb-user-1",
        provider_account_name="Jane Doe",
        revoked_at=None,
    )


def test_publish_linkedin_requires_connected_account() -> None:
    service = _build_service(connection=None)

    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="linkedin",
            content="LinkedIn content",
        )
    )

    assert result.status is False
    assert result.code == 400
    assert result.error_code == "SOCIAL_NOT_CONNECTED"


def test_publish_linkedin_success(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection())

    def _fake_post(url: str, **kwargs):
        assert url == "https://api.linkedin.com/v2/ugcPosts"
        assert kwargs["headers"]["Authorization"] == "Bearer provider-access-token"
        assert kwargs["json"]["author"] == "urn:li:person:abc123"
        return _FakeResponse(
            status_code=201,
            payload={"id": "urn:li:ugcPost:999999"},
        )

    monkeypatch.setattr(requests, "post", _fake_post)

    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="linkedin",
            content="LinkedIn content",
        )
    )

    assert result.status is True
    assert result.code == 200
    assert result.error_code is None
    assert result.data is not None
    assert result.data["platform"] == "linkedin"
    assert result.data["provider_post_id"] == "urn:li:ugcPost:999999"
    assert result.data["view_url"].endswith("/urn:li:ugcPost:999999/")


def test_publish_provider_token_error_returns_expired_code(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection())

    def _fake_post(_url: str, **_kwargs):
        return _FakeResponse(
            status_code=401,
            payload={"message": "Invalid access token"},
        )

    monkeypatch.setattr(requests, "post", _fake_post)

    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="linkedin",
            content="Publish me",
        )
    )

    assert result.status is False
    assert result.code == 401
    assert result.error_code == "SOCIAL_TOKEN_EXPIRED"


def test_publish_facebook_requires_page_id() -> None:
    service = _build_service(connection=_valid_connection(provider="facebook"))
    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="facebook",
            content="Hello",
            page_id="",
        )
    )
    assert result.status is False
    assert result.error_code == "SOCIAL_PAGE_ID_REQUIRED"


def test_publish_facebook_page_not_found(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection(provider="facebook"))

    def _fake_get(url: str, **kwargs):
        assert url.endswith("/me/accounts")
        assert kwargs["params"]["access_token"] == "provider-access-token"
        return _FakeResponse(status_code=200, payload={"data": []})

    monkeypatch.setattr(requests, "get", _fake_get)
    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="facebook",
            content="Hello",
            page_id="123",
        )
    )
    assert result.status is False
    assert result.error_code == "SOCIAL_PAGE_NOT_FOUND"


def test_publish_facebook_permission_denied(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection(provider="facebook"))

    def _fake_get(_url: str, **_kwargs):
        return _FakeResponse(
            status_code=200,
            payload={"data": [{"id": "123", "access_token": "page-token"}]},
        )

    def _fake_post(_url: str, **_kwargs):
        return _FakeResponse(
            status_code=400,
            payload={
                "error": {
                    "message": "Insufficient permission to post.",
                    "code": 200,
                }
            },
        )

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "post", _fake_post)

    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="facebook",
            content="Hello",
            page_id="123",
        )
    )
    assert result.status is False
    assert result.error_code == "SOCIAL_PAGE_PERMISSION_DENIED"


def test_publish_facebook_success(monkeypatch) -> None:
    service = _build_service(connection=_valid_connection(provider="facebook"))

    def _fake_get(_url: str, **_kwargs):
        return _FakeResponse(
            status_code=200,
            payload={
                "data": [
                    {
                        "id": "123",
                        "name": "Page",
                        "access_token": "page-token",
                        "tasks": ["CREATE_CONTENT"],
                        "perms": ["CREATE_CONTENT"],
                    }
                ]
            },
        )

    def _fake_post(url: str, **kwargs):
        assert url.endswith("/123/feed")
        assert kwargs["data"]["access_token"] == "page-token"
        return _FakeResponse(status_code=200, payload={"id": "123_999"})

    monkeypatch.setattr(requests, "get", _fake_get)
    monkeypatch.setattr(requests, "post", _fake_post)

    result = service.publish(
        SocialPublishInput(
            user_id="user-1",
            platform="facebook",
            content="Hello",
            page_id="123",
        )
    )
    assert result.status is True
    assert result.error_code is None
    assert result.data is not None
    assert result.data["platform"] == "facebook"
    assert result.data["provider_post_id"] == "123_999"
