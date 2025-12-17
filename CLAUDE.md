# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MCP server providing **read-only** access to Google Workspace (Drive, Gmail, Calendar, Sheets). Uses Application Default Credentials (ADC) via `gcloud auth application-default login` - no GCP project or credentials.json needed.

## Development Commands

```bash
# Install globally (isolated environment)
uv tool install .

# Install for development (editable, requires venv)
uv venv && source .venv/bin/activate && uv pip install -e ".[dev]"

# Run linting
ruff check .

# Run formatting
ruff format .
black .

# Type checking
mypy g_workspace_mcp

# Run tests
pytest

# Run single test
pytest tests/test_file.py::test_name -v

# Test the CLI
g-workspace-mcp --help
g-workspace-mcp status

# Reinstall after changes (ALWAYS clean cache first to avoid stale code)
uv cache clean && uv tool install --force .
```

## Architecture

**Stdio Mode**: MCP runs via stdin/stdout (not HTTP). AI tools spawn the process on demand via `g-workspace-mcp run`.

```
g_workspace_mcp/
├── src/
│   ├── auth/google_oauth.py   # ADC auth via google.auth.default(), global singleton get_auth()
│   ├── cli.py                 # Click CLI (setup, run, config, status)
│   ├── main.py                # Entry point - runs server.mcp.run()
│   ├── mcp.py                 # WorkspaceMCPServer class, registers all tools with FastMCP
│   └── tools/                 # One file per Google service (drive, gmail, calendar, sheets)
└── utils/pylogger.py          # structlog-based logging
```

**Key classes:**
- `GoogleWorkspaceAuth` (google_oauth.py:30): Manages ADC credentials and service caching
- `WorkspaceMCPServer` (mcp.py:19): Registers tools with FastMCP

## Adding New Tools

1. Create function in `tools/*.py` returning `Dict[str, Any]` with `status` key
2. Register in `mcp.py` `_register_mcp_tools()`:
   ```python
   self.mcp.tool()(your_new_tool)
   ```

**Tool pattern:**
```python
def tool_name(...) -> Dict[str, Any]:
    try:
        service = get_auth().get_service("api_name", "version")
        # ... work ...
        return {"status": "success", "data": result}
    except Exception as e:
        logger.error(f"Tool failed: {e}")
        return {"status": "error", "error": str(e), "message": "Human readable message"}
```

## Key Design Decisions

- **Read-only scopes only** (`*.readonly`) for safety
- **No HTTP server** - stdio mode for MCP
- **ADC authentication** - users run `gcloud auth application-default login` once
- **Global auth singleton** - `get_auth()` returns cached `GoogleWorkspaceAuth` instance
- **Minimal dependencies** - no FastAPI, no pydantic-settings, no dotenv

## Common Issues

| Issue | Solution |
|-------|----------|
| "Google authentication not configured" | Run `g-workspace-mcp setup` |
| "Authentication expired" | Run `g-workspace-mcp setup` |
| Import errors after rename | Ensure all imports use `g_workspace_mcp` (underscore, not hyphen) |
