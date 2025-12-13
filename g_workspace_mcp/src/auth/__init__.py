"""Authentication module for Google Workspace MCP Server."""

from .google_oauth import GoogleWorkspaceAuth, get_auth

__all__ = ["GoogleWorkspaceAuth", "get_auth"]
