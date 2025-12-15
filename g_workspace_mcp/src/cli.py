"""
CLI for Google Workspace MCP Server.

Provides:
- setup: Authenticate with Google (OAuth or ADC)
- serve: Start the MCP server
- config: Print MCP configuration for Claude Code/Cursor
"""

import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

# Import shared constants from auth module (single source of truth)
from g_workspace_mcp.src.auth.google_oauth import (
    CLIENT_SECRET_FILE,
    CONFIG_DIR,
    SCOPES,
    TOKEN_FILE,
)

console = Console()


@click.group()
@click.version_option(version="0.1.0")
def main():
    """Google Workspace MCP Server CLI."""
    pass


def _check_gcloud_installed() -> bool:
    """Check if gcloud CLI is installed."""
    return shutil.which("gcloud") is not None


def _check_adc_configured() -> bool:
    """Check if Application Default Credentials are configured."""
    try:
        from g_workspace_mcp.src.auth.google_oauth import get_auth

        return get_auth().is_authenticated()
    except Exception:
        return False


def _get_adc_file_path() -> Path:
    """Get the path to the Application Default Credentials file."""
    return Path.home() / ".config" / "gcloud" / "application_default_credentials.json"


def _read_adc_file() -> dict | None:
    """
    Read and parse the ADC file.

    Returns:
        Dictionary with ADC contents, or None if file doesn't exist or can't be read.
    """
    adc_path = _get_adc_file_path()
    if not adc_path.exists():
        return None

    try:
        with open(adc_path) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _backup_adc_file() -> Path | None:
    """
    Create a timestamped backup of the ADC file.

    Returns:
        Path to the backup file, or None if no file to backup.
    """
    adc_path = _get_adc_file_path()
    if not adc_path.exists():
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = adc_path.with_suffix(f".json.backup.{timestamp}")

    try:
        shutil.copy2(adc_path, backup_path)
        return backup_path
    except OSError:
        return None


def _test_workspace_api_access() -> tuple[bool, str]:
    """
    Test if current ADC has proper scopes for Workspace APIs.

    Returns:
        Tuple of (success, error_type) where error_type is:
        - "" if success
        - "no_adc" if no credentials
        - "insufficient_scopes" if scopes are missing
        - "api_not_enabled" if quota project issue
        - "other" for other errors
    """
    try:
        from g_workspace_mcp.src.auth.google_oauth import get_auth

        # Clear any cached credentials to get fresh state
        get_auth().clear_cache()

        # Try to list 1 file from Drive as a test
        service = get_auth().get_service("drive", "v3")
        service.files().list(pageSize=1, fields="files(id)").execute()
        return (True, "")
    except Exception as e:
        error_str = str(e).lower()
        if "insufficient authentication scopes" in error_str:
            return (False, "insufficient_scopes")
        elif "api has not been used" in error_str or "api is disabled" in error_str:
            return (False, "api_not_enabled")
        elif "default credentials" in error_str or "could not automatically determine" in error_str:
            return (False, "no_adc")
        else:
            return (False, "other")


# ADC scopes: workspace scopes + cloud-platform (to not break other GCP tools)
ADC_EXTRA_SCOPE = "https://www.googleapis.com/auth/cloud-platform"


def _run_gcloud_auth() -> bool:
    """Run gcloud auth application-default login with all required scopes."""
    try:
        # Use shared SCOPES + cloud-platform for ADC
        adc_scopes = list(SCOPES) + [ADC_EXTRA_SCOPE]
        scope_arg = ",".join(adc_scopes)

        console.print("  [dim]Scopes: drive, gmail, calendar, sheets, cloud-platform[/dim]")

        result = subprocess.run(
            ["gcloud", "auth", "application-default", "login", f"--scopes={scope_arg}"],
            check=False,
        )
        return result.returncode == 0
    except Exception as e:
        console.print(f"  [red]Error running gcloud: {e}[/red]")
        return False


