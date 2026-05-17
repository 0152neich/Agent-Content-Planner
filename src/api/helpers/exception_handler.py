from __future__ import annotations

from enum import Enum
from typing import Any

from shared.logging import redact_message


class ResponseMessage(str, Enum):
    INTERNAL_SERVER_ERROR = "Server might meet some errors. Please try again later !!!"
    SUCCESS = "Process successfully !!!"
    NOT_FOUND = "Resource not found !!!"
    BAD_REQUEST = "Invalid request !!!"
    UNPROCESSABLE_ENTITY = "Input is not allowed !!!"


_TECHNICAL_ERROR_MARKERS = (
    "traceback",
    "sqlalchemy",
    "psycopg",
    "exception",
    "stack",
    "openai",
    "connectionerror",
    "timeout",
    "object has no attribute",
    "no such file",
    "keyerror",
    "typeerror",
    "valueerror",
)


def _looks_like_technical_error(message: str) -> bool:
    lowered = message.lower()
    return any(marker in lowered for marker in _TECHNICAL_ERROR_MARKERS)


def _strip_validation_prefix(message: str) -> str:
    stripped = message.strip()
    lowered = stripped.lower()
    if lowered.startswith("value error,"):
        return stripped[len("Value error,") :].strip()
    return stripped


def to_validation_error_message(detail: Any) -> str:
    fallback = "Invalid input. Please check your data and try again."
    if not isinstance(detail, list):
        return fallback

    for item in detail:
        if not isinstance(item, dict):
            continue
        error_type = str(item.get("type") or "").lower()
        message = str(item.get("msg") or "").strip()
        message_lower = message.lower()

        if error_type == "missing":
            return "Please fill in all required fields."

        if (
            "url" in error_type
            or "valid url" in message_lower
            or "valid url" in str(item.get("input") or "").lower()
        ):
            return "Please enter a valid URL (including http:// or https://)."

        if "too_short" in error_type or "at least" in message_lower:
            return "One of the fields is too short. Please check and try again."

        if "too_long" in error_type or "at most" in message_lower:
            return "One of the fields is too long. Please shorten it and try again."

        if (
            "type" in error_type
            or "parsing" in error_type
            or "valid string" in message_lower
            or "valid integer" in message_lower
            or "input should be" in message_lower
        ):
            return (
                "One of the fields has an invalid format. Please check and try again."
            )

        cleaned_message = _strip_validation_prefix(message)
        if cleaned_message and not _looks_like_technical_error(cleaned_message):
            return cleaned_message

    return fallback


def to_http_detail_message(*, detail: Any, status_code: int) -> str:
    if status_code == 422:
        return to_validation_error_message(detail)

    fallback = "Request failed."
    if status_code == 401:
        fallback = "Unauthorized."
    elif status_code == 403:
        fallback = "You do not have permission to perform this action."
    elif status_code == 404:
        fallback = "The requested resource was not found."

    if isinstance(detail, str):
        return to_user_error_message(
            error=detail,
            status_code=status_code,
            fallback=fallback,
        )
    return to_user_error_message(error=None, status_code=status_code, fallback=fallback)


def to_user_error_message(
    *,
    error: str | None,
    status_code: int,
    fallback: str,
) -> str:
    if status_code >= 500:
        return "Something went wrong on our side. Please try again later."

    sanitized = redact_message((error or "").strip())
    if not sanitized:
        return fallback
    if _looks_like_technical_error(sanitized):
        return fallback
    return sanitized
