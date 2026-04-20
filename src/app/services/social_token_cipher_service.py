from __future__ import annotations

import base64
import hashlib
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from shared.base import BaseModel
from shared.settings import Settings


class SocialTokenCipherService(BaseModel):
    def __init__(self, **data: Any) -> None:
        super().__init__(**data)
        self._settings = Settings()
        self._fernet: Fernet | None = None

    def _resolve_key(self) -> bytes:
        raw_key = self._settings.auth.social_token_encryption_key.strip()
        if not raw_key:
            raise ValueError("AUTH__SOCIAL_TOKEN_ENCRYPTION_KEY is not configured.")
        # Support both a Fernet key and a plain secret string.
        if len(raw_key) == 44:
            try:
                return raw_key.encode("utf-8")
            except Exception:
                pass
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        return base64.urlsafe_b64encode(digest)

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            self._fernet = Fernet(self._resolve_key())
        return self._fernet

    def encrypt(self, value: str) -> str:
        return self._get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        try:
            return self._get_fernet().decrypt(value.encode("utf-8")).decode("utf-8")
        except InvalidToken as exc:
            raise ValueError("Invalid encrypted social token payload.") from exc
