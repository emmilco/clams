"""Installation step orchestration.

Coordinates the execution of individual installation steps.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

from calm.config import CALM_HOME, settings
from calm.install import InstallOptions, InstallResult, InstallStep
from calm.install.config_merge import register_hooks, register_mcp_server
from calm.install.dependencies import check_all_dependencies
from calm.install.docker import ensure_qdrant_running
from calm.install.templates import copy_all_templates, create_directory_structure

if TYPE_CHECKING:
    pass


def _get_calm_home(options: InstallOptions) -> Path:
    """Get the CALM home directory from options or default."""
    return options.calm_home or CALM_HOME


def _log(message: str, verbose: bool) -> None:
    """Print a message if verbose mode is enabled."""
    if verbose:
        print(message)


def step_check_dependencies(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Check system dependencies.

    Returns:
        True if dependencies are satisfied, False otherwise
    """
    output("[1/9] Checking dependencies...")

    checks, all_passed = check_all_dependencies(skip_docker=options.skip_qdrant)

    for check in checks:
        if check.available:
            version_str = f" ({check.found_version})" if check.found_version else ""
            output(f"  [OK] {check.name}{version_str}")
        else:
            found = check.found_version
            version_str = f" (found {found})" if found else ""
            output(f"  [MISSING] {check.name}{version_str}")
            output(f"    {check.install_hint}")

    if not all_passed:
        result.add_error(
            InstallStep.CHECK_DEPS,
            "Missing required dependencies. See above for installation instructions.",
        )
        return False

    result.add_completed(InstallStep.CHECK_DEPS)
    return True


