"""CALM review CLI commands."""

import sqlite3

import click

from calm.orchestration import reviews as review_ops

REVIEW_TYPES = ["spec", "proposal", "code", "bugfix"]
REVIEW_RESULTS = ["approved", "changes_requested"]


@click.group()
def review() -> None:
    """Review management commands."""
    pass


@review.command()
@click.argument("task_id")
@click.argument("review_type", type=click.Choice(REVIEW_TYPES))
@click.argument("result", type=click.Choice(REVIEW_RESULTS))
@click.option("--worker", "worker_id", help="Worker ID who performed the review")
@click.option("--notes", help="Reviewer notes")
def record(
    task_id: str,
    review_type: str,
    result: str,
    worker_id: str | None,
    notes: str | None,
) -> None:
    """Record a review result.

    If changes_requested, clears previous reviews to restart the cycle.
    """
    try:
        review_ops.record_review(
            task_id=task_id,
            review_type=review_type,
            result=result,
            worker_id=worker_id,
            notes=notes,
        )
        click.echo(f"Recorded {review_type} review: {result}")
        if result == "changes_requested":
            click.echo("Previous reviews cleared - review cycle restarted")
    except ValueError as e:
        raise click.ClickException(str(e))
    except sqlite3.IntegrityError:
        msg = f"Task '{task_id}' not found. "
        msg += "Create the task first with 'calm task create'."
        raise click.ClickException(msg)


@review.command("list")
@click.argument("task_id")
@click.argument("review_type", required=False)
def list_cmd(task_id: str, review_type: str | None) -> None:
    """List reviews for a task."""
    reviews = review_ops.list_reviews(task_id, review_type=review_type)

    if not reviews:
        click.echo("No reviews found.")
        return

    click.echo(f"{'ID':<5} {'Type':<10} {'Result':<18} {'Worker':<25} {'Date'}")
    click.echo("-" * 80)

    for r in reviews:
        worker = r.worker_id or "N/A"
        date = r.created_at.strftime("%Y-%m-%d %H:%M")
        click.echo(
            f"{r.id:<5} {r.review_type:<10} {r.result:<18} {worker:<25} {date}"
        )


@review.command()
@click.argument("task_id")
@click.argument("review_type", type=click.Choice(REVIEW_TYPES))
def check(task_id: str, review_type: str) -> None:
    """Check if review requirements are met (2 approved reviews)."""
    passed, count = review_ops.check_reviews(task_id, review_type)

    if passed:
        click.echo(f"PASS: {count}/2 {review_type} reviews approved")
    else:
        click.echo(f"FAIL: {count}/2 {review_type} reviews approved")
        raise SystemExit(1)


@review.command()
@click.argument("task_id")
@click.argument("review_type", required=False)
@click.confirmation_option(prompt="Are you sure you want to clear reviews?")
def clear(task_id: str, review_type: str | None) -> None:
    """Clear reviews for a task."""
    count = review_ops.clear_reviews(task_id, review_type=review_type)

    if review_type:
        click.echo(f"Cleared {count} {review_type} reviews for {task_id}")
    else:
        click.echo(f"Cleared {count} reviews for {task_id}")