@main.command()
@click.option(
    "--oauth", "auth_method", flag_value="oauth", help="Use OAuth authentication (recommended)"
)
@click.option(
    "--adc", "auth_method", flag_value="adc", help="Use Application Default Credentials (gcloud)"
)
@click.option(
    "--client-secret", type=click.Path(exists=True), help="Path to client_secret.json for OAuth"
)
def setup(auth_method: str | None, client_secret: str | None):
    """
    Set up Google authentication.

    Two authentication methods are available:

    \b
    OAuth (recommended):
      - Just sign in with your Google account
      - No gcloud CLI needed
      - Works with personal Gmail and Google Workspace accounts
      - Tokens stored locally in ~/.config/g-workspace-mcp/

    \b
    ADC (Application Default Credentials):
      - Uses gcloud CLI
      - For users who already have gcloud configured
      - Requires a quota project with Workspace APIs enabled
    """
    console.print(
        Panel.fit("[bold blue]Google Workspace MCP Setup[/bold blue]", border_style="blue")
    )

    # Step 1: Check existing authentication
    console.print("\n[yellow]Step 1:[/yellow] Checking existing authentication")

    from g_workspace_mcp.src.auth.google_oauth import get_auth

    auth = get_auth()
    has_oauth = auth.has_oauth_token()
    has_adc = auth.has_adc()

    if has_oauth:
        console.print("  [green]✓[/green] OAuth token found")
        console.print(f"      [dim]{TOKEN_FILE}[/dim]")
    if has_adc:
        console.print("  [green]✓[/green] ADC credentials found")

    # If user explicitly requested a specific method, skip the "already working" check
    if auth_method is not None:
        console.print(f"\n  [cyan]ℹ[/cyan] Using requested method: {auth_method}")
    elif has_oauth or has_adc:
        # Test if current auth works (only if no explicit method requested)
        console.print("\n[yellow]Step 2:[/yellow] Testing Google Workspace API access")
        success, error_type = _test_workspace_api_access()

        if success:
            console.print("  [green]✓[/green] Workspace APIs accessible!")
            console.print("\n[green]Setup complete![/green]")
            console.print("\nRun [bold]g-workspace-mcp config[/bold] to get MCP configuration")
            return

        console.print(f"  [yellow]![/yellow] API test failed: {error_type}")
        console.print("  Re-authentication needed.")

    # Step 2/3: Choose authentication method
    if auth_method is None:
        console.print("\n[yellow]Step 2:[/yellow] Choose authentication method\n")
        console.print("  [bold][1] OAuth[/bold] [green](recommended)[/green]")
        console.print("      Sign in with your Google account via browser")
        console.print("      No gcloud CLI needed, works with any Google account")
        console.print("")
        console.print("  [bold][2] ADC[/bold] (Application Default Credentials)")
        console.print("      Uses gcloud CLI, requires quota project with APIs enabled")
        console.print("      For advanced users with existing gcloud setup")
        console.print("")

        choice = click.prompt("Choose method", type=click.Choice(["1", "2"]), default="1")
        auth_method = "oauth" if choice == "1" else "adc"

    # OAuth flow
    if auth_method == "oauth":
        _run_oauth_setup(client_secret)

    # ADC flow
    else:
        _run_adc_setup()


def _run_oauth_setup(client_secret_path: str | None):
    """Run OAuth authentication setup."""
    from g_workspace_mcp.src.auth.google_oauth import run_oauth_flow

    console.print("\n[yellow]OAuth Setup[/yellow]")

    # Check for client secret
    secret_path = Path(client_secret_path) if client_secret_path else CLIENT_SECRET_FILE

    if not secret_path.exists():
        # Check if user has a client secret file somewhere
        console.print("\n  [yellow]![/yellow] Client secret file not found")
        console.print(f"      Expected at: [dim]{CLIENT_SECRET_FILE}[/dim]")
        console.print("""
  To use OAuth, you need a client_secret.json file from Google Cloud Console:

  1. Go to https://console.cloud.google.com/
  2. Create a project (or select existing)
  3. Go to APIs & Services > Credentials
  4. Create OAuth Client ID (Desktop app)
  5. Download the JSON file
  6. Copy it to: [bold]~/.config/g-workspace-mcp/client_secret.json[/bold]

  Or run: [bold]g-workspace-mcp setup --client-secret /path/to/your/file.json[/bold]
""")
        sys.exit(1)

    # Copy client secret to config dir if not already there
    if client_secret_path and Path(client_secret_path) != CLIENT_SECRET_FILE:
        import os
        import stat

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(client_secret_path, CLIENT_SECRET_FILE)
        # Set secure permissions (600 - owner read/write only)
        os.chmod(CLIENT_SECRET_FILE, stat.S_IRUSR | stat.S_IWUSR)
        console.print(f"  [green]✓[/green] Copied client secret to {CLIENT_SECRET_FILE}")
        secret_path = CLIENT_SECRET_FILE

    console.print("  [green]✓[/green] Client secret found")
    console.print("\n  Opening browser for authentication...")
    console.print("  [dim](Sign in with your Google account and authorize access)[/dim]\n")

    if run_oauth_flow(secret_path):
        # Verify it worked
        success, _ = _test_workspace_api_access()
        if success:
            console.print("\n  [green]✓[/green] Authentication successful!")
            console.print(f"  [green]✓[/green] Token saved to {TOKEN_FILE}")
            console.print("\n[green]Setup complete![/green]")
            console.print("\nRun [bold]g-workspace-mcp config[/bold] to get MCP configuration")
        else:
            console.print("\n  [yellow]![/yellow] Authentication completed but API test failed")
            console.print("  The APIs may not be enabled in your Google Cloud project.")
            sys.exit(1)
    else:
        console.print("\n  [red]✗[/red] Authentication failed or was cancelled")
        sys.exit(1)


