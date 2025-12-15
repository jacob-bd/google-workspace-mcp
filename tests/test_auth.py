"""
Tests for Google Workspace authentication module.

Tests cover:
- OAuth token loading (valid, expired, missing, corrupted)
- ADC fallback when OAuth missing
- Credential refresh logic
- Token file permissions
"""

import os
import stat
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from g_workspace_mcp.src.auth.google_oauth import (
    SCOPES,
    GoogleWorkspaceAuth,
    get_auth,
    run_oauth_flow,
)


class TestGoogleWorkspaceAuth:
    """Tests for GoogleWorkspaceAuth class."""

    def test_init_creates_empty_state(self):
        """Auth instance starts with no credentials or services."""
        auth = GoogleWorkspaceAuth()
        assert auth._credentials is None
        assert auth._services == {}

    def test_clear_cache_resets_state(self):
        """clear_cache should reset credentials and services."""
        auth = GoogleWorkspaceAuth()
        auth._credentials = MagicMock()
        auth._services = {"test": MagicMock()}

        auth.clear_cache()

        assert auth._credentials is None
        assert auth._services == {}

    @patch("g_workspace_mcp.src.auth.google_oauth.TOKEN_FILE")
    def test_load_oauth_credentials_missing_file(self, mock_token_file):
        """Should return None when token file doesn't exist."""
        mock_token_file.exists.return_value = False

        auth = GoogleWorkspaceAuth()
        result = auth._load_oauth_credentials()

        assert result is None

    @patch("g_workspace_mcp.src.auth.google_oauth.OAuthCredentials")
    @patch("g_workspace_mcp.src.auth.google_oauth.TOKEN_FILE")
    def test_load_oauth_credentials_valid_token(self, mock_token_file, mock_creds_class):
        """Should load valid OAuth credentials from file."""
        mock_token_file.exists.return_value = True

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = False
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        auth = GoogleWorkspaceAuth()
        result = auth._load_oauth_credentials()

        assert result == mock_creds
        mock_creds_class.from_authorized_user_file.assert_called_once()

    @patch("g_workspace_mcp.src.auth.google_oauth.Request")
    @patch("g_workspace_mcp.src.auth.google_oauth.OAuthCredentials")
    @patch("g_workspace_mcp.src.auth.google_oauth.TOKEN_FILE")
    def test_load_oauth_credentials_expired_refreshes(
        self, mock_token_file, mock_creds_class, mock_request
    ):
        """Should refresh expired OAuth credentials."""
        mock_token_file.exists.return_value = True

        mock_creds = MagicMock()
        mock_creds.valid = True
        mock_creds.expired = True
        mock_creds.refresh_token = "refresh_token"
        mock_creds_class.from_authorized_user_file.return_value = mock_creds

        auth = GoogleWorkspaceAuth()
        # Mock _save_token to avoid file operations
        auth._save_token = MagicMock()

        auth._load_oauth_credentials()

        mock_creds.refresh.assert_called_once()
        auth._save_token.assert_called_once_with(mock_creds)

    @patch("g_workspace_mcp.src.auth.google_oauth.google.auth.default")
    def test_load_adc_credentials_success(self, mock_auth_default):
        """Should load valid ADC credentials."""
        mock_creds = MagicMock()
        mock_creds.expired = False
        mock_auth_default.return_value = (mock_creds, "project-id")

        auth = GoogleWorkspaceAuth()
        result = auth._load_adc_credentials()

        assert result == mock_creds
        mock_auth_default.assert_called_once_with(scopes=SCOPES)

    @patch("g_workspace_mcp.src.auth.google_oauth.google.auth.default")
    def test_load_adc_credentials_not_configured(self, mock_auth_default):
        """Should return None when ADC not configured."""
        import google.auth.exceptions

        mock_auth_default.side_effect = google.auth.exceptions.DefaultCredentialsError(
            "not configured"
        )

        auth = GoogleWorkspaceAuth()
        result = auth._load_adc_credentials()

        assert result is None

    def test_get_credentials_tries_oauth_first(self):
        """get_credentials should try OAuth before ADC."""
        auth = GoogleWorkspaceAuth()

        mock_oauth_creds = MagicMock()
        auth._load_oauth_credentials = MagicMock(return_value=mock_oauth_creds)
        auth._load_adc_credentials = MagicMock()

        result = auth.get_credentials()

        assert result == mock_oauth_creds
        auth._load_oauth_credentials.assert_called_once()
        auth._load_adc_credentials.assert_not_called()

    def test_get_credentials_falls_back_to_adc(self):
        """get_credentials should fall back to ADC when OAuth fails."""
        auth = GoogleWorkspaceAuth()

        mock_adc_creds = MagicMock()
        auth._load_oauth_credentials = MagicMock(return_value=None)
        auth._load_adc_credentials = MagicMock(return_value=mock_adc_creds)

        result = auth.get_credentials()

        assert result == mock_adc_creds
        auth._load_oauth_credentials.assert_called_once()
        auth._load_adc_credentials.assert_called_once()

    def test_get_credentials_raises_when_no_auth(self):
        """get_credentials should raise ValueError when no auth available."""
        auth = GoogleWorkspaceAuth()

        auth._load_oauth_credentials = MagicMock(return_value=None)
        auth._load_adc_credentials = MagicMock(return_value=None)

        with pytest.raises(ValueError) as exc_info:
            auth.get_credentials()

        assert "authentication not configured" in str(exc_info.value).lower()

    def test_has_oauth_token_returns_bool(self):
        """has_oauth_token should return boolean based on OAuth availability."""
        auth = GoogleWorkspaceAuth()

        auth._load_oauth_credentials = MagicMock(return_value=MagicMock())
        assert auth.has_oauth_token() is True

        auth._load_oauth_credentials = MagicMock(return_value=None)
        assert auth.has_oauth_token() is False

    def test_has_adc_returns_bool(self):
        """has_adc should return boolean based on ADC availability."""
        auth = GoogleWorkspaceAuth()

        auth._load_adc_credentials = MagicMock(return_value=MagicMock())
        assert auth.has_adc() is True

        auth._load_adc_credentials = MagicMock(return_value=None)
        assert auth.has_adc() is False


