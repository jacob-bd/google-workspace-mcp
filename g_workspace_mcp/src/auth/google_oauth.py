"""
Google Workspace OAuth Authentication.

Supports two authentication methods:
1. OAuth Client ID flow - User signs in via browser, tokens stored locally
2. ADC (Application Default Credentials) - Uses gcloud auth, for advanced users

OAuth is preferred as it doesn't require gcloud CLI installation.
"""

from pathlib import Path
from typing import Any, Optional

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as OAuthCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

# All read-only scopes for Google Workspace
SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
]

# Config directory for OAuth tokens
CONFIG_DIR = Path.home() / ".config" / "g-workspace-mcp"
TOKEN_FILE = CONFIG_DIR / "token.json"
CLIENT_SECRET_FILE = CONFIG_DIR / "client_secret.json"


class GoogleWorkspaceAuth:
    """
    Manages Google Workspace authentication.

    Supports two authentication methods (tried in order):
    1. OAuth Client ID flow - tokens stored in ~/.config/g-workspace-mcp/token.json
    2. ADC (Application Default Credentials) - for users with gcloud configured

    Usage:
        auth = GoogleWorkspaceAuth()
        creds = auth.get_credentials()
        drive_service = auth.get_service("drive", "v3")
    """

    def __init__(self):
        self._credentials: Optional[Credentials] = None
        self._services: dict[str, Any] = {}

    def _load_oauth_credentials(self) -> Optional[Credentials]:
        """Load OAuth credentials from token file if available."""
        if not TOKEN_FILE.exists():
            return None

        try:
            creds = OAuthCredentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

            # Refresh if expired
            if creds and creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    # Save refreshed token
                    self._save_token(creds)
                    logger.info("Refreshed OAuth credentials")
                except google.auth.exceptions.RefreshError:
                    logger.warning("OAuth token refresh failed, will try other methods")
                    return None

            if creds and creds.valid:
                logger.info("Loaded OAuth credentials from token file")
                return creds

        except Exception as e:
            logger.warning(f"Failed to load OAuth credentials: {e}")

        return None

    def _load_adc_credentials(self) -> Optional[Credentials]:
        """Load Application Default Credentials if available."""
        try:
            creds, project = google.auth.default(scopes=SCOPES)
            logger.info("Loaded Application Default Credentials")

            # Refresh if expired
            if creds.expired:
                creds.refresh(Request())
                logger.info("Refreshed ADC credentials")

            return creds

        except google.auth.exceptions.DefaultCredentialsError:
            return None

    def _save_token(self, creds: Credentials) -> None:
        """Save OAuth credentials to token file with secure permissions (600)."""
        import os
        import stat

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)

        # Write token with 600 permissions (owner read/write only)
        token_path = str(TOKEN_FILE)
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        try:
            os.write(fd, creds.to_json().encode())
        finally:
            os.close(fd)

        logger.info(f"Saved OAuth token to {TOKEN_FILE}")

    def get_credentials(self) -> Credentials:
        """
        Get valid OAuth credentials.

        Tries OAuth token file first, then falls back to ADC.

        Returns:
            Valid Credentials object

        Raises:
            ValueError: If no valid credentials found
        """
        if self._credentials is not None and self._credentials.valid:
            return self._credentials

        # Try OAuth credentials first
        self._credentials = self._load_oauth_credentials()
        if self._credentials:
            return self._credentials

        # Fall back to ADC
        self._credentials = self._load_adc_credentials()
        if self._credentials:
            return self._credentials

        # No credentials found
        raise ValueError("Google authentication not configured.\nRun: g-workspace-mcp setup")

    def get_service(self, service_name: str, version: str) -> Any:
        """
        Get authenticated Google API service.

        Args:
            service_name: API name (drive, gmail, calendar, sheets)
            version: API version (v3, v1, etc.)

        Returns:
            Authenticated service object
        """
        cache_key = f"{service_name}_{version}"

        if cache_key not in self._services:
            credentials = self.get_credentials()
            self._services[cache_key] = build(service_name, version, credentials=credentials)
            logger.info(f"Created {service_name} {version} service")

        return self._services[cache_key]

    def clear_cache(self) -> None:
        """Clear cached services (useful after credential refresh)."""
        self._services.clear()
        self._credentials = None

    def is_authenticated(self) -> bool:
        """Check if valid credentials exist without triggering auth flow."""
        # Check OAuth token first
        if self._load_oauth_credentials():
            return True
        # Check ADC
        if self._load_adc_credentials():
            return True
        return False

    def has_oauth_token(self) -> bool:
        """Check if OAuth token file exists and is valid."""
        return self._load_oauth_credentials() is not None

    def has_adc(self) -> bool:
        """Check if ADC credentials are available."""
        return self._load_adc_credentials() is not None


def run_oauth_flow(client_secret_path: Optional[Path] = None) -> bool:
    """
    Run the OAuth flow to authenticate the user.

    Opens a browser for user authentication and saves the token locally.

    Args:
        client_secret_path: Path to client_secret.json file. If None, uses default location.

    Returns:
        True if authentication successful, False otherwise.
    """
    import os
    import stat

    secret_path = client_secret_path or CLIENT_SECRET_FILE

    if not secret_path.exists():
        logger.error(f"Client secret file not found: {secret_path}")
        return False

    try:
        flow = InstalledAppFlow.from_client_secrets_file(str(secret_path), SCOPES)

        # Run local server flow - opens browser automatically
        creds = flow.run_local_server(port=0)

        # Save the token with secure permissions (600 - owner read/write only)
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        token_path = str(TOKEN_FILE)
        fd = os.open(token_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, stat.S_IRUSR | stat.S_IWUSR)
        try:
            os.write(fd, creds.to_json().encode())
        finally:
            os.close(fd)

        logger.info(f"OAuth authentication successful, token saved to {TOKEN_FILE}")
        return True

    except Exception as e:
        logger.error(f"OAuth flow failed: {e}")
        return False


def get_oauth_status() -> dict:
    """
    Get detailed status of OAuth configuration.

    Returns:
        Dictionary with status information.
    """
    return {
        "config_dir": str(CONFIG_DIR),
        "token_file": str(TOKEN_FILE),
        "token_exists": TOKEN_FILE.exists(),
        "client_secret_file": str(CLIENT_SECRET_FILE),
        "client_secret_exists": CLIENT_SECRET_FILE.exists(),
    }


# Global singleton for convenience
_auth_instance: Optional[GoogleWorkspaceAuth] = None


def get_auth() -> GoogleWorkspaceAuth:
    """Get global GoogleWorkspaceAuth instance."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = GoogleWorkspaceAuth()
    return _auth_instance
