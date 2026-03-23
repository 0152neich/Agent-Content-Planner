from __future__ import annotations

import asyncio
from functools import partial

from fastapi import Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.services import AuthService, AuthServiceOutput, ValidateAccessTokenInput

_service = AuthService()
_bearer_scheme = HTTPBearer(
    auto_error=False,
    scheme_name="BearerAuth",
    description="Paste JWT access token here.",
)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_scheme),
) -> AuthServiceOutput:
    if not credentials or not credentials.credentials:
        return AuthServiceOutput(
            status=False, data=None, error="Missing authorization token.", code=401
        )

    if (credentials.scheme or "").lower() != "bearer":
        return AuthServiceOutput(
            status=False, data=None, error="Invalid authorization scheme.", code=401
        )
    token = credentials.credentials.strip()
    if not token:
        return AuthServiceOutput(
            status=False, data=None, error="Missing authorization token.", code=401
        )

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(
            _service.validate_access_token, ValidateAccessTokenInput(access_token=token)
        ),
    )