def _run_adc_setup():
    """Run ADC (gcloud) authentication setup."""
    console.print("\n[yellow]ADC Setup[/yellow]")

    # Check gcloud CLI
    if not _check_gcloud_installed():
        console.print("  [red]✗[/red] gcloud CLI not found")
        console.print("""
  Please install the Google Cloud CLI:

  [bold]macOS:[/bold]
    brew install --cask google-cloud-sdk

  [bold]Linux (Fedora/RHEL):[/bold]
    sudo dnf install google-cloud-cli

  [bold]Linux (Ubuntu/Debian):[/bold]
    sudo apt-get install google-cloud-cli

  [bold]Or download from:[/bold]
    https://cloud.google.com/sdk/docs/install

  Alternatively, use OAuth instead: [bold]g-workspace-mcp setup --oauth[/bold]
""")
        sys.exit(1)

    console.print("  [green]✓[/green] gcloud CLI is installed")

    # Check existing ADC
    adc_path = _get_adc_file_path()
    existing_adc = _read_adc_file()
    existing_quota_project = None

    if existing_adc:
        console.print(f"  [green]✓[/green] Existing ADC found at {adc_path}")
        existing_quota_project = existing_adc.get("quota_project_id")
        if existing_quota_project:
            console.print(f"  [cyan]ℹ[/cyan] Quota project: [bold]{existing_quota_project}[/bold]")

    # Backup before making changes
    backup_path = None
    if existing_adc:
        backup_path = _backup_adc_file()
        if backup_path:
            console.print(f"  [cyan]ℹ[/cyan] Backed up to: [dim]{backup_path}[/dim]")

    if not click.confirm("\nDo you want to authenticate now?", default=True):
        console.print("\n[yellow]Cancelled.[/yellow]")
        sys.exit(0)

    console.print("\n  Opening browser for authentication...")
    console.print("  [dim](Sign in with your Google account)[/dim]\n")

    if _run_gcloud_auth():
        # Verify it worked
        success, error_type = _test_workspace_api_access()
        if success:
            console.print("\n  [green]✓[/green] Authentication successful!")
            console.print("\n[green]Setup complete![/green]")
            console.print("\nRun [bold]g-workspace-mcp config[/bold] to get MCP configuration")
        else:
            console.print("\n  [yellow]![/yellow] Authentication completed but API test failed")
            if error_type == "api_not_enabled":
                console.print("  This is likely a quota project issue.")
                console.print("\n  Set a quota project with Workspace APIs enabled:")
                console.print(
                    "    [bold]gcloud auth application-default set-quota-project <PROJECT>[/bold]"
                )
            if existing_quota_project:
                console.print(
                    f"\n  Your previous quota project was: [bold]{existing_quota_project}[/bold]"
                )
            sys.exit(1)
    else:
        console.print("\n  [red]✗[/red] Authentication failed or was cancelled")
        if backup_path:
            console.print(f"\n  [cyan]ℹ[/cyan] Backup available at: [dim]{backup_path}[/dim]")
        sys.exit(1)


@main.command()
def run():
    """
    Run the MCP server (stdio mode).

    This is called by Claude Code automatically.
    You don't need to run this manually.
    """
    from g_workspace_mcp.src.main import main as run_server

    run_server()


