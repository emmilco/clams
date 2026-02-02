"""CALM status command."""

import click

from calm.config import settings


@click.group(invoke_without_command=True)
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show overall CALM system status.

    Displays:
    - Server status (running/stopped)
    - Database status
    - Configuration summary
    - Active tasks and health (with orchestration)
    """
    if ctx.invoked_subcommand is not None:
        return

    from calm.server.daemon import get_server_pid, is_server_running

    click.echo("=== CALM System Status ===")
    click.echo()

    # Server status
    click.echo("Server:")
    if is_server_running():
        pid = get_server_pid()
        click.echo(f"  Status: Running (PID: {pid})")
        click.echo(f"  URL: http://{settings.server_host}:{settings.server_port}")
    else:
        click.echo("  Status: Stopped")
    click.echo()

    # Database status
    click.echo("Database:")
    db_path = settings.db_path
    if db_path.exists():
        size_kb = db_path.stat().st_size / 1024
        click.echo(f"  Path: {db_path}")
        click.echo(f"  Size: {size_kb:.1f} KB")

        # Get table counts
        try:
            import sqlite3

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            tables = [
                ("memories", "memories"),
                ("sessions", "session_journal"),
                ("ghap_entries", "ghap_entries"),
                ("tasks", "tasks"),
            ]

            for label, table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    count = cursor.fetchone()[0]
                    click.echo(f"  {label.capitalize()}: {count}")
                except sqlite3.OperationalError:
                    pass

            conn.close()
        except Exception as e:
            click.echo(f"  Error reading database: {e}")
    else:
        click.echo("  Not initialized (run 'calm init')")
    click.echo()

    # Configuration
    click.echo("Configuration:")
    click.echo(f"  Home: {settings.home}")
    click.echo(f"  Qdrant: {settings.qdrant_url}")


@status.command()
def health() -> None:
    """Show system health status."""
    from calm.orchestration.counters import list_counters
    from calm.orchestration.workers import list_workers

    click.echo("=== System Health ===")
    click.echo()

    # Check counters
    counters = list_counters()
    merge_lock = counters.get("merge_lock", 0)
    merges_since_e2e = counters.get("merges_since_e2e", 0)
    merges_since_docs = counters.get("merges_since_docs", 0)

    # Determine health status
    if merge_lock > 0:
        status_text = "DEGRADED"
        status_color = "red"
    elif merges_since_e2e >= 12:
        status_text = "ATTENTION"
        status_color = "yellow"
    else:
        status_text = "HEALTHY"
        status_color = "green"

    click.echo(f"Status: {click.style(status_text, fg=status_color, bold=True)}")
    click.echo()

    # Counter details
    click.echo("Counters:")
    click.echo(f"  merge_lock: {merge_lock}")
    click.echo(f"  merges_since_e2e: {merges_since_e2e}")
    click.echo(f"  merges_since_docs: {merges_since_docs}")
    click.echo()

    # Active workers
    active_workers = list_workers(status="active")
    click.echo(f"Active Workers: {len(active_workers)}")
    for w in active_workers[:5]:
        click.echo(f"  - {w.id}: {w.role} on {w.task_id}")

    if len(active_workers) > 5:
        click.echo(f"  ... and {len(active_workers) - 5} more")


@status.command("worktrees")
def worktrees_cmd() -> None:
    """Show active worktrees."""
    from calm.orchestration.worktrees import list_worktrees

    worktrees = list_worktrees()

    click.echo("=== Active Worktrees ===")
    click.echo()

    if not worktrees:
        click.echo("No worktrees found.")
        return

    click.echo(f"{'Task ID':<20} {'Phase':<15} {'Type':<10} {'Path'}")
    click.echo("-" * 80)

    for wt in worktrees:
        phase = wt.phase or "N/A"
        task_type = wt.task_type or "N/A"
        click.echo(f"{wt.task_id:<20} {phase:<15} {task_type:<10} {wt.path}")


@status.command()
def tasks() -> None:
    """Show tasks grouped by phase."""
    from calm.orchestration.tasks import list_tasks

    tasks_list = list_tasks(include_done=False)

    click.echo("=== Active Tasks ===")
    click.echo()

    if not tasks_list:
        click.echo("No active tasks.")
        return

    # Group by phase
    by_phase: dict[str, list[str]] = {}
    for t in tasks_list:
        if t.phase not in by_phase:
            by_phase[t.phase] = []
        by_phase[t.phase].append(f"{t.id}: {t.title}")

    for phase, task_ids in sorted(by_phase.items()):
        click.echo(f"{phase}:")
        for task_info in task_ids:
            click.echo(f"  - {task_info}")
        click.echo()


@status.command()
def workers() -> None:
    """Show active workers."""
    from calm.orchestration.workers import list_workers

    active = list_workers(status="active")

    click.echo("=== Active Workers ===")
    click.echo()

    if not active:
        click.echo("No active workers.")
        return

    click.echo(f"{'ID':<25} {'Task':<15} {'Role':<15} {'Started'}")
    click.echo("-" * 70)

    for w in active:
        started = w.started_at.strftime("%Y-%m-%d %H:%M")
        click.echo(f"{w.id:<25} {w.task_id:<15} {w.role:<15} {started}")


@status.command()
def counters() -> None:
    """Show system counters."""
    from calm.orchestration.counters import list_counters

    counter_values = list_counters()

    click.echo("=== System Counters ===")
    click.echo()

    if not counter_values:
        click.echo("No counters found.")
        return

    click.echo(f"{'Name':<25} {'Value'}")
    click.echo("-" * 35)

    for name, value in sorted(counter_values.items()):
        click.echo(f"{name:<25} {value}")
