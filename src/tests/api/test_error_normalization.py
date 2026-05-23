from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from api.models.conversation import ConversationMessageAPIData, ConversationRunAPIData
from app.services.conversation_service import ConversationService
from main import app

_TEST_BOOM_ROUTE = "/api/v1/__test__/boom"

if not any(getattr(route, "path", None) == _TEST_BOOM_ROUTE for route in app.routes):

    @app.get(_TEST_BOOM_ROUTE)
    async def _test_boom() -> dict[str, bool]:
        raise RuntimeError("SQLAlchemy timeout with traceback details")


@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


def test_422_invalid_url_is_user_friendly(client: TestClient) -> None:
    response = client.post("/api/v1/content-plan", json={"url": "a"})

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert (
        payload["error"] == "Please enter a valid URL (including http:// or https://)."
    )
    assert "detail" not in payload


def test_422_missing_fields_uses_short_message(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={})

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert payload["error"] == "Please fill in all required fields."
    assert "detail" not in payload


def test_422_model_validator_message_is_cleaned(client: TestClient) -> None:
    response = client.post(
        "/api/v1/content-plan",
        json={"url": "https://example.com/post", "project_id": "project_1"},
    )

    assert response.status_code == 422
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert (
        "project_id and conversation_id must be provided together." in payload["error"]
    )
    assert "Value error" not in payload["error"]


def test_500_is_generic_and_safe(client: TestClient) -> None:
    response = client.get(_TEST_BOOM_ROUTE)

    assert response.status_code == 500
    payload = response.json()
    assert payload["success"] is False
    assert payload["data"] is None
    assert (
        payload["error"] == "Something went wrong on our side. Please try again later."
    )
    assert "traceback" not in payload["error"].lower()
    assert "sqlalchemy" not in payload["error"].lower()


def test_conversation_failure_text_is_sanitized() -> None:
    technical_text = ConversationService._build_assistant_failure_text(
        "OpenAI APIConnectionError timeout while requesting model.",
        500,
    )
    assert (
        technical_text
        == "I could not complete this request right now. Please try again."
    )

    business_text = ConversationService._build_assistant_failure_text(
        "No content snapshot found for this project yet.",
        409,
    )
    assert "No content snapshot found for this project yet." in business_text


def test_history_payload_error_is_sanitized_for_output() -> None:
    run = SimpleNamespace(
        id="run_1",
        conversation_id="conv_1",
        project_id="proj_1",
        status="failed",
        started_at=datetime.now(timezone.utc),
        finished_at=None,
        source_url=None,
        platforms=[],
        request_payload={},
        response_payload={"error": "SQLAlchemy timeout traceback details"},
        createdAt=None,
    )
    data = ConversationRunAPIData.from_domain(run)  # type: ignore[arg-type]
    assert (
        data.response_payload["error"]
        == "I could not complete this request. Please try again."
    )

    message = SimpleNamespace(
        id="msg_1",
        conversation_id="conv_1",
        role="assistant",
        content="text",
        model="gpt-5.4",
        input_tokens=None,
        output_tokens=10,
        latency_ms=50,
        error="OpenAI APIConnectionError timeout",
        createdAt=None,
    )
    msg_data = ConversationMessageAPIData.from_domain(message)  # type: ignore[arg-type]
    assert msg_data.error == "I could not complete this request. Please try again."
