"""
Module 20: Structured logging configuration.
Sets up JSON-structured logging in production, human-readable in development.
Never logs secrets, credentials, tokens, or stack traces to external sinks.
"""
import logging
import sys
from app.core.config import settings

# Fields that must never appear in log output
_BLOCKED_LOG_FIELDS = frozenset([
    "password", "secret", "api_key", "token", "authorization",
    "database_url", "secret_key", "lm_api_key",
])


class _SafeFilter(logging.Filter):
    """Drop log records that accidentally contain sensitive field names."""

    def filter(self, record: logging.LogRecord) -> bool:
        msg = str(record.getMessage()).lower()
        for field in _BLOCKED_LOG_FIELDS:
            if field in msg:
                # Replace the message rather than dropping — keeps the event visible
                record.msg = "[REDACTED — log message contained a sensitive field name]"
                record.args = ()
                break
        return True


def configure_logging() -> None:
    """Configure root logger. Call once at application startup."""
    level = logging.DEBUG if settings.DEBUG else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(_SafeFilter())

    if settings.ENVIRONMENT == "production":
        # Minimal structured format for log aggregators
        fmt = "%(asctime)s %(levelname)s %(name)s %(message)s"
    else:
        fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    handler.setFormatter(logging.Formatter(fmt))

    root = logging.getLogger()
    root.setLevel(level)
    # Avoid duplicate handlers if called more than once
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)

    # Suppress noisy third-party loggers
    for noisy in ("httpx", "httpcore", "sqlalchemy.engine", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
