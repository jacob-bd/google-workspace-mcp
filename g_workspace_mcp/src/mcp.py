"""
Google Workspace MCP Server.

Provides:
- WorkspaceMCPServer class that registers all Google Workspace tools
"""

from fastmcp import FastMCP

from g_workspace_mcp.src.tools.calendar_tools import calendar_get_events, calendar_list
from g_workspace_mcp.src.tools.drive_tools import (
    drive_get_content,
    drive_list,
    drive_list_recursive,
    drive_search,
)
from g_workspace_mcp.src.tools.gmail_tools import gmail_get_message, gmail_list_labels, gmail_search
from g_workspace_mcp.src.tools.sheets_tools import sheets_read
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


class WorkspaceMCPServer:
    """
    MCP Server for Google Workspace tools.

    Registers all Google Workspace tools with FastMCP.

    Usage:
        server = WorkspaceMCPServer()
        app = server.mcp.http_app()  # For FastAPI mounting
    """

    def __init__(self, name: str = "google-workspace"):
        """
        Initialize the Workspace MCP Server.

        Args:
            name: Server name for MCP registration
        """
        self.mcp = FastMCP(name)
        self._register_mcp_tools()
        logger.info(f"Initialized WorkspaceMCPServer: {name}")

    def _register_mcp_tools(self) -> None:
        """Register all Google Workspace tools with the MCP server."""

        # Drive tools
        self.mcp.tool()(drive_search)
        self.mcp.tool()(drive_list)
        self.mcp.tool()(drive_list_recursive)
        self.mcp.tool()(drive_get_content)

        # Gmail tools
        self.mcp.tool()(gmail_search)
        self.mcp.tool()(gmail_get_message)
        self.mcp.tool()(gmail_list_labels)

        # Calendar tools
        self.mcp.tool()(calendar_list)
        self.mcp.tool()(calendar_get_events)

        # Sheets tools
        self.mcp.tool()(sheets_read)

        logger.info("Registered 10 Google Workspace MCP tools")
