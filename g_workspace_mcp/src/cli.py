"""
CLI for Google Workspace MCP Server.

Provides:
- setup: Run gcloud auth for Application Default Credentials
- serve: Start the MCP server
- config: Print MCP configuration for Claude Code/Cursor
"""

import json
import shutil
import subprocess
import sys

import click
from rich.console import Console
from rich.panel import Panel

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


# All scopes needed - includes cloud-platform to not break other GCP tools
REQUIRED_SCOPES = [
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/cloud-platform",  # For Claude Code/Vertex and other GCP tools
]


def _run_gcloud_auth() -> bool:
    """Run gcloud auth application-default login with all required scopes."""
    try:
        scope_arg = ",".join(REQUIRED_SCOPES)

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
def setup():
    """
    Set up Google authentication using Application Default Credentials.

    This uses the same authentication method as the analyzer tool.
    No GCP project access required - just a Google account.
    """
    console.print(Panel.fit(
        "[bold blue]Google Workspace MCP Setup[/bold blue]",
        border_style="blue"
    ))

    # Step 1: Check gcloud CLI
    console.print(f"\n[yellow]Step 1:[/yellow] Checking gcloud CLI installation")

    if _check_gcloud_installed():
        console.print("  [green]✓[/green] gcloud CLI is installed")
    else:
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

  After installing, run: [bold]g-workspace-mcp setup[/bold]
""")
        sys.exit(1)

    # Step 2: Test Workspace API access
    console.print(f"\n[yellow]Step 2:[/yellow] Testing Google Workspace API access")

    success, error_type = _test_workspace_api_access()

    if success:
        console.print("  [green]✓[/green] Workspace APIs accessible!")
        console.print(f"\n[green]Setup complete![/green]")
        console.print(f"\nRun [bold]g-workspace-mcp config[/bold] to get MCP configuration")
        return

    # Handle different error types
    if error_type == "no_adc":
        console.print("  [yellow]![/yellow] No authentication found")
        console.print("\n  You need to authenticate with Google.")

    elif error_type == "insufficient_scopes":
        console.print("  [yellow]![/yellow] Missing required scopes")
        console.print("\n  Your current authentication doesn't include Workspace API scopes.")
        console.print("  Re-authentication is needed to add: drive, gmail, calendar, sheets")
        console.print("  [dim](cloud-platform scope will also be included to not break other tools)[/dim]")

    elif error_type == "api_not_enabled":
        console.print("  [red]✗[/red] API not enabled on quota project")
        console.print("""
  Your quota project doesn't have Google Workspace APIs enabled.

  [bold]Option 1:[/bold] Change quota project to one with APIs enabled:
    gcloud auth application-default set-quota-project <PROJECT_WITH_APIS>

  [bold]Option 2:[/bold] Enable APIs on your current quota project (if you have access)

  [dim]For Red Hat users: try 'redhat-ai-analysis' as the quota project[/dim]