@main.command()
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["claude", "cursor", "gemini", "json"]),
    default=None,
    help="Target AI tool: claude, cursor, gemini, or json",
)
@click.option(
    "--scope",
    "-s",
    type=click.Choice(["user", "project"]),
    default="user",
    help="Scope: user (system-wide, default) or project (current directory)",
)
def config(output_format: str, scope: str):
    """
    Configure MCP for AI tools.

    Requires --format/-f to specify the target tool.
    """
    # Show help if no format specified
    if output_format is None:
        console.print(Panel.fit("[bold blue]MCP Configuration[/bold blue]", border_style="blue"))
        console.print("\n[yellow]Usage:[/yellow] g-workspace-mcp config -f <format>\n")
        console.print("[yellow]Available formats:[/yellow]")
        console.print(
            "  [bold]claude[/bold]   - Configure Claude Code (runs 'claude mcp add' automatically)"
        )
        console.print(
            "  [bold]gemini[/bold]   - Configure Gemini CLI (runs 'gemini mcp add' automatically)"
        )
        console.print("  [bold]cursor[/bold]   - Show JSON config for Cursor (manual copy)")
        console.print("  [bold]json[/bold]     - Raw JSON output for other tools")
        console.print("\n[yellow]Options:[/yellow]")
        console.print(
            "  [bold]-s, --scope[/bold]  user (system-wide, default) or project (current directory)"
        )
        console.print("\n[yellow]Examples:[/yellow]")
        console.print("  g-workspace-mcp config -f claude")
        console.print("  g-workspace-mcp config -f gemini -s project")
        console.print("  g-workspace-mcp config -f cursor")
        return

    # Find the installed command path
    cmd_path = shutil.which("g-workspace-mcp")
    if not cmd_path:
        cmd_path = "g-workspace-mcp"

    if output_format == "claude":
        # Check if claude CLI is installed
        claude_path = shutil.which("claude")
        if not claude_path:
            console.print("\n[red]Error:[/red] Claude Code CLI not found.")
            console.print("Install Claude Code from: [bold]https://claude.ai/download[/bold]")
            sys.exit(1)

        # Build the command
        scope_desc = "system-wide" if scope == "user" else "project-level"

        cmd = ["claude", "mcp", "add", "google-workspace", "-s", scope, "--", cmd_path, "run"]

        console.print(f"\n[bold]Claude Code Configuration ({scope_desc})[/bold]")
        console.print("\nThis will run the following command:\n")
        console.print(f"  [cyan]{' '.join(cmd)}[/cyan]\n")

        if click.confirm("Do you want to proceed?", default=True):
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                console.print("\n[green]✓[/green] MCP server added to Claude Code!")
                console.print("Verify with: [bold]claude mcp list[/bold]")
            else:
                console.print("\n[red]✗[/red] Failed to add MCP server")
                sys.exit(1)
        else:
            console.print("\n[yellow]Cancelled.[/yellow]")

    elif output_format == "cursor":
        console.print("\n[bold]Cursor Configuration[/bold]")
        console.print("Add to Cursor MCP settings:\n")

        config_json = {"google-workspace": {"command": cmd_path, "args": ["run"]}}
        console.print_json(json.dumps(config_json, indent=2))

    elif output_format == "gemini":
        # Check if gemini CLI is installed
        gemini_path = shutil.which("gemini")
        if not gemini_path:
            console.print("\n[red]Error:[/red] Gemini CLI not found.")
            console.print("Install it with: [bold]npm install -g @google/gemini-cli[/bold]")
            sys.exit(1)

        # Build the command
        scope_desc = "system-wide" if scope == "user" else "project-level"

        cmd = ["gemini", "mcp", "add"]
        if scope == "user":
            cmd.extend(["-s", "user"])
        cmd.extend(["google-workspace", cmd_path, "run"])

        console.print(f"\n[bold]Gemini CLI Configuration ({scope_desc})[/bold]")
        console.print("\nThis will run the following command:\n")
        console.print(f"  [cyan]{' '.join(cmd)}[/cyan]\n")

        if click.confirm("Do you want to proceed?", default=True):
            result = subprocess.run(cmd, check=False)
            if result.returncode == 0:
                console.print("\n[green]✓[/green] MCP server added to Gemini CLI!")
                console.print("Verify with: [bold]gemini mcp list[/bold]")
            else:
                console.print("\n[red]✗[/red] Failed to add MCP server")
                sys.exit(1)
        else:
            console.print("\n[yellow]Cancelled.[/yellow]")

    elif output_format == "json":
        # Raw JSON for programmatic use
        config_json = {"command": cmd_path, "args": ["run"], "env": {}}
        print(json.dumps(config_json))


