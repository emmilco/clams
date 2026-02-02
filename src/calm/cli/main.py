"""CALM CLI main entry point.

This module provides the main CLI interface for CALM.
"""

import click

from calm import __version__


@click.group()
@click.version_option(version=__version__, prog_name="calm")
def cli() -> None:
    """CALM - Claude Agent Learning & Management.

    A unified system for memory, learning, and orchestration.
    """
    pass


# Import and register subcommands
from calm.cli.backup import backup  # noqa: E402
from calm.cli.counter import counter  # noqa: E402
from calm.cli.gate import gate  # noqa: E402
from calm.cli.init_cmd import init  # noqa: E402
from calm.cli.review import review  # noqa: E402
from calm.cli.server import server  # noqa: E402
from calm.cli.session import session  # noqa: E402
from calm.cli.status import status  # noqa: E402

# Orchestration commands
from calm.cli.task import task  # noqa: E402
from calm.cli.worker import worker  # noqa: E402
from calm.cli.worktree import worktree  # noqa: E402

cli.add_command(init)
cli.add_command(server)
cli.add_command(status)

# Register orchestration commands
cli.add_command(task)
cli.add_command(gate)
cli.add_command(worktree)
cli.add_command(worker)
cli.add_command(review)
cli.add_command(counter)
cli.add_command(backup)
cli.add_command(session)
