from __future__ import annotations


class GoogleAuthError(Exception):
    def __init__(self, message: str, *, code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
