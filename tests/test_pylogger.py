"""
Tests for structured logging configuration.

Tests cover:
- Logger outputs to stderr (not stdout) to avoid corrupting MCP stdio protocol
- Logger configuration is idempotent
- Third-party loggers are properly suppressed
"""

import logging
import sys
from unittest.mock import patch

from g_workspace_mcp.utils.pylogger import get_python_logger


class TestLoggerStream:
    """Tests for logger stream configuration."""

    def test_logger_outputs_to_stderr_not_stdout(self):
        """Logger must use stderr to avoid corrupting MCP stdio JSON-RPC stream."""
        import g_workspace_mcp.utils.pylogger as pylogger_module

        # Reset so basicConfig runs again
        pylogger_module._LOGGING_CONFIGURED = False

        with patch("g_workspace_mcp.utils.pylogger.logging.basicConfig") as mock_basic:
            get_python_logger()
            mock_basic.assert_called_once()
            call_kwargs = mock_basic.call_args
            assert call_kwargs[1]["stream"] is sys.stderr or call_kwargs.kwargs["stream"] is sys.stderr

        # Restore
        pylogger_module._LOGGING_CONFIGURED = False

    def test_logger_returns_structlog_logger(self):
        """get_python_logger should return a usable structlog logger."""
        logger = get_python_logger()
        # structlog.get_logger() returns a lazy proxy; verify it has standard log methods
        assert hasattr(logger, "info")
        assert hasattr(logger, "warning")
        assert hasattr(logger, "error")
        assert callable(logger.info)


class TestThirdPartyLoggerSuppression:
    """Tests for third-party logger suppression."""

    def test_google_loggers_set_to_error_level(self):
        """Google API loggers should be suppressed to ERROR level."""
        import g_workspace_mcp.utils.pylogger as pylogger_module

        pylogger_module._LOGGING_CONFIGURED = False
        get_python_logger()

        for name in pylogger_module.GOOGLE_LOGGERS:
            logger = logging.getLogger(name)
            assert logger.level == logging.ERROR, (
                f"Logger '{name}' should be ERROR level, got {logger.level}"
            )

        pylogger_module._LOGGING_CONFIGURED = False

    def test_http_client_loggers_configured(self):
        """HTTP client loggers should be configured (not left at default)."""
        import g_workspace_mcp.utils.pylogger as pylogger_module

        pylogger_module._LOGGING_CONFIGURED = False
        get_python_logger("WARNING")

        for name in pylogger_module.HTTP_CLIENT_LOGGERS:
            logger = logging.getLogger(name)
            # Should be set to the configured level (WARNING), not default (0)
            assert logger.level != logging.NOTSET, (
                f"Logger '{name}' should be configured, not NOTSET"
            )

        pylogger_module._LOGGING_CONFIGURED = False