@main.command()
def status():
    """
    Check authentication status.

    Shows OAuth token and ADC status.
    """
    console.print(
        Panel.fit("[bold blue]Google Workspace MCP Status[/bold blue]", border_style="blue")
    )

    from g_workspace_mcp.src.auth.google_oauth import get_auth

    auth = get_auth()

    # Check OAuth
    console.print("\n[yellow]OAuth:[/yellow]")
    if TOKEN_FILE.exists():
        if auth.has_oauth_token():
            console.print("  [green]✓[/green] Token valid")
            console.print(f"      [dim]{TOKEN_FILE}[/dim]")
        else:
            console.print("  [yellow]![/yellow] Token expired or invalid")
            console.print(f"      [dim]{TOKEN_FILE}[/dim]")
    else:
        console.print("  [dim]  No OAuth token[/dim]")

    # Check ADC
    console.print("\n[yellow]ADC (gcloud):[/yellow]")
    if _check_gcloud_installed():
        gcloud_path = shutil.which("gcloud")
        console.print(f"  [green]✓[/green] gcloud installed at {gcloud_path}")

        adc_path = _get_adc_file_path()
        if adc_path.exists():
            if auth.has_adc():
                console.print("  [green]✓[/green] ADC credentials valid")
            else:
                console.print("  [yellow]![/yellow] ADC credentials expired or invalid")
            console.print(f"      [dim]{adc_path}[/dim]")

            existing_adc = _read_adc_file()
            if existing_adc and existing_adc.get("quota_project_id"):
                console.print(f"  [cyan]ℹ[/cyan] Quota project: {existing_adc['quota_project_id']}")
        else:
            console.print("  [dim]  No ADC credentials[/dim]")
    else:
        console.print("  [dim]  gcloud not installed[/dim]")

    # Overall status
    console.print("\n[yellow]API Access:[/yellow]")
    success, error_type = _test_workspace_api_access()
    if success:
        console.print("  [green]✓[/green] Workspace APIs accessible!")
        console.print("  [green]✓[/green] Ready to use!")
    else:
        console.print(f"  [red]✗[/red] API test failed: {error_type}")
        console.print("  Run: [bold]g-workspace-mcp setup[/bold]")


@main.command()
@click.option("--oauth", "logout_oauth", is_flag=True, help="Remove OAuth token only")
@click.option(
    "--all", "logout_all", is_flag=True, help="Remove OAuth token and show ADC instructions"
)
def logout(logout_oauth: bool, logout_all: bool):
    """
    Remove stored authentication tokens.

    By default, removes the OAuth token. Use --all to also get instructions
    for clearing ADC credentials.
    """
    console.print(
        Panel.fit("[bold blue]Google Workspace MCP Logout[/bold blue]", border_style="blue")
    )

    removed_something = False

    # Remove OAuth token
    if TOKEN_FILE.exists():
        TOKEN_FILE.unlink()
        console.print("\n  [green]✓[/green] Removed OAuth token")
        console.print(f"      [dim]{TOKEN_FILE}[/dim]")
        removed_something = True
    else:
        console.print("\n  [dim]  No OAuth token found[/dim]")

    # Show ADC instructions if --all
    if logout_all:
        adc_path = _get_adc_file_path()
        if adc_path.exists():
            console.print("\n  [cyan]ℹ[/cyan] To remove ADC credentials, run:")
            console.print("      [bold]gcloud auth application-default revoke[/bold]")
            console.print(f"\n  Or manually delete: [dim]{adc_path}[/dim]")
        else:
            console.print("\n  [dim]  No ADC credentials found[/dim]")

    if removed_something:
        console.print("\n[green]Logged out successfully.[/green]")
        console.print("\nRun [bold]g-workspace-mcp setup[/bold] to re-authenticate.")
    elif not logout_all:
        console.print("\n[yellow]Nothing to remove.[/yellow]")
        console.print("Use [bold]--all[/bold] to see ADC logout instructions.")


if __name__ == "__main__":
    main()
