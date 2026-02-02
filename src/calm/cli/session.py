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
