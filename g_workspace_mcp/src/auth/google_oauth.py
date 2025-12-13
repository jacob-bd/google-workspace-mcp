"""
Google Workspace OAuth Authentication using Application Default Credentials.

Provides:
- ADC-based authentication (same as agents-python/analyzer)
- No credentials.json file needed
- User runs `gcloud auth application-default login` once
"""

from typing import Any, Optional

import google.auth
from google.auth.credentials import Credentials
from google.auth.transport.requests import Request
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


class GoogleWorkspaceAuth:
    """
    Manages Google Workspace authentication using Application Default Credentials.

    Uses the same auth pattern as agents-python/analyzer:
    - User runs `gcloud auth application-default login` once
    - Credentials are automatically discovered and refreshed

    Usage:
        auth = GoogleWorkspaceAuth()
        creds = auth.get_credentials()
        drive_service = auth.get_service("drive", "v3")
    """

    def __init__(self):
        self._credentials: Optional[Credentials] = None
        self._services: dict[str, Any] = {}

    def get_credentials(self) -> Credentials:
        """
        Get valid OAuth credentials using Application Default Credentials.

        Returns:
            Valid Credentials object

        Raises:
            ValueError: If ADC not configured or refresh fails
        """
        if self._credentials is None or not self._credentials.valid:
            try:
                # Use Application Default Credentials
                self._credentials, project = google.auth.default(scopes=SCOPES)
                logger.info("Loaded Application Default Credentials")

                # Refresh if expired (tokens last ~1 hour, refresh token auto-renews)
                if self._credentials.expired and self._credentials.refresh_token:
                    try:
                        self._credentials.refresh(Request())
                        logger.info("Refreshed expired credentials")
                    except google.auth.exceptions.RefreshError as e:
                        logger.error(f"Token refresh failed: {e}")
                        raise ValueError(
                            "Google authentication expired and could not be refreshed.\n"
                            "Please re-authenticate by running:\n"
                            "  g-workspace-mcp setup\n"
                            "Or: gcloud auth application-default login"
                        ) from e
                elif self._credentials.expired:
                    self._credentials.refresh(Request())
                    logger.info("Refreshed credentials")

            except google.auth.exceptions.DefaultCredentialsError as e:
                logger.error(f"ADC not configured: {e}")
                raise ValueError(
                    "Google authentication not configured.\n"
                    "Run: g-workspace-mcp setup\n"
                    "Or: gcloud auth application-default login"
                ) from e

        return self._credentials

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
        try:
            creds, _ = google.auth.default(scopes=SCOPES)
            if creds.expired:
                creds.refresh(Request())
            return creds.valid
        except Exception:
            return False


# Global singleton for convenience
_auth_instance: Optional[GoogleWorkspaceAuth] = None


def get_auth() -> GoogleWorkspaceAuth:
    """Get global GoogleWorkspaceAuth instance."""
    global _auth_instance
    if _auth_instance is None:
        _auth_instance = GoogleWorkspaceAuth()
    return _auth_instance
