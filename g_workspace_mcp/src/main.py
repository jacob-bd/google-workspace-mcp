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
    import sys

    logger.info("Starting Google Workspace MCP Server (stdio mode)")

    try:
        server = WorkspaceMCPServer()
        # Run in stdio mode - FastMCP handles the protocol
        server.mcp.run()
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except BrokenPipeError:
        # Parent process disconnected - normal during shutdown
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"Server failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