def step_create_directories(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Create CALM directory structure."""
    output("[2/9] Creating directories...")

    calm_home = _get_calm_home(options)
    created = create_directory_structure(calm_home, dry_run=options.dry_run)

    for msg in created:
        output(f"  {msg}")

    if not created and not options.dry_run:
        output("  All directories already exist")

    result.add_completed(InstallStep.CREATE_DIRS)
    return True


def step_copy_templates(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Copy template files."""
    output("[3/9] Copying templates...")

    calm_home = _get_calm_home(options)
    copied, skipped, errors = copy_all_templates(
        calm_home,
        force=options.force,
        dry_run=options.dry_run,
    )

    for msg in copied:
        output(f"  {msg}")

    if skipped and options.verbose:
        for msg in skipped:
            output(f"  {msg}")

    if errors:
        for msg in errors:
            output(f"  ERROR: {msg}")
        result.add_error(InstallStep.COPY_TEMPLATES, "; ".join(errors))
        return False

    if not copied and skipped:
        output("  All templates already exist (use --force to overwrite)")

    result.add_completed(InstallStep.COPY_TEMPLATES)
    return True


def step_init_database(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Initialize the database."""
    output("[4/9] Initializing database...")

    if options.dry_run:
        output(f"  Would initialize database at {settings.db_path}")
        result.add_completed(InstallStep.INIT_DATABASE)
        return True

    try:
        from calm.db.schema import init_database

        calm_home = _get_calm_home(options)
        db_path = calm_home / "metadata.db"
        init_database(db_path)
        output(f"  Initialized database at {db_path}")
        result.add_completed(InstallStep.INIT_DATABASE)
        return True
    except Exception as e:
        result.add_error(InstallStep.INIT_DATABASE, str(e))
        return False


def step_start_qdrant(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Start Qdrant container."""
    if options.skip_qdrant:
        output("[5/9] Skipping Qdrant setup (--skip-qdrant)")
        result.add_skipped(InstallStep.START_QDRANT, "user requested --skip-qdrant")
        return True

    output("[5/9] Setting up Qdrant...")

    success, message = ensure_qdrant_running(dry_run=options.dry_run)

    output(f"  {message}")

    if success:
        result.add_completed(InstallStep.START_QDRANT)
        return True
    else:
        result.add_error(InstallStep.START_QDRANT, message)
        result.add_warning(
            "Qdrant setup failed. You can skip this with --skip-qdrant "
            "and manage Qdrant separately."
        )
        return False


def step_register_mcp(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Register MCP server in claude.json."""
    if options.skip_mcp:
        output("[6/9] Skipping MCP registration (--skip-mcp)")
        result.add_skipped(InstallStep.REGISTER_MCP, "user requested --skip-mcp")
        return True

    output("[6/9] Registering MCP server...")

    claude_json_path = Path.home() / ".claude.json"

    try:
        message = register_mcp_server(
            claude_json_path,
            dry_run=options.dry_run,
        )
        output(f"  {message}")
        result.add_completed(InstallStep.REGISTER_MCP)
        return True
    except Exception as e:
        result.add_error(InstallStep.REGISTER_MCP, str(e))
        return False


def step_register_hooks(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Register hooks in settings.json."""
    if options.skip_hooks:
        output("[7/9] Skipping hook registration (--skip-hooks)")
        result.add_skipped(InstallStep.REGISTER_HOOKS, "user requested --skip-hooks")
        return True

    output("[7/9] Registering hooks...")

    settings_path = Path.home() / ".claude" / "settings.json"

    try:
        message = register_hooks(settings_path, dry_run=options.dry_run)
        output(f"  {message}")
        result.add_completed(InstallStep.REGISTER_HOOKS)
        return True
    except Exception as e:
        result.add_error(InstallStep.REGISTER_HOOKS, str(e))
        return False


def step_start_server(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Start CALM server daemon."""
    if options.skip_server:
        output("[8/9] Skipping server startup (--skip-server)")
        result.add_skipped(InstallStep.START_SERVER, "user requested --skip-server")
        return True

    output("[8/9] Starting CALM server...")

    if options.dry_run:
        output("  Would start CALM server daemon")
        result.add_completed(InstallStep.START_SERVER)
        return True

    try:
        from calm.server.daemon import start_daemon

        # Get paths for output messages
        calm_home = _get_calm_home(options)
        pid_file = calm_home / "server.pid"

        # start_daemon uses settings.pid_file and settings.log_file
        start_daemon()

        output(f"  Started CALM server (PID file: {pid_file})")
        result.add_completed(InstallStep.START_SERVER)
        return True
    except Exception as e:
        # Server may already be running or other startup issue
        error_msg = str(e)
        if "already running" in error_msg.lower():
            output("  Server may already be running")
            result.add_warning("Server start failed - may already be running")
            result.add_completed(InstallStep.START_SERVER)
            return True
        result.add_error(InstallStep.START_SERVER, error_msg)
        return False


def step_verify(
    options: InstallOptions,
    result: InstallResult,
    output: Callable[[str], None],
) -> bool:
    """Verify the installation."""
    output("[9/9] Verifying installation...")

    if options.dry_run:
        output("  Would verify installation")
        result.add_completed(InstallStep.VERIFY)
        return True

    calm_home = _get_calm_home(options)
    all_good = True

    # Check directories exist
    dirs_to_check = ["roles", "workflows", "skills", "sessions"]
    for dirname in dirs_to_check:
        dir_path = calm_home / dirname
        if dir_path.exists():
            output(f"  [OK] {dir_path}")
        else:
            output(f"  [MISSING] {dir_path}")
            all_good = False

    # Check database exists
    db_path = calm_home / "metadata.db"
    if db_path.exists():
        output(f"  [OK] {db_path}")
    else:
        output(f"  [MISSING] {db_path}")
        all_good = False

    # Check config exists
    config_path = calm_home / "config.yaml"
    if config_path.exists():
        output(f"  [OK] {config_path}")
    else:
        output(f"  [MISSING] {config_path}")
        all_good = False

    if all_good:
        result.add_completed(InstallStep.VERIFY)
        return True
    else:
        result.add_error(InstallStep.VERIFY, "Some components missing")
        return False


def run_installation(options: InstallOptions) -> InstallResult:
    """Run the full installation process.

    Args:
        options: Installation options

    Returns:
        InstallResult with status and details
    """
    result = InstallResult()

    # Helper to print output
    def output(msg: str) -> None:
        print(msg)

    if options.dry_run:
        output("CALM Installation (dry run)")
        output("")
    else:
        output("CALM Installation")
        output("")

    # Run each step in order
    steps = [
        step_check_dependencies,
        step_create_directories,
        step_copy_templates,
        step_init_database,
        step_start_qdrant,
        step_register_mcp,
        step_register_hooks,
        step_start_server,
        step_verify,
    ]

    for step_fn in steps:
        success = step_fn(options, result, output)
        if not success and result.status == "failed":
            # Stop on fatal error
            break
        output("")  # Blank line between steps

    # Final status
    if options.dry_run:
        output("No changes made (dry run).")
    elif result.status == "success":
        output("Installation complete!")
        output("")
        output("Next steps:")
        output("  1. Start a new Claude Code session")
        output("  2. CALM tools will be available via mcp__calm__*")
        output("  3. Run /orchestrate to start orchestration")
    else:
        output("Installation failed. See errors above.")
        for error in result.errors:
            output(f"  - {error}")

    return result
