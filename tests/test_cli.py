"""
Tests for CLI commands.

Tests cover:
- Setup command flow
- Status command output
- Logout command
- Config command
"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from g_workspace_mcp.src.cli import main


@pytest.fixture
def cli_runner():
    """Create a Click CLI test runner."""
    return CliRunner()


class TestLogoutCommand:
    """Tests for the logout command."""

    def test_logout_no_token(self, cli_runner):
        """Logout should handle missing token gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"

            with patch("g_workspace_mcp.src.cli.TOKEN_FILE", token_path):
                result = cli_runner.invoke(main, ["logout"])

                assert result.exit_code == 0
                assert "No OAuth token found" in result.output

    def test_logout_removes_token(self, cli_runner):
        """Logout should remove existing token file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text('{"token": "test"}')

            with patch("g_workspace_mcp.src.cli.TOKEN_FILE", token_path):
                result = cli_runner.invoke(main, ["logout"])

                assert result.exit_code == 0
                assert "Removed OAuth token" in result.output
                assert not token_path.exists()

    def test_logout_all_shows_adc_instructions(self, cli_runner):
        """Logout --all should show ADC removal instructions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            adc_path = Path(tmpdir) / "adc.json"
            adc_path.write_text('{"credentials": "test"}')

            with patch("g_workspace_mcp.src.cli.TOKEN_FILE", token_path):
                with patch("g_workspace_mcp.src.cli._get_adc_file_path", return_value=adc_path):
                    result = cli_runner.invoke(main, ["logout", "--all"])

                    assert result.exit_code == 0
                    assert "gcloud auth application-default revoke" in result.output


class TestStatusCommand:
    """Tests for the status command."""

    @patch("g_workspace_mcp.src.cli._test_workspace_api_access")
    @patch("g_workspace_mcp.src.auth.google_oauth.get_auth")
    def test_status_shows_oauth_status(self, mock_get_auth, mock_test_api, cli_runner):
        """Status should show OAuth token status."""
        mock_auth = MagicMock()
        mock_auth.has_oauth_token.return_value = False
        mock_auth.has_adc.return_value = False
        mock_get_auth.return_value = mock_auth
        mock_test_api.return_value = (False, "no_auth")

        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"

            with patch("g_workspace_mcp.src.cli.TOKEN_FILE", token_path):
                with patch("g_workspace_mcp.src.cli._check_gcloud_installed", return_value=False):
                    result = cli_runner.invoke(main, ["status"])

                    assert result.exit_code == 0
                    assert "OAuth" in result.output

    @patch("g_workspace_mcp.src.cli._test_workspace_api_access")
    @patch("g_workspace_mcp.src.auth.google_oauth.get_auth")
    def test_status_shows_api_access(self, mock_get_auth, mock_test_api, cli_runner):
        """Status should show API access test results."""
        mock_auth = MagicMock()
        mock_auth.has_oauth_token.return_value = True
        mock_auth.has_adc.return_value = False
        mock_get_auth.return_value = mock_auth
        mock_test_api.return_value = (True, "")

        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"
            token_path.write_text("{}")

            with patch("g_workspace_mcp.src.cli.TOKEN_FILE", token_path):
                with patch("g_workspace_mcp.src.cli._check_gcloud_installed", return_value=False):
                    result = cli_runner.invoke(main, ["status"])

                    assert result.exit_code == 0
                    assert "API Access" in result.output
                    assert "Ready to use" in result.output


