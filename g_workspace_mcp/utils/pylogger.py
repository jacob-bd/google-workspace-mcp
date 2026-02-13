"""Structured logger utility for the Google Workspace MCP server."""

import logging
import sys
from typing import Any, Dict, Set

import structlog

# HTTP clients
HTTP_CLIENT_LOGGERS = {
    "urllib3",
    "urllib3.connectionpool",
    "urllib3.util",
    "urllib3.util.retry",
    "requests",
    "httpx",
}

# Google API
GOOGLE_LOGGERS = {
    "google",
    "google.auth",
    "google.auth.transport",
    "googleapiclient",
    "googleapiclient.discovery",
    "googleapiclient.http",
}

# MCP (custom platform)
MCP_LOGGERS = {
    "fastmcp",
    "fastmcp.server",
    "fastmcp.server.http",
    "fastmcp.utilities",
    "fastmcp.utilities.logging",
    "fastmcp.client",
    "fastmcp.transports",
}

# --- Aggregated Sets ---

THIRD_PARTY_LOGGERS: Set[str] = HTTP_CLIENT_LOGGERS | GOOGLE_LOGGERS | MCP_LOGGERS

ERROR_ONLY_LOGGERS: Set[str] = GOOGLE_LOGGERS

_LOGGING_CONFIGURED = False


# --- Internal helpers ---


def _clear_handlers(logger: logging.Logger) -> None:
    logger.handlers.clear()
    logger.filters.clear()


def _setup_logger(logger_name: str, level: str) -> None:
    logger = logging.getLogger(logger_name)
    _clear_handlers(logger)
    logger.setLevel(logging.ERROR if logger_name in ERROR_ONLY_LOGGERS else level)
    logger.propagate = True


def _configure_third_party_loggers(log_level: str) -> None:
    """Apply structured logging to selected third-party loggers."""
    logging.getLogger().handlers.clear()

    for name in THIRD_PARTY_LOGGERS:
        _setup_logger(name, log_level)


# --- Public API ---



def get_python_logger(log_level: str = "INFO") -> structlog.BoundLogger:
    """Get a configured structlog logger."""
    global _LOGGING_CONFIGURED
    log_level = log_level.upper()

    if not _LOGGING_CONFIGURED:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stderr,
            level=log_level,
        )

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        _LOGGING_CONFIGURED = True

    _configure_third_party_loggers(log_level)
    return structlog.get_logger()


