"""CALM task CLI commands."""

import click

from calm.orchestration import tasks as task_ops
from calm.orchestration.phases import get_next_phases


@click.group()
def task() -> None:
    """Task management commands."""
    pass


@task.command()
@click.argument("task_id")
@click.argument("title")
@click.option("--spec", "spec_id", help="Parent spec ID")
@click.option(
    "--type",
    "task_type",
    type=click.Choice(["feature", "bug"]),
    default="feature",
    help="Task type",
)
def create(task_id: str, title: str, spec_id: str | None, task_type: str) -> None:
    """Create a new task."""
    try:
        result = task_ops.create_task(
            task_id=task_id,
            title=title,
            spec_id=spec_id,
            task_type=task_type,
        )
        click.echo(f"Created {task_type}: {task_id} (phase: {result.phase})")
    except ValueError as e:
        raise click.ClickException(str(e))


@task.command("list")
@click.option("--phase", help="Filter by phase")
@click.option(
    "--type",
    "task_type",
    type=click.Choice(["feature", "bug"]),
    help="Filter by task type",
)
@click.option("--include-done", is_flag=True, help="Include completed tasks")
def list_cmd(
    phase: str | None, task_type: str | None, include_done: bool
) -> None:
    """List tasks."""
    tasks = task_ops.list_tasks(
        phase=phase,
        task_type=task_type,
        include_done=include_done,
    )

    if not tasks:
        click.echo("No tasks found.")
        return

    click.echo(f"{'ID':<15} {'Phase':<15} {'Type':<10} {'Title'}")
    click.echo("-" * 70)

    for t in tasks:
        click.echo(f"{t.id:<15} {t.phase:<15} {t.task_type:<10} {t.title}")


@task.command()
@click.argument("task_id")
def show(task_id: str) -> None:
    """Show task details."""
    t = task_ops.get_task(task_id)
    if not t:
        raise click.ClickException(f"Task {task_id} not found")

    click.echo(f"Task: {t.id}")
    click.echo(f"Title: {t.title}")
    click.echo(f"Type: {t.task_type}")
    click.echo(f"Phase: {t.phase}")

    if t.spec_id:
        click.echo(f"Spec ID: {t.spec_id}")
    if t.specialist:
        click.echo(f"Specialist: {t.specialist}")
    if t.notes:
        click.echo(f"Notes: {t.notes}")
    if t.blocked_by:
        click.echo(f"Blocked by: {', '.join(t.blocked_by)}")
    if t.worktree_path:
        click.echo(f"Worktree: {t.worktree_path}")

    click.echo(f"Project: {t.project_path}")
    click.echo(f"Created: {t.created_at}")
    click.echo(f"Updated: {t.updated_at}")

    # Show next phases
    next_phases = get_next_phases(t.task_type, t.phase)
    if next_phases:
        click.echo(f"Next phases: {', '.join(next_phases)}")


@task.command()
@click.argument("task_id")
@click.option("--phase", help="New phase")
@click.option("--specialist", help="Specialist assignment")
@click.option("--notes", help="Task notes")
@click.option("--blocked-by", help="Comma-separated list of blocking task IDs")
def update(
    task_id: str,
    phase: str | None,
    specialist: str | None,
    notes: str | None,
    blocked_by: str | None,
) -> None:
    """Update task fields."""
    try:
        blocked_by_list = blocked_by.split(",") if blocked_by else None
        result = task_ops.update_task(
            task_id=task_id,
            phase=phase,
            specialist=specialist,
            notes=notes,
            blocked_by=blocked_by_list,
        )
        click.echo(f"Updated task {task_id} (phase: {result.phase})")
    except ValueError as e:
        raise click.ClickException(str(e))


@task.command()
@click.argument("task_id")
@click.argument("to_phase")
@click.option(
    "--gate-result",
    type=click.Choice(["pass", "fail"]),
    help="Gate check result",
)
@click.option("--gate-details", help="Gate check details")
def transition(
    task_id: str,
    to_phase: str,
    gate_result: str | None,
    gate_details: str | None,
) -> None:
    """Transition task to a new phase."""
    try:
        result = task_ops.transition_task(
            task_id=task_id,
            to_phase=to_phase,
            gate_result=gate_result,
            gate_details=gate_details,
        )
        click.echo(f"Transitioned {task_id} to {result.phase}")
    except ValueError as e:
        raise click.ClickException(str(e))


@task.command()
@click.argument("task_id")
@click.confirmation_option(prompt="Are you sure you want to delete this task?")
def delete(task_id: str) -> None:
    """Delete a task."""
    try:
        task_ops.delete_task(task_id)
        click.echo(f"Deleted task {task_id}")
    except ValueError as e:
        raise click.ClickException(str(e))
