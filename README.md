# Google Workspace MCP Server

A Model Context Protocol (MCP) server providing read-only access to Google Workspace services.

## How is this different?

Most Google Workspace MCPs require you to:
1. Create a Google Cloud Platform project
2. Enable APIs manually
3. Configure OAuth consent screens
4. Create OAuth credentials and download a `credentials.json` file
5. Manage token refresh and storage

**This MCP uses Application Default Credentials (ADC)** - the same auth method used by `gcloud`, Terraform, and other Google tools. Setup is one command:

```bash
gcloud auth application-default login
```

No GCP project access needed. No credentials files to manage. Works with your existing Google Workspace account - ideal for enterprise users whose organizations manage Google Workspace centrally.

## Features

- **Google Drive**: Search files, list folders, read document content
- **Gmail**: Search emails, read messages, list labels
- **Google Calendar**: List calendars, get events
- **Google Sheets**: Read spreadsheet data

All access is **read-only** for safety.

## Requirements

- **Python 3.11+**
- **uv** - Fast Python package manager ([install](https://docs.astral.sh/uv/getting-started/installation/))
- **Google Cloud CLI** - For authentication

## Quick Start

### 1. Install uv (if not already installed)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Install the MCP Server

**Clone from GitHub:**
```bash
git clone https://github.com/jacob-bd/google-workspace-mcp.git
cd google-workspace-mcp
uv tool install .
```

**Or clone from GitLab:**
```bash
git clone https://gitlab.com/jbendavi/google-workspace-mcp.git
cd google-workspace-mcp
uv tool install .
```

This installs the CLI globally in an isolated environment. After installation, you can delete the `google-workspace-mcp` folder.

### 3. Install Google Cloud CLI (if not already installed)

**macOS:**
```bash
brew install --cask google-cloud-sdk
```

**Linux (Fedora/RHEL):**
```bash
sudo dnf install google-cloud-cli
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install google-cloud-cli
```

### 4. Authenticate

```bash
g-workspace-mcp setup
```

This will:
- Check that gcloud CLI is installed
- Open a browser for Google authentication
- Store credentials for future use (auto-refreshes)

**That's it!** No GCP project access required - just your Google account.

### 5. Configure Your AI Tool

```bash
# See available options
g-workspace-mcp config

# Configure Claude Code
g-workspace-mcp config -f claude

# Configure Gemini CLI
g-workspace-mcp config -f gemini

# Get JSON for Cursor or other tools
g-workspace-mcp config -f cursor
```

The command will show what it's about to do and ask for confirmation.

**No server to run!** Claude Code spawns the process on demand via stdio.

## Authentication Details

This MCP uses **Application Default Credentials (ADC)** - the same method used by the analyzer tool.

- **Access tokens** last ~1 hour and auto-refresh
- **Refresh tokens** last until revoked or unused for 6 months
- If authentication expires, run `g-workspace-mcp setup` again

### Token Storage Location

ADC stores tokens in:
- **Linux**: `~/.config/gcloud/application_default_credentials.json`
- **macOS**: `~/.config/gcloud/application_default_credentials.json`

### Re-authenticate

If you need to re-authenticate:
```bash
g-workspace-mcp setup
```

Or manually:
```bash
gcloud auth application-default login
```

## CLI Commands

```bash
# Set up authentication (opens browser)
g-workspace-mcp setup

# Configure MCP for AI tools (shows help if no format specified)
g-workspace-mcp config -f <claude|cursor|gemini|json> [-s user|project]

# Check authentication status
g-workspace-mcp status

# Run MCP server (called by AI tools automatically)
g-workspace-mcp run
```

## Available Tools

### Drive Tools

| Tool | Description |
|------|-------------|
| `drive_search` | Search files by query with optional type filter |
| `drive_list` | List files in a folder |
| `drive_get_content` | Get file content (Docs, Sheets, text files) |

### Gmail Tools

| Tool | Description |
|------|-------------|
| `gmail_search` | Search emails using Gmail query syntax |
| `gmail_get_message` | Get full email content by message ID |
| `gmail_list_labels` | List all Gmail labels |

### Calendar Tools

| Tool | Description |
|------|-------------|
| `calendar_list` | List all accessible calendars |
| `calendar_get_events` | Get events in a date range |

### Sheets Tools

| Tool | Description |
|------|-------------|
| `sheets_read` | Read data from a spreadsheet range |

## Configuration for AI Tools

### Claude Code

**Option 1: Using g-workspace-mcp (recommended)**

```bash
# Add system-wide (default)
g-workspace-mcp config -f claude

# Or add project-level
g-workspace-mcp config -f claude -s project
```

This will show you the command and ask for confirmation before running it.

**Option 2: Manual configuration**

Add to `~/.claude/mcp_servers.json`:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "g-workspace-mcp",
      "args": ["run"],
      "env": {}
    }
  }
}
```

**Verify installation:**

Use the `/mcp` command inside Claude Code to verify the server is configured.

### Cursor

Add to Cursor MCP settings:

```json
{
  "google-workspace": {
    "command": "g-workspace-mcp",
    "args": ["run"]
  }
}
```

### Gemini CLI

**Option 1: Using g-workspace-mcp (recommended)**

```bash
# Add system-wide (default)
g-workspace-mcp config -f gemini

# Or add project-level
g-workspace-mcp config -f gemini -s project
```

This will show you the command and ask for confirmation before running it.

**Option 2: Manual configuration**

For **system-wide** access, add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "g-workspace-mcp",
      "args": ["run"]
    }
  }
}
```

For **project-level** access, add to `.gemini/settings.json` in your project directory:

```json
{
  "mcpServers": {
    "google-workspace": {
      "command": "g-workspace-mcp",
      "args": ["run"]
    }
  }
}
```

**Verify installation:**

```bash
gemini mcp list
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level |

## Security

- All API scopes are **read-only**
- Uses Google's Application Default Credentials
- No credentials files to manage or share

## Troubleshooting

### "Google authentication not configured"

Run the setup command:
```bash
g-workspace-mcp setup
```

### "Authentication expired and could not be refreshed"

Re-authenticate:
```bash
g-workspace-mcp setup
```

### Check Status

```bash
g-workspace-mcp status
```

## Development

```bash
# Install in editable mode (for development - requires keeping the folder)
uv pip install -e ".[dev]"

# Run directly
uv run python -m g_workspace_mcp.src.main
```

## License

MIT