class TestSetupCommand:
    """Tests for the setup command."""

    @patch("g_workspace_mcp.src.cli._test_workspace_api_access")
    @patch("g_workspace_mcp.src.auth.google_oauth.get_auth")
    def test_setup_detects_existing_auth(self, mock_get_auth, mock_test_api, cli_runner):
        """Setup should detect when authentication already works."""
        mock_auth = MagicMock()
        mock_auth.has_oauth_token.return_value = True
        mock_auth.has_adc.return_value = False
        mock_get_auth.return_value = mock_auth
        mock_test_api.return_value = (True, "")

        result = cli_runner.invoke(main, ["setup"])

        assert result.exit_code == 0
        assert "Setup complete" in result.output

    @patch("g_workspace_mcp.src.auth.google_oauth.get_auth")
    def test_setup_oauth_missing_client_secret(self, mock_get_auth, cli_runner):
        """Setup --oauth should fail gracefully when client secret missing."""
        mock_auth = MagicMock()
        mock_auth.has_oauth_token.return_value = False
        mock_auth.has_adc.return_value = False
        mock_get_auth.return_value = mock_auth

        with tempfile.TemporaryDirectory() as tmpdir:
            client_secret_path = Path(tmpdir) / "client_secret.json"

            with patch("g_workspace_mcp.src.cli.CLIENT_SECRET_FILE", client_secret_path):
                result = cli_runner.invoke(main, ["setup", "--oauth"])

                assert result.exit_code == 1
                assert "Client secret file not found" in result.output

    @patch("g_workspace_mcp.src.cli._check_gcloud_installed")
    @patch("g_workspace_mcp.src.auth.google_oauth.get_auth")
    def test_setup_adc_missing_gcloud(self, mock_get_auth, mock_gcloud, cli_runner):
        """Setup --adc should fail gracefully when gcloud not installed."""
        mock_auth = MagicMock()
        mock_auth.has_oauth_token.return_value = False
        mock_auth.has_adc.return_value = False
        mock_get_auth.return_value = mock_auth
        mock_gcloud.return_value = False

        result = cli_runner.invoke(main, ["setup", "--adc"])

        assert result.exit_code == 1
        assert "gcloud CLI not found" in result.output


class TestConfigCommand:
    """Tests for the config command."""

    def test_config_no_format_shows_help(self, cli_runner):
        """Config without format should show help."""
        result = cli_runner.invoke(main, ["config"])

        assert result.exit_code == 0
        assert "Available formats" in result.output
        assert "claude" in result.output
        assert "cursor" in result.output

    @patch("shutil.which")
    def test_config_json_outputs_json(self, mock_which, cli_runner):
        """Config -f json should output JSON."""
        mock_which.return_value = "/usr/local/bin/g-workspace-mcp"

        result = cli_runner.invoke(main, ["config", "-f", "json"])

        assert result.exit_code == 0
        # Should be valid JSON
        import json

        config = json.loads(result.output)
        assert "command" in config
        assert "args" in config


class TestHelperFunctions:
    """Tests for CLI helper functions."""

    def test_check_gcloud_installed(self):
        """_check_gcloud_installed should check for gcloud binary."""
        from g_workspace_mcp.src.cli import _check_gcloud_installed

        # This test just verifies the function runs without error
        # The actual result depends on the test environment
        result = _check_gcloud_installed()
        assert isinstance(result, bool)

    def test_get_adc_file_path(self):
        """_get_adc_file_path should return correct path."""
        from g_workspace_mcp.src.cli import _get_adc_file_path

        path = _get_adc_file_path()
        assert "gcloud" in str(path)
        assert "application_default_credentials.json" in str(path)

    def test_read_adc_file_missing(self):
        """_read_adc_file should return None for missing file."""
        from g_workspace_mcp.src.cli import _read_adc_file

        with patch("g_workspace_mcp.src.cli._get_adc_file_path") as mock_path:
            mock_path.return_value = Path("/nonexistent/path.json")

            result = _read_adc_file()
            assert result is None

    def test_backup_adc_file_creates_backup(self):
        """_backup_adc_file should create timestamped backup."""
        from g_workspace_mcp.src.cli import _backup_adc_file

        with tempfile.TemporaryDirectory() as tmpdir:
            adc_path = Path(tmpdir) / "application_default_credentials.json"
            adc_path.write_text('{"test": true}')

            with patch("g_workspace_mcp.src.cli._get_adc_file_path", return_value=adc_path):
                backup_path = _backup_adc_file()

                assert backup_path is not None
                assert backup_path.exists()
                assert "backup" in str(backup_path)
