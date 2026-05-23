from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient

import api.routers.conversation as conversation_router_module
from api.dependencies.auth import get_current_user
from api.helpers.exception_handler import to_user_error_message
from app.services import AuthServiceOutput, ConversationServiceOutput
from infra.database.pg.schemas import ConversationMessage, ConversationRun, User
from main import app


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


def _fake_message(*, message_id: str, role: str, content: str) -> ConversationMessage:
    return ConversationMessage(
        id=message_id,
        conversation_id="conv-1",
        role=role,
        content=content,
        model="gpt-5.4",
        input_tokens=12,
        output_tokens=34,
        latency_ms=123,
        error=None,
        createdAt=datetime.now(timezone.utc),
        updatedAt=None,
        deletedAt=None,
    )


def _fake_run() -> ConversationRun:
    now = datetime.now(timezone.utc)
    return ConversationRun(
        id="run-1",
        conversation_id="conv-1",
        project_id="proj-1",
        request_payload={"trigger": "chat", "selected_model": "gpt-5.4"},
        response_payload={"ok": True},
        status="completed",
        started_at=now,
        finished_at=now,
        source_url="https://example.com/article",
        platforms=["linkedin", "facebook"],
        createdAt=now,
        updatedAt=None,
        deletedAt=None,
    )


def _parse_sse_events(raw: str) -> list[tuple[str, dict[str, Any]]]:
    frames = raw.replace("\r\n", "\n").split("\n\n")
    events: list[tuple[str, dict[str, Any]]] = []

    for frame in frames:
        if not frame.strip():
            continue

        event_name = "message"
        data_lines: list[str] = []
        for raw_line in frame.split("\n"):
            line = raw_line.rstrip("\n")
            if not line or line.startswith(":"):
                continue

            if ":" in line:
                field, value = line.split(":", 1)
                value = value.lstrip(" ")
            else:
                field, value = line, ""

            if field == "event" and value:
                event_name = value
            elif field == "data":
                data_lines.append(value)

        if not data_lines:
            continue

        payload = json.loads("\n".join(data_lines))
        if isinstance(payload, dict):
            events.append((event_name, payload))

    return events


def _set_auth_override() -> None:
    async def _auth_override() -> AuthServiceOutput:
        return AuthServiceOutput(
            status=True,
            data=_fake_user(),
            error=None,
            code=200,
        )

    app.dependency_overrides[get_current_user] = _auth_override


def _patch_stream_executor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(conversation_router_module, "get_crew_executor", lambda: None)


def test_stream_returns_sse_content_type_and_done_event(
    client: TestClient, monkeypatch
) -> None:
    _set_auth_override()
    _patch_stream_executor(monkeypatch)

    class _FakeService:
        @staticmethod
        def create_message(_inputs):
            return ConversationServiceOutput(
                status=True,
                data={
                    "user_message": _fake_message(
                        message_id="msg-user-1",
                        role="user",
                        content="Please refine this campaign.",
                    ),
                    "assistant_message": _fake_message(
                        message_id="msg-assistant-1",
                        role="assistant",
                        content="Refined response content with enough text to stream.",
                    ),
                    "run": _fake_run(),
                    "intent": None,
                    "affected_sections": ["analysis"],
                    "content_plan_snapshot": {"analysis": {"core_message": "updated"}},
                },
                error=None,
                code=200,
            )

    monkeypatch.setattr(conversation_router_module, "_service", _FakeService())
    try:
        response = client.post(
            "/api/v1/conversations/conv-1/messages/stream",
            json={"content": "Please refine this campaign."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert response.headers.get("cache-control") == "no-cache"
    assert response.headers.get("x-accel-buffering") == "no"
    assert response.headers.get("connection") == "keep-alive"

    events = _parse_sse_events(response.text)
    assert events
    assert any(
        name == "status" and payload.get("status") == "started"
        for name, payload in events
    )

    done_events = [payload for name, payload in events if name == "done"]
    assert done_events
    done_payload = done_events[-1]
    assert "run" in done_payload
    assert done_payload.get("assistant_message", {}).get("id") == "msg-assistant-1"


def test_stream_service_failure_emits_error_event(
    client: TestClient, monkeypatch
) -> None:
    _set_auth_override()
    _patch_stream_executor(monkeypatch)

    class _FakeService:
        @staticmethod
        def create_message(_inputs):
            return ConversationServiceOutput(
                status=False,
                data=None,
                error="Create message failed: timeout from upstream.",
                code=503,
            )

    monkeypatch.setattr(conversation_router_module, "_service", _FakeService())
    try:
        response = client.post(
            "/api/v1/conversations/conv-1/messages/stream",
            json={"content": "Retry this prompt."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events

    error_events = [payload for name, payload in events if name == "error"]
    assert error_events
    expected_error = to_user_error_message(
        error="Create message failed: timeout from upstream.",
        status_code=503,
        fallback="Create message failed.",
    )
    assert error_events[-1]["error"] == expected_error
    assert error_events[-1]["code"] == 503


def test_stream_unhandled_exception_emits_error_event_and_finishes(
    client: TestClient, monkeypatch
) -> None:
    _set_auth_override()
    _patch_stream_executor(monkeypatch)

    class _FakeService:
        @staticmethod
        def create_message(_inputs):
            raise RuntimeError("boom")

    monkeypatch.setattr(conversation_router_module, "_service", _FakeService())
    try:
        response = client.post(
            "/api/v1/conversations/conv-1/messages/stream",
            json={"content": "Cause exception."},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    events = _parse_sse_events(response.text)
    assert events
    assert all(name != "done" for name, _ in events)

    error_events = [payload for name, payload in events if name == "error"]
    assert error_events
    assert error_events[-1]["error"] == "Unexpected error while creating message."
    assert error_events[-1]["code"] == 500


def test_chunk_text_preserves_leading_spaces_in_stream_delta() -> None:
    chunks = conversation_router_module._chunk_text(" hello  world\nnext")
    assert chunks == [" ", "hello  ", "world\n", "next"]
