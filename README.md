# Google Workspace MCP Server

A Model Context Protocol (MCP) server providing read-only access to Google Workspace services.

## How is this different?

Most Google Workspace MCPs require complex setup. This MCP offers **two simple authentication options**:

### Option 1: OAuth (Recommended)
- Just sign in with your Google account
- No gcloud CLI needed
- Works with personal Gmail and Google Workspace accounts
- Tokens stored securely in `~/.config/g-workspace-mcp/`

### Option 2: ADC (Application Default Credentials)
- Uses gcloud CLI (same as Terraform, other Google tools)
- Ideal for enterprise users with existing gcloud setup
- Requires a quota project with Workspace APIs enabled

**Both options work with personal Gmail accounts and enterprise Google Workspace accounts.**

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
1. **Check gcloud CLI** - Verify it's installed
2. **Check existing credentials** - If you have existing ADC credentials, shows the file location and any configured `quota_project`
3. **Test API access** - Verifies your credentials have the required scopes and that the quota project (if any) has Workspace APIs enabled
4. **Re-authenticate if needed** - If scopes are missing:
   - Creates a timestamped backup of your existing credentials
   - Opens browser for Google authentication
   - Reminds you to restore your quota project if one was configured

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

This MCP supports two authentication methods. Use whichever suits your setup.

### OAuth Token Storage

OAuth tokens are stored securely in:
- **Location**: `~/.config/g-workspace-mcp/token.json`
- **Permissions**: 600 (owner read/write only)
- **Refresh**: Tokens auto-refresh when expired

### ADC Token Storage

ADC tokens are stored in:
- **Linux/macOS**: `~/.config/gcloud/application_default_credentials.json`

When re-authenticating with ADC, the setup command automatically backs up your existing credentials:
```
~/.config/gcloud/application_default_credentials.json.backup.<timestamp>
```

### Token Lifetime

- **Access tokens** last ~1 hour and auto-refresh
- **Refresh tokens** last until revoked or unused for 6 months
- If authentication expires, run `g-workspace-mcp setup` again

## CLI Commands

```bash
# Set up authentication (interactive - choose OAuth or ADC)
g-workspace-mcp setup

# Set up with specific method
g-workspace-mcp setup --oauth          # OAuth flow (recommended)
g-workspace-mcp setup --adc            # ADC/gcloud flow

# Configure MCP for AI tools (shows help if no format specified)
g-workspace-mcp config -f <claude|cursor|gemini|json> [-s user|project]

# Check authentication status
g-workspace-mcp status

# Remove stored credentials
g-workspace-mcp logout                 # Remove OAuth token
g-workspace-mcp logout --all           # Also show ADC removal instructions

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

- All API scopes are **read-only** for safety
- OAuth tokens stored with **600 permissions** (owner read/write only)
- No credentials files to manage or share
- Client secrets (if using OAuth) should never be committed to git

## Privacy

This MCP does **not** collect, store, or transmit any user data:

- **No data logging** - Operational logs contain only metadata (counts, IDs), never content
- **No data storage** - Your emails, files, and calendar events are never written to disk
- **No telemetry** - Zero analytics, tracking, or usage reporting
- **Direct data flow** - Data flows directly from Google APIs to your AI tool

The only file stored locally is your OAuth token (`~/.config/g-workspace-mcp/token.json`) for authentication purposes.

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
