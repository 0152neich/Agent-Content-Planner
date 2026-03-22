from __future__ import annotations

import logging
import re
import sys

import structlog
from structlog.stdlib import BoundLogger

# Patterns that match API keys / secrets (redact entire match)
_SECRET_PATTERNS = [
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"AIza[a-zA-Z0-9_-]{30,}", re.IGNORECASE),
    re.compile(r"api_key=['\"][^'\"]+['\"]", re.IGNORECASE),
]


def _redact_string(s: str) -> str:
    out = s
    for pat in _SECRET_PATTERNS:
        out = pat.sub("***REDACTED***", out)
    return out


def redact_message(msg: str) -> str:
    """Redact API keys and secrets from a string (e.g. error messages). Safe to use in logs or API responses."""
    return _redact_string(msg)


def _redact_event_dict(
    logger: logging.Logger, method_name: str, event_dict: dict
) -> dict:
    """Structlog processor: redact secret-like values in event dict (in-place)."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = _redact_string(value)
    return event_dict


def redact_secrets(logger: logging.Logger, method_name: str, event_dict: dict) -> dict:
    """Structlog processor to prevent API keys and secrets from appearing in logs."""
    return _redact_event_dict(logger, method_name, event_dict)


def setup_logging(is_production: bool = False) -> None:
    """
    Configures structlog for the application.
    Uses JSON rendering for production, and colorful ConsoleRender for dev.
    """
    # Shared processors for both structlog and standard logging
    shared_processors = [
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        redact_secrets,
    ]

    # Clear existing handlers to prevent duplicates
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set base logging level
    root_logger.setLevel(logging.INFO)

    console_handler = logging.StreamHandler(sys.stdout)

    if is_production:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(colors=True),
            foreign_pre_chain=shared_processors,
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Quiet overly verbose third-party loggers if necessary
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> BoundLogger:
    """Get a logger with the given name

    Args:
        name (str): The name of the logger

    Returns:
        BoundLogger: The logger
    """
    return structlog.stdlib.get_logger(name)
