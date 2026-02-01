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
from calm.cli.init_cmd import init  # noqa: E402
from calm.cli.server import server  # noqa: E402
from calm.cli.status import status  # noqa: E402

cli.add_command(init)
cli.add_command(server)
cli.add_command(status)
