from __future__ import annotations


class UnsupportedModelError(ValueError):
    """Raised when selected model is invalid or unsupported by current provider."""
