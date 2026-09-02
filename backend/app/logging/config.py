"""
app/logging/config.py

Centralized logging configuration for SalesCompass AI.

Usage:
    from app.logging.config import get_logger
    logger = get_logger(__name__)

Reads LOG_LEVEL from environment (default: INFO).
Safe defaults: does not log passwords, tokens, or secrets.
"""

import logging
import os
import sys


def _build_formatter() -> logging.Formatter:
    """Return a log formatter with timestamp, level, module, and message."""
    return logging.Formatter(
        fmt="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


def configure_logging() -> None:
    """
    Configure the root logger once for the entire application.

    Should be called exactly once, at application startup (main.py).
    Subsequent calls are safe but are no-ops (handler already attached).
    """
    root = logging.getLogger()

    # Only configure once
    if root.handlers:
        return

    level_name: str = os.getenv("LOG_LEVEL", "INFO").upper()
    level: int = getattr(logging, level_name, logging.INFO)

    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(_build_formatter())

    root.addHandler(handler)

    # Silence noisy third-party loggers that are not useful in production
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Return a named logger.

    Args:
        name: Typically ``__name__`` of the calling module.

    Returns:
        A configured Logger instance.
    """
    return logging.getLogger(name)
