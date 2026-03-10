from __future__ import annotations

import logging
import sys

import structlog
from structlog.typing import BoundLogger


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
        processors=shared_processors + [
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