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
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Default log format
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s] [session:%(sessionId)s] - %(message)s"
DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"

# Global log level (can be overridden via environment variable)
DEFAULT_LOG_LEVEL = logging.INFO
MAX_LOG_BYTES = 2 * 1024 * 1024
LOG_BACKUP_COUNT = 3


def redact_text(value: str) -> str:
    value = re.sub(r'(?i)\bBearer\s+[^\s\"\'<>]+', 'Bearer <redacted>', value)
    value = re.sub(r'//[^\s/@]+@', '//<redacted>@', value)
    value = re.sub(
        r'(?i)(\b(?:api[_-]?key|secret(?:[_-]?key)?|password|authorization|access[_-]?token|auth[_-]?token|token|signature)[\"\']?\s*[=:]\s*[\"\']?)[^\s&\"\'<> ,}]+',
        r'\1<redacted>', value,
    )
    return value


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


class SessionIdFilter(logging.Filter):
    """Attach the host-provided session id to every backend log record."""

    def __init__(self, session_id: str):
        super().__init__()
        self.session_id = session_id or "-"

    def filter(self, record: logging.LogRecord) -> bool:
        record.sessionId = self.session_id
        return True


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
    session_filter = SessionIdFilter(os.environ.get("GLIMPSE_SESSION_ID", ""))

    # A configured file is the single sink for structured Python logs. Raw
    # sidecar stdout/stderr is captured separately by the Tauri host.
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=MAX_LOG_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)  # File always gets DEBUG
        file_handler.addFilter(session_filter)
        file_formatter = RedactingFormatter(log_format, date_format)
        file_handler.setFormatter(file_formatter)
        root.addHandler(file_handler)
    else:
        console_stream = sys.stdout if sys.stdout is not None else sys.stderr
        if console_stream is not None:
            console_handler = logging.StreamHandler(console_stream)
            console_handler.setLevel(log_level)
            console_handler.addFilter(session_filter)
            console_formatter = RedactingFormatter(log_format, date_format)
            console_handler.setFormatter(console_formatter)
            root.addHandler(console_handler)

    if not root.handlers:
        root.addHandler(logging.NullHandler())

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)


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
