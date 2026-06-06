"""
Unified logging utility for Glimpse.

Provides a central logger factory with consistent formatting and log level control.
All modules should use `get_logger(__name__)` instead of `print()`.

Example:
    from utils.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.error("An error occurred", exc_info=True)
"""
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Default log format
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Global log level (can be overridden via environment variable)
DEFAULT_LOG_LEVEL = logging.INFO


def _get_log_level() -> int:
    """Get log level from environment variable or default."""
    level = os.environ.get("GLIMPSE_LOG_LEVEL", "INFO").upper()
    return getattr(logging, level, DEFAULT_LOG_LEVEL)


def setup_logging(
    log_level: Optional[int] = None,
    log_file: Optional[Path] = None,
    log_format: str = LOG_FORMAT,
    date_format: str = DATE_FORMAT,
) -> None:
    """
    Setup global logging configuration.

    Args:
        log_level: Logging level (default: INFO or from GLIMPSE_LOG_LEVEL env)
        log_file: Optional path to log file for file output
        log_format: Format string for log messages
        date_format: Format string for dates
    """
    if log_level is None:
        log_level = _get_log_level()

    # Remove existing handlers to avoid duplicates
    root = logging.getLogger()
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Configure root logger
    root.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(log_format, date_format)
    console_handler.setFormatter(console_formatter)
    root.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)  # File always gets DEBUG
        file_formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("pynput").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given module name.

    Args:
        name: Usually `__name__` from the calling module

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


# Auto-setup logging on import
setup_logging()
