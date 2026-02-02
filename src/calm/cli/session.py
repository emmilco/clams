"""CALM session CLI commands."""

import sys

import click

from calm.orchestration import sessions as session_ops


@click.group()
def session() -> None:
    """Session handoff management commands."""
    pass


@session.command()
@click.option("--continue", "needs_continuation", is_flag=True,
              help="Mark as needing continuation")
def save(needs_continuation: bool) -> None:
    """Save handoff from stdin.

    Read handoff content from stdin and save it to the database.
    Use --continue to indicate the session needs to be continued.
    """
    # Read content from stdin
    if sys.stdin.isatty():
        click.echo("Enter handoff content (Ctrl+D to finish):")

    content = sys.stdin.read()

    if not content.strip():
        raise click.ClickException("No content provided")

    session_id = session_ops.save_session(
        content=content,
        needs_continuation=needs_continuation,
    )

    click.echo(f"Saved session: {session_id}")
    if needs_continuation:
        click.echo("Marked for continuation")


@session.command("list")
@click.option("--limit", default=10, help="Maximum sessions to show")
def list_cmd(limit: int) -> None:
    """List recent sessions."""
    sessions = session_ops.list_sessions(limit=limit)

    if not sessions:
        click.echo("No sessions found.")
        return

    click.echo(f"{'ID':<10} {'Created':<20} {'Continue':<10} {'Resumed'}")
    click.echo("-" * 60)

    for s in sessions:
        created = s.created_at.strftime("%Y-%m-%d %H:%M")
        continuation = "Yes" if s.needs_continuation else "No"
        resumed = s.resumed_at.strftime("%Y-%m-%d %H:%M") if s.resumed_at else "No"
        click.echo(f"{s.id:<10} {created:<20} {continuation:<10} {resumed}")


@session.command()
@click.argument("session_id")
def show(session_id: str) -> None:
    """Show a session's handoff content."""
    s = session_ops.get_session(session_id)

    if not s:
        raise click.ClickException(f"Session {session_id} not found")

    click.echo(f"Session: {s.id}")
    click.echo(f"Created: {s.created_at}")
    click.echo(f"Needs continuation: {s.needs_continuation}")
    if s.resumed_at:
        click.echo(f"Resumed: {s.resumed_at}")
    click.echo("")
    click.echo("--- Handoff Content ---")
    click.echo(s.handoff_content)


@session.command()
def pending() -> None:
    """Show pending handoff (if any)."""
    s = session_ops.get_pending_handoff()

    if not s:
        click.echo("No pending handoff.")
        return

    click.echo(f"Pending Session: {s.id}")
    click.echo(f"Created: {s.created_at}")
    click.echo("")
    click.echo("--- Handoff Content ---")
    click.echo(s.handoff_content)


@session.command()
@click.argument("session_id")
def resume(session_id: str) -> None:
    """Mark a session as resumed."""
    try:
        session_ops.mark_session_resumed(session_id)
        click.echo(f"Marked session {session_id} as resumed")
    except ValueError as e:
        raise click.ClickException(str(e))


@session.command("next-commands")
def next_commands() -> None:
    """Generate next commands for active tasks."""
    commands = session_ops.generate_next_commands()
    click.echo(commands)


# === Journal Subgroup ===
# Journal entries are distinct from session handoffs.
# They capture session summaries, friction points, and logs for
# the learning reflection loop.


@session.group()
def journal() -> None:
    """Session journal management commands."""
    pass


@journal.command("list")
@click.option("--unreflected", is_flag=True, help="Only show unreflected entries")
@click.option("--project", "project_name", help="Filter by project name")
@click.option("--limit", default=20, help="Maximum entries (default: 20)")
def journal_list(unreflected: bool, project_name: str | None, limit: int) -> None:
    """List session journal entries."""
    from calm.orchestration.journal import list_journal_entries

    entries = list_journal_entries(
        unreflected_only=unreflected,
        project_name=project_name,
        limit=limit,
    )

    if not entries:
        click.echo("No journal entries found.")
        return

    # Table header
    click.echo(f"{'ID':<36}  {'Created':<19}  {'Project':<15}  {'Summary'}")
    click.echo("-" * 100)

    for entry in entries:
        created = entry.created_at.strftime("%Y-%m-%d %H:%M:%S")
        project = entry.project_name or "(none)"
        summary = (
            (entry.summary[:40] + "...") if len(entry.summary) > 43 else entry.summary
        )
        reflected = "" if entry.reflected_at else " [unreflected]"
        click.echo(
            f"{entry.id:<36}  {created:<19}  {project:<15}  {summary}{reflected}"
        )


@journal.command("show")
@click.argument("entry_id")
@click.option("--log", is_flag=True, help="Include session log content")
def journal_show(entry_id: str, log: bool) -> None:
    """Show full details of a journal entry."""
    from calm.orchestration.journal import get_journal_entry

    entry = get_journal_entry(entry_id, include_log=log)

    if not entry:
        raise click.ClickException(f"Entry {entry_id} not found")

    click.echo(f"ID: {entry.id}")
    click.echo(f"Created: {entry.created_at}")
    click.echo(f"Project: {entry.project_name or '(none)'}")
    click.echo(f"Working Directory: {entry.working_directory}")
    click.echo(f"Reflected: {entry.reflected_at or 'No'}")
    click.echo(f"Memories Created: {entry.memories_created}")
    click.echo("")
    click.echo("--- Summary ---")
    click.echo(entry.summary)

    if entry.friction_points:
        click.echo("")
        click.echo("--- Friction Points ---")
        for point in entry.friction_points:
            click.echo(f"- {point}")

    if entry.next_steps:
        click.echo("")
        click.echo("--- Next Steps ---")
        for step in entry.next_steps:
            click.echo(f"- {step}")

    if log and entry.session_log:
        click.echo("")
        click.echo("--- Session Log ---")
        click.echo(entry.session_log)
