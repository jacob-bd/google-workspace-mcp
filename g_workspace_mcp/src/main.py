#!/usr/bin/env python3
"""
Main entry point for Google Workspace MCP Server.

Runs in stdio mode - Claude Code spawns this process on demand.
No persistent server needed.
"""

from g_workspace_mcp.src.mcp import WorkspaceMCPServer
from g_workspace_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def main() -> None:
    """
    Main entry point - runs MCP server in stdio mode.

    Claude Code will spawn this process and communicate via stdin/stdout.
    """
    logger.info("Starting Google Workspace MCP Server (stdio mode)")

    server = WorkspaceMCPServer()

    # Run in stdio mode - FastMCP handles the protocol
    server.mcp.run()


if __name__ == "__main__":
    main()
