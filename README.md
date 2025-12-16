# Google Workspace MCP Server

A Model Context Protocol (MCP) server providing read-only access to Google Workspace services.

## How is this different?

This MCP offers **two authentication options** depending on your setup:

### Option 1: ADC (Recommended for Enterprise)
- Uses gcloud CLI (same as Terraform, other Google tools)
- Ideal for enterprise users with existing gcloud setup
- Requires a quota project with Workspace APIs enabled
- **No additional setup** if you already have gcloud configured

### Option 2: OAuth (For Personal Gmail)
- Works with personal Gmail accounts without gcloud
- Requires one-time setup: create your own OAuth credentials in Google Cloud Console (~5 minutes)
- Tokens stored securely in `~/.config/g-workspace-mcp/`

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
- **Google Cloud CLI** - Only required for ADC authentication (not needed for OAuth)

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

**Choose your authentication method:**

- **ADC (Enterprise)**: If you have gcloud installed, just run `g-workspace-mcp setup --adc`
- **OAuth (Personal Gmail)**: First create your OAuth credentials (see next section), then run `g-workspace-mcp setup --oauth`

---

## Creating Your OAuth Credentials (For Personal Gmail Users)

If you're using OAuth instead of ADC, you need to create your own OAuth credentials in Google Cloud Console. This is a one-time setup that takes about 5 minutes.

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click the project dropdown at the top of the page
3. Click **New Project**
4. Enter a project name (e.g., "Workspace MCP")
5. Click **Create**
6. Wait for the project to be created, then select it from the dropdown

### Step 2: Enable APIs

1. Go to **APIs & Services** > **Library** (or [click here](https://console.cloud.google.com/apis/library))
2. Search for and enable each of these APIs:
   - **Google Drive API**
   - **Gmail API**
   - **Google Calendar API**
   - **Google Sheets API**

### Step 3: Configure OAuth Consent Screen

1. Go to **APIs & Services** > **OAuth consent screen**
2. Select **External** and click **Create**
3. Fill in the required fields:
   - **App name**: "Workspace MCP" (or any name you prefer)
   - **User support email**: Your email address
   - **Developer contact email**: Your email address
4. Click **Save and Continue**
5. On the **Scopes** page, click **Add or Remove Scopes**
6. Add these scopes (search or paste the URLs):
   - `https://www.googleapis.com/auth/drive.readonly`
   - `https://www.googleapis.com/auth/gmail.readonly`
   - `https://www.googleapis.com/auth/calendar.readonly`
   - `https://www.googleapis.com/auth/spreadsheets.readonly`
7. Click **Update**, then **Save and Continue**
8. On the **Test users** page, click **Add Users**
9. Add your own email address
10. Click **Save and Continue**, then **Back to Dashboard**

### Step 4: Create OAuth Client ID

1. Go to **APIs & Services** > **Credentials**
2. Click **+ Create Credentials** > **OAuth client ID**
3. Select **Desktop app** as the application type
4. Enter a name (e.g., "Workspace MCP Desktop")
5. Click **Create**

### Step 5: Download and Save the Credentials

1. A popup will show your Client ID and Client Secret
2. Click **Download JSON** (important: do this now, you can't download the secret later!)
3. Rename the downloaded file to `client_secret.json`
4. Move it to: `~/.config/g-workspace-mcp/client_secret.json`

**On macOS/Linux:**
```bash
mkdir -p ~/.config/g-workspace-mcp
mv ~/Downloads/client_secret_*.json ~/.config/g-workspace-mcp/client_secret.json
```

### Step 6: Run Setup

```bash
g-workspace-mcp setup --oauth
```

This will open your browser to sign in with your Google account. After authorizing, you're all set!

> **Note**: You'll see a warning that the app is "unverified". This is normal for personal OAuth apps. Click **Advanced** > **Go to Workspace MCP (unsafe)** to continue. This is safe because you created the app yourself.

---

### 5. Authenticate (ADC Method - Enterprise Users)

If you have gcloud installed and configured, run:

```bash
g-workspace-mcp setup --adc
```

This will:
1. **Check gcloud CLI** - Verify it's installed
2. **Check existing credentials** - Shows the file location and any configured `quota_project`
3. **Test API access** - Verifies your credentials have the required scopes
4. **Re-authenticate if needed** - Creates a backup of existing credentials before re-authenticating

**That's it!** If you already have gcloud set up with a quota project, you're ready to go.

---

### 6. Configure Your AI Tool

```bash
# See available options
g-workspace-mcp config

# Configure Claude Code
g-workspace-mcp config -f claude

# Configure Gemini CLI
g-workspace-mcp config -f gemini

# Get JSON config for Cursor or other tools
g-workspace-mcp config -f cursor

# Get universal JSON format for other AI IDEs
g-workspace-mcp config -f json
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
# Set up authentication (interactive - prompts to choose method)
g-workspace-mcp setup

# Set up with specific method
g-workspace-mcp setup --oauth          # OAuth flow (requires client_secret.json)
g-workspace-mcp setup --adc            # ADC/gcloud flow (for enterprise users)

# Configure MCP for AI tools (default: system-wide)
g-workspace-mcp config -f <claude|cursor|gemini|json>
g-workspace-mcp config -f claude -s project      # Project-level instead

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
      "args": ["run"]
    }
  }
}
```

**Verify installation:**

```bash
claude mcp list
```

Or use the `/mcp` command inside Claude Code to verify the server is configured.

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

### Other AI IDEs (JSON Format)

For tools not listed above, use the JSON format to get a universal configuration:

```bash
g-workspace-mcp config -f json
```

This outputs the standard MCP server configuration that works with any AI IDE:

```json
{
  "google-workspace": {
    "command": "g-workspace-mcp",
    "args": ["run"]
  }
}
```

Add this to your IDE's MCP configuration file (consult your IDE's documentation for the exact location and format).

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

### "ModuleNotFoundError: No module named 'google.auth'" or similar import errors

If you see import errors when trying to run Python files directly, **don't run source files**.
The MCP server is installed as a CLI tool. Always use:

```bash
g-workspace-mcp status   # Check authentication
g-workspace-mcp run      # Run the server
```

Do NOT try to run source files directly:
```bash
# These will fail:
python3 g_workspace_mcp/src/cli.py status  # WRONG
python3 -m g_workspace_mcp.src.cli status  # WRONG
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
