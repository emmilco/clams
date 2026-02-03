"""CALM install command.

Provides the CLI interface for installing CALM.
"""

from __future__ import annotations

import sys
from pathlib import Path

import click


@click.command("install")
@click.option(
    "--dev",
    is_flag=True,
    help="Install in development mode (use current directory for paths)",
)
@click.option(
    "--skip-qdrant",
    is_flag=True,
    help="Skip Qdrant setup (user will manage separately)",
)
@click.option(
    "--skip-hooks",
    is_flag=True,
    help="Skip hook registration",
)
@click.option(
    "--skip-mcp",
    is_flag=True,
    help="Skip MCP server registration",
)
@click.option(
    "--skip-server",
    is_flag=True,
    help="Skip starting the CALM server daemon",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing files",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be done without making changes",
)
@click.option(
    "-y",
    "--yes",
    is_flag=True,
    help="Skip confirmation prompts",
)
@click.option(
    "-v",
    "--verbose",
    is_flag=True,
    help="Verbose output",
)
def install_cmd(
    dev: bool,
    skip_qdrant: bool,
    skip_hooks: bool,
    skip_mcp: bool,
    skip_server: bool,
    force: bool,
    dry_run: bool,
    yes: bool,
    verbose: bool,
) -> None:
    """Install CALM for fresh installations.

    Creates directory structure, copies templates, registers MCP server
    and hooks, starts Qdrant container, and starts CALM server.

    Use --dev for development installations that use local paths.

    Examples:

        # Fresh install
        calm install

        # Development install (uses current directory)
        calm install --dev

        # Skip services (manage separately)
        calm install --skip-qdrant --skip-server

        # Preview changes without making them
        calm install --dry-run
    """
    from calm.install import InstallOptions, install

    # Confirmation prompt (unless -y or --dry-run)
    if not yes and not dry_run:
        click.echo("This will install CALM to ~/.calm/")
        click.echo("")
        if dev:
            click.echo(f"  Development mode: paths will point to {Path.cwd()}")
        if not skip_qdrant:
            click.echo("  Will create/start Qdrant Docker container")
        if not skip_mcp:
            click.echo("  Will register MCP server in ~/.claude.json")
        if not skip_hooks:
            click.echo("  Will register hooks in ~/.claude/settings.json")
        click.echo("")
        if not click.confirm("Continue?"):
            click.echo("Aborted.")
            sys.exit(0)
        click.echo("")

    # Build options
    options = InstallOptions(
        dev_mode=dev,
        skip_qdrant=skip_qdrant,
        skip_hooks=skip_hooks,
        skip_mcp=skip_mcp,
        skip_server=skip_server,
        force=force,
        dry_run=dry_run,
        verbose=verbose,
        dev_directory=Path.cwd() if dev else None,
    )

    # Run installation
    result = install(options)

    # Exit with appropriate code
    if result.status == "failed":
        sys.exit(1)
    elif result.status == "partial":
        sys.exit(2)
    else:
        sys.exit(0)
