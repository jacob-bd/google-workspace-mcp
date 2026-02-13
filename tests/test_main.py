"""
Tests for main entry point.

Tests cover:
- Graceful handling of KeyboardInterrupt
- Graceful handling of BrokenPipeError
- sys.exit(1) on unexpected errors
"""

from unittest.mock import MagicMock, patch

import pytest

from g_workspace_mcp.src.main import main


class TestMainExceptionHandling:
    """Tests for main() exception handling."""

    @patch("g_workspace_mcp.src.main.WorkspaceMCPServer")
    def test_keyboard_interrupt_exits_cleanly(self, mock_server_class):
        """KeyboardInterrupt should not raise - server exits cleanly."""
        mock_server = MagicMock()
        mock_server.mcp.run.side_effect = KeyboardInterrupt()
        mock_server_class.return_value = mock_server

        # Should not raise
        main()

    @patch("g_workspace_mcp.src.main.WorkspaceMCPServer")
    def test_broken_pipe_exits_cleanly(self, mock_server_class):
        """BrokenPipeError should not raise - client disconnected."""
        mock_server = MagicMock()
        mock_server.mcp.run.side_effect = BrokenPipeError()
        mock_server_class.return_value = mock_server

        # Should not raise
        main()

    @patch("g_workspace_mcp.src.main.WorkspaceMCPServer")
    def test_unexpected_error_calls_sys_exit(self, mock_server_class):
        """Unexpected exceptions should call sys.exit(1)."""
        mock_server = MagicMock()
        mock_server.mcp.run.side_effect = RuntimeError("something broke")
        mock_server_class.return_value = mock_server

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch("g_workspace_mcp.src.main.WorkspaceMCPServer")
    def test_init_failure_calls_sys_exit(self, mock_server_class):
        """If WorkspaceMCPServer() fails, should call sys.exit(1)."""
        mock_server_class.side_effect = ImportError("missing dependency")

        with pytest.raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1