class TestTokenFilePermissions:
    """Tests for token file security."""

    def test_save_token_creates_file_with_600_permissions(self):
        """Token file should be created with 600 permissions (owner only)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            token_path = Path(tmpdir) / "token.json"

            # Mock the module-level constants
            with patch("g_workspace_mcp.src.auth.google_oauth.TOKEN_FILE", token_path):
                with patch("g_workspace_mcp.src.auth.google_oauth.CONFIG_DIR", Path(tmpdir)):
                    auth = GoogleWorkspaceAuth()

                    mock_creds = MagicMock()
                    mock_creds.to_json.return_value = '{"token": "test"}'

                    auth._save_token(mock_creds)

                    # Verify file was created
                    assert token_path.exists()

                    # Verify permissions are 600 (owner read/write only)
                    file_stat = os.stat(token_path)
                    permissions = stat.S_IMODE(file_stat.st_mode)
                    assert permissions == 0o600


class TestOAuthFlow:
    """Tests for OAuth flow function."""

    def test_run_oauth_flow_missing_client_secret(self):
        """Should return False when client secret file is missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            missing_path = Path(tmpdir) / "nonexistent.json"

            result = run_oauth_flow(missing_path)

            assert result is False

    @patch("g_workspace_mcp.src.auth.google_oauth.InstalledAppFlow")
    def test_run_oauth_flow_creates_token_with_600_perms(self, mock_flow_class):
        """OAuth flow should create token file with 600 permissions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a mock client secret file
            client_secret_path = Path(tmpdir) / "client_secret.json"
            client_secret_path.write_text('{"installed": {"client_id": "test"}}')

            token_path = Path(tmpdir) / "token.json"

            # Mock the flow
            mock_flow = MagicMock()
            mock_creds = MagicMock()
            mock_creds.to_json.return_value = '{"access_token": "test"}'
            mock_flow.run_local_server.return_value = mock_creds
            mock_flow_class.from_client_secrets_file.return_value = mock_flow

            with patch("g_workspace_mcp.src.auth.google_oauth.TOKEN_FILE", token_path):
                with patch("g_workspace_mcp.src.auth.google_oauth.CONFIG_DIR", Path(tmpdir)):
                    result = run_oauth_flow(client_secret_path)

                    assert result is True
                    assert token_path.exists()

                    # Verify permissions
                    file_stat = os.stat(token_path)
                    permissions = stat.S_IMODE(file_stat.st_mode)
                    assert permissions == 0o600


class TestGetAuth:
    """Tests for global auth singleton."""

    def test_get_auth_returns_singleton(self):
        """get_auth should return the same instance."""
        # Reset the singleton
        import g_workspace_mcp.src.auth.google_oauth as auth_module

        auth_module._auth_instance = None

        auth1 = get_auth()
        auth2 = get_auth()

        assert auth1 is auth2

    def test_get_auth_creates_instance(self):
        """get_auth should create GoogleWorkspaceAuth instance."""
        import g_workspace_mcp.src.auth.google_oauth as auth_module

        auth_module._auth_instance = None

        auth = get_auth()

        assert isinstance(auth, GoogleWorkspaceAuth)


class TestScopes:
    """Tests for scope configuration."""

    def test_scopes_are_readonly(self):
        """All scopes should be readonly for security."""
        for scope in SCOPES:
            assert "readonly" in scope, f"Scope {scope} is not readonly"

    def test_scopes_include_required_apis(self):
        """SCOPES should include all required Workspace APIs."""
        scope_str = " ".join(SCOPES)
        assert "drive" in scope_str
        assert "gmail" in scope_str
        assert "calendar" in scope_str
        assert "spreadsheets" in scope_str
