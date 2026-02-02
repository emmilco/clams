"""CALM worker CLI commands."""

import click

from calm.orchestration import workers as worker_ops


@click.group()
def worker() -> None:
    """Worker management commands."""
    pass


@worker.command()
@click.argument("task_id")
@click.argument("role")
def start(task_id: str, role: str) -> None:
    """Register a worker and return its ID."""
    worker_id = worker_ops.start_worker(task_id, role)
    click.echo(worker_id)


@worker.command()
@click.argument("worker_id")
def complete(worker_id: str) -> None:
    """Mark a worker as completed."""
    try:
        worker_ops.complete_worker(worker_id)
        click.echo(f"Worker {worker_id} marked as completed")
    except ValueError as e:
        raise click.ClickException(str(e))


@worker.command()
@click.argument("worker_id")
@click.option("--reason", help="Failure reason")
def fail(worker_id: str, reason: str | None) -> None:
    """Mark a worker as failed."""
    try:
        worker_ops.fail_worker(worker_id, reason=reason)
        click.echo(f"Worker {worker_id} marked as failed")
    except ValueError as e:
        raise click.ClickException(str(e))


@worker.command("list")
@click.option(
    "--status",
    type=click.Choice(["active", "completed", "failed", "session_ended"]),
    help="Filter by status",
)
def list_cmd(status: str | None) -> None:
    """List workers."""
    workers = worker_ops.list_workers(status=status)

    if not workers:
        click.echo("No workers found.")
        return

    click.echo(f"{'ID':<25} {'Task':<15} {'Role':<15} {'Status':<12} {'Started'}")
    click.echo("-" * 90)

    for w in workers:
        started = w.started_at.strftime("%Y-%m-%d %H:%M")
        click.echo(f"{w.id:<25} {w.task_id:<15} {w.role:<15} {w.status:<12} {started}")


@worker.command()
@click.argument("task_id")
@click.argument("role")
def context(task_id: str, role: str) -> None:
    """Get full context for a worker."""
    ctx = worker_ops.get_worker_context(task_id, role)
    click.echo(ctx)


@worker.command()
@click.argument("role")
def prompt(role: str) -> None:
    """Get the role prompt for a given role."""
    try:
        role_prompt = worker_ops.get_role_prompt(role)
        click.echo(role_prompt)
    except FileNotFoundError as e:
        raise click.ClickException(str(e))


@worker.command()
@click.option("--max-age", default=2, help="Maximum age in hours (default: 2)")
def cleanup(max_age: int) -> None:
    """Mark stale workers as session_ended."""
    count = worker_ops.cleanup_stale_workers(max_age_hours=max_age)
    click.echo(f"Marked {count} stale workers as session_ended")
