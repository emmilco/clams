"""CALM worktree CLI commands."""

from pathlib import Path

import click

from calm.orchestration import worktrees as worktree_ops
from calm.orchestration.project import detect_main_repo


def _warn_if_cwd_inside_worktree(task_id: str) -> None:
    """Warn if the caller's cwd was inside the removed worktree."""
    try:
        main_repo = Path(detect_main_repo())
        worktree_path = main_repo / ".worktrees" / task_id
        cwd = Path.cwd()
        if cwd == worktree_path or worktree_path in cwd.parents:
            click.echo(
                f"Warning: your shell is inside the removed worktree. "
                f"Run: cd {main_repo}",
                err=True,
            )
    except OSError:
        # cwd already invalid
        try:
            main_repo = Path(detect_main_repo())
        except Exception:
            main_repo = Path.home()
        click.echo(
            f"Warning: your shell is in a deleted directory. "
            f"Run: cd {main_repo}",
            err=True,
        )


@click.group()
def worktree() -> None:
    """Git worktree management commands."""
    pass


@worktree.command()
@click.argument("task_id")
def create(task_id: str) -> None:
    """Create a git worktree for a task."""
    try:
        result = worktree_ops.create_worktree(task_id)
        click.echo(f"Created worktree: {result.path}")
        click.echo(f"Branch: {result.branch}")
    except ValueError as e:
        raise click.ClickException(str(e))


@worktree.command("list")
def list_cmd() -> None:
    """List all worktrees."""
    worktrees = worktree_ops.list_worktrees()

    if not worktrees:
        click.echo("No worktrees found.")
        return

    click.echo(f"{'Task ID':<20} {'Phase':<15} {'Type':<10} {'Path'}")
    click.echo("-" * 80)

    for wt in worktrees:
        phase = wt.phase or "N/A"
        task_type = wt.task_type or "N/A"
        click.echo(f"{wt.task_id:<20} {phase:<15} {task_type:<10} {wt.path}")


@worktree.command()
@click.argument("task_id")
def path(task_id: str) -> None:
    """Get the worktree path for a task."""
    wt_path = worktree_ops.get_worktree_path(task_id)
    if wt_path:
        click.echo(str(wt_path))
    else:
        raise click.ClickException(f"No worktree found for task {task_id}")


@worktree.command()
@click.argument("task_id")
@click.option("--skip-sync", is_flag=True, help="Skip dependency sync after merge")
@click.option("--force", is_flag=True, help="Force merge even if merge_lock is set")
def merge(task_id: str, skip_sync: bool, force: bool) -> None:
    """Merge worktree to main and cleanup."""
    _warn_if_cwd_inside_worktree(task_id)
    try:
        sha = worktree_ops.merge_worktree(
            task_id,
            skip_sync=skip_sync,
            force=force,
        )
        click.echo(f"Merged {task_id} to main")
        click.echo(f"Commit: {sha}")
    except ValueError as e:
        raise click.ClickException(str(e))


@worktree.command()
@click.argument("task_id")
@click.confirmation_option(prompt="Are you sure you want to remove this worktree?")
def remove(task_id: str) -> None:
    """Remove a worktree without merging."""
    _warn_if_cwd_inside_worktree(task_id)
    try:
        worktree_ops.remove_worktree(task_id)
        click.echo(f"Removed worktree for {task_id}")
    except ValueError as e:
        raise click.ClickException(str(e))


@worktree.command("check-conflicts")
@click.argument("task_id")
def check_conflicts(task_id: str) -> None:
    """Check for merge conflicts without merging."""
    conflicts = worktree_ops.check_merge_conflicts(task_id)

    if not conflicts:
        click.echo("No merge conflicts detected.")
    else:
        click.echo("Merge conflicts detected:")
        for conflict in conflicts:
            click.echo(f"  - {conflict}")
        raise SystemExit(1)
