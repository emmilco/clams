"""CALM counter CLI commands."""

import click

from calm.orchestration import counters as counter_ops


@click.group()
def counter() -> None:
    """Counter management commands."""
    pass


@counter.command("list")
def list_cmd() -> None:
    """Show all counters."""
    counters = counter_ops.list_counters()

    if not counters:
        click.echo("No counters found.")
        return

    click.echo(f"{'Name':<25} {'Value'}")
    click.echo("-" * 35)

    for name, value in sorted(counters.items()):
        click.echo(f"{name:<25} {value}")


@counter.command()
@click.argument("name")
def get(name: str) -> None:
    """Get a counter value."""
    value = counter_ops.get_counter(name)
    click.echo(value)


@counter.command("set")
@click.argument("name")
@click.argument("value", type=int)
def set_cmd(name: str, value: int) -> None:
    """Set a counter to a specific value."""
    counter_ops.set_counter(name, value)
    click.echo(f"Set {name} = {value}")


@counter.command()
@click.argument("name")
def increment(name: str) -> None:
    """Increment a counter by 1."""
    new_value = counter_ops.increment_counter(name)
    click.echo(f"{name} = {new_value}")


@counter.command()
@click.argument("name")
def reset(name: str) -> None:
    """Reset a counter to 0."""
    counter_ops.reset_counter(name)
    click.echo(f"Reset {name} to 0")


@counter.command()
@click.argument("name")
@click.argument("value", type=int, default=0)
def add(name: str, value: int) -> None:
    """Create a new counter with optional initial value."""
    counter_ops.add_counter(name, value)
    click.echo(f"Created counter {name} = {value}")