""")
        sys.exit(1)

    else:
        console.print(f"  [red]✗[/red] API test failed: {error_type}")
        console.print("  Try running setup again or check your network connection")
        sys.exit(1)

    # Step 3: Ask for approval and run authentication
    console.print(f"\n[yellow]Step 3:[/yellow] Authentication required")

    if not click.confirm("Do you want to authenticate now?", default=True):
        console.print("\n[yellow]Cancelled.[/yellow]")
        console.print("Run [bold]g-workspace-mcp setup[/bold] when ready to authenticate")
        sys.exit(0)

    console.print("\n  Opening browser for authentication...")
    console.print("  [dim](Sign in with your Google account)[/dim]\n")

    if _run_gcloud_auth():
        # Verify it worked
        success, _ = _test_workspace_api_access()
        if success:
            console.print("\n  [green]✓[/green] Authentication successful!")
            console.print(f"\n[green]Setup complete![/green]")
            console.print(f"\nRun [bold]g-workspace-mcp config[/bold] to get MCP configuration")
        else:
            console.print("\n  [yellow]![/yellow] Authentication completed but API test failed")
            console.print("  This might be a quota project issue. Check:")
            console.print("    cat ~/.config/gcloud/application_default_credentials.json | grep quota")
            sys.exit(1)
    else:
        console.print("\n  [red]✗[/red] Authentication failed or was cancelled")
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
@click.option("--format", "-f", "output_format", type=click.Choice(["claude", "cursor", "gemini", "json"]), default=None, help="Target AI tool: claude, cursor, gemini, or json")
@click.option("--scope", "-s", type=click.Choice(["user", "project"]), default="user", help="Scope: user (system-wide) or project (current directory)")
def config(output_format: str, scope: str):
    """
    Configure MCP for AI tools.

    Requires --format/-f to specify the target tool.
    """
    # Show help if no format specified
    if output_format is None:
        console.print(Panel.fit(
            "[bold blue]MCP Configuration[/bold blue]",
            border_style="blue"
        ))
        console.print("\n[yellow]Usage:[/yellow] g-workspace-mcp config -f <format>\n")
        console.print("[yellow]Available formats:[/yellow]")
        console.print("  [bold]claude[/bold]   - Configure Claude Code (runs 'claude mcp add' automatically)")
        console.print("  [bold]gemini[/bold]   - Configure Gemini CLI (runs 'gemini mcp add' automatically)")
        console.print("  [bold]cursor[/bold]   - Show JSON config for Cursor (manual copy)")
        console.print("  [bold]json[/bold]     - Raw JSON output for other tools")
        console.print("\n[yellow]Options:[/yellow]")
        console.print("  [bold]-s, --scope[/bold]  user (system-wide) or project (current directory)")
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
                console.print("Verify with: [bold]/mcp[/bold] command inside Claude Code")
            else:
                console.print("\n[red]✗[/red] Failed to add MCP server")
                sys.exit(1)
        else:
            console.print("\n[yellow]Cancelled.[/yellow]")

    elif output_format == "cursor":
        console.print("\n[bold]Cursor Configuration[/bold]")
        console.print("Add to Cursor MCP settings:\n")

        config_json = {
            "google-workspace": {
                "command": cmd_path,
                "args": ["run"]
            }
        }
        console.print_json(json.dumps(config_json, indent=2))

    elif output_format == "gemini":
        # Check if gemini CLI is installed
        gemini_path = shutil.which("gemini")
        if not gemini_path:
            console.print("\n[red]Error:[/red] Gemini CLI not found.")
            console.print("Install it with: [bold]npm install -g @google/gemini-cli[/bold]")
            sys.exit(1)

        # Build the command
        scope_arg = "-s user" if scope == "user" else ""
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
        config_json = {
            "command": cmd_path,
            "args": ["run"],
            "env": {}
        }
        print(json.dumps(config_json))


@main.command()
def status():
    """
    Check authentication status.

    Shows whether gcloud and Application Default Credentials are configured.
    """
    console.print(Panel.fit(
        "[bold blue]Google Workspace MCP Status[/bold blue]",
        border_style="blue"
    ))

    # Check gcloud CLI
    console.print(f"\n[yellow]gcloud CLI:[/yellow]")
    if _check_gcloud_installed():
        gcloud_path = shutil.which("gcloud")
        console.print(f"  [green]✓[/green] Installed at {gcloud_path}")
    else:
        console.print("  [red]✗[/red] Not installed - run 'g-workspace-mcp setup' for instructions")
        return

    # Check ADC
    console.print(f"\n[yellow]Authentication:[/yellow]")
    if _check_adc_configured():
        console.print("  [green]✓[/green] Application Default Credentials configured")
        console.print("  [green]✓[/green] Ready to use!")
    else:
        console.print("  [red]✗[/red] Not authenticated")
        console.print("  Run: [bold]g-workspace-mcp setup[/bold]")


if __name__ == "__main__":
    main()
