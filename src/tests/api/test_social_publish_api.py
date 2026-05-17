from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from api.dependencies.auth import get_current_user
from app.services import AuthServiceOutput, SocialPublishServiceOutput
from infra.database.pg.schemas import User
from main import app

import api.routers.social_publish as social_publish_router_module


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


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


def test_social_publish_requires_auth(client: TestClient) -> None:
    response = client.post(
        "/api/v1/social/publish",
        json={"platform": "linkedin", "content": "Hello LinkedIn"},
    )

    assert response.status_code == 401
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert isinstance(payload["error"], str)


def test_social_publish_success_with_auth_override(
    client: TestClient, monkeypatch
) -> None:
    async def _auth_override() -> AuthServiceOutput:
        return AuthServiceOutput(
            status=True,
            data=_fake_user(),
            error=None,
            code=200,
        )

    class _FakeService:
        @staticmethod
        def publish(_inputs):
            return SocialPublishServiceOutput(
                status=True,
                data={
                    "platform": "linkedin",
                    "provider_post_id": "urn:li:ugcPost:12345",
                    "view_url": "https://www.linkedin.com/feed/update/urn:li:ugcPost:12345/",
                },
                error=None,
                error_code=None,
                code=200,
            )

    app.dependency_overrides[get_current_user] = _auth_override
    monkeypatch.setattr(
        social_publish_router_module, "_publish_service", _FakeService()
    )
    try:
        response = client.post(
            "/api/v1/social/publish",
            json={"platform": "linkedin", "content": "Hello LinkedIn"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["error"] is None
    assert payload["data"]["platform"] == "linkedin"
    assert payload["data"]["provider_post_id"] == "urn:li:ugcPost:12345"


def test_social_publish_service_error_keeps_envelope(
    client: TestClient, monkeypatch
) -> None:
    async def _auth_override() -> AuthServiceOutput:
        return AuthServiceOutput(
            status=True,
            data=_fake_user(),
            error=None,
            code=200,
        )

    class _FakeService:
        @staticmethod
        def publish(_inputs):
            return SocialPublishServiceOutput(
                status=False,
                data=None,
                error="Provider rejected this post.",
                error_code="SOCIAL_PROVIDER_ERROR",
                code=400,
            )

    app.dependency_overrides[get_current_user] = _auth_override
    monkeypatch.setattr(
        social_publish_router_module, "_publish_service", _FakeService()
    )
    try:
        response = client.post(
            "/api/v1/social/publish",
            json={"platform": "linkedin", "content": "Hello LinkedIn"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"] == "Provider rejected this post."
    assert payload["code"] == "SOCIAL_PROVIDER_ERROR"


def test_social_publish_facebook_requires_page_id(client: TestClient) -> None:
    response = client.post(
        "/api/v1/social/publish",
        json={"platform": "facebook", "content": "Hello Facebook"},
    )
    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert isinstance(payload["error"], str)


def test_social_publish_facebook_success(client: TestClient, monkeypatch) -> None:
    async def _auth_override() -> AuthServiceOutput:
        return AuthServiceOutput(
            status=True,
            data=_fake_user(),
            error=None,
            code=200,
        )

    class _FakeService:
        @staticmethod
        def publish(inputs):
            assert inputs.platform == "facebook"
            assert inputs.page_id == "123"
            return SocialPublishServiceOutput(
                status=True,
                data={
                    "platform": "facebook",
                    "provider_post_id": "123_456",
                    "view_url": "https://www.facebook.com/123_456",
                },
                error=None,
                error_code=None,
                code=200,
            )

    app.dependency_overrides[get_current_user] = _auth_override
    monkeypatch.setattr(
        social_publish_router_module, "_publish_service", _FakeService()
    )
    try:
        response = client.post(
            "/api/v1/social/publish",
            json={
                "platform": "facebook",
                "content": "Hello Facebook",
                "page_id": "123",
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["platform"] == "facebook"
    assert payload["data"]["provider_post_id"] == "123_456"


def test_facebook_pages_requires_auth(client: TestClient) -> None:
    response = client.get("/api/v1/social/facebook/pages")
    assert response.status_code == 401


def test_facebook_pages_success(client: TestClient, monkeypatch) -> None:
    async def _auth_override() -> AuthServiceOutput:
        return AuthServiceOutput(
            status=True,
            data=_fake_user(),
            error=None,
            code=200,
        )

    class _FakeFacebookService:
        @staticmethod
        def list_pages(_user):
            return type(
                "Result",
                (),
                {
                    "status": True,
                    "data": [
                        {
                            "id": "123",
                            "name": "Page 1",
                            "tasks": ["CREATE_CONTENT"],
                            "perms": ["CREATE_CONTENT"],
                        }
                    ],
                    "error": None,
                    "error_code": None,
                    "code": 200,
                },
            )()

    app.dependency_overrides[get_current_user] = _auth_override
    monkeypatch.setattr(
        social_publish_router_module,
        "_facebook_connection_service",
        _FakeFacebookService(),
    )
    try:
        response = client.get("/api/v1/social/facebook/pages")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"][0]["id"] == "123"
