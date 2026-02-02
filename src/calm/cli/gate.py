"""CALM gate CLI commands."""

import click

from calm.orchestration.gates import (
    GATE_REQUIREMENTS,
    check_gate,
)


@click.group()
def gate() -> None:
    """Gate checking commands."""
    pass


@gate.command()
@click.argument("task_id")
@click.argument("transition")
def check(task_id: str, transition: str) -> None:
    """Run gate checks for a phase transition.

    TASK_ID is the task identifier (e.g., SPEC-001-01)
    TRANSITION is the phase transition (e.g., IMPLEMENT-CODE_REVIEW)
    """
    try:
        result = check_gate(task_id, transition)

        click.echo(f"Gate Check: {transition}")
        click.echo(f"Commit: {result.commit_sha}")
        click.echo("")

        for check_result in result.checks:
            status = "[PASS]" if check_result.passed else "[FAIL]"
            click.echo(f"{status} {check_result.name}")
            if check_result.message:
                click.echo(f"       {check_result.message}")
            if check_result.duration_seconds is not None:
                click.echo(f"       Duration: {check_result.duration_seconds:.1f}s")

        click.echo("")
        if result.passed:
            click.echo("GATE PASSED")
        else:
            click.echo("GATE FAILED")
            raise SystemExit(1)

    except ValueError as e:
        raise click.ClickException(str(e))


@gate.command("list")
def list_cmd() -> None:
    """List gate requirements by transition."""
    click.echo("Gate Requirements by Transition")
    click.echo("=" * 60)
    click.echo("")

    for transition, requirements in sorted(GATE_REQUIREMENTS.items()):
        click.echo(f"{transition}:")
        for req in requirements:
            auto = "(auto)" if req.automated else "(manual)"
            click.echo(f"  - {req.description} {auto}")
        click.echo("")
