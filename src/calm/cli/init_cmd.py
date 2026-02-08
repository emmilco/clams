"""CALM init command.

Initializes the ~/.calm directory structure and database.
"""

import click

from calm.config import CALM_HOME, DEFAULT_CONFIG, settings
from calm.db.schema import init_database


@click.command("init")
def init() -> None:
    """Initialize CALM directory and database.

    Creates the ~/.calm directory structure:
    - ~/.calm/config.yaml (user configuration)
    - ~/.calm/metadata.db (SQLite database)
    - ~/.calm/workflows/ (workflow definitions)
    - ~/.calm/roles/ (role files)
    - ~/.calm/sessions/ (session logs)
    - ~/.calm/skills/ (skill definitions)
    - ~/.calm/journal/ (session journals)

    This command is idempotent - safe to run multiple times.
    """
    home = settings.home

    # Create directories
    directories = [
        home,
        settings.workflows_dir,
        settings.roles_dir,
        settings.sessions_dir,
        settings.skills_dir,
        settings.journal_dir,
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        click.echo(f"  Created {directory}")

    # Initialize database
    db_path = settings.db_path
    init_database(db_path)
    click.echo(f"  Initialized database at {db_path}")

    # Create default config if not exists
    config_path = CALM_HOME / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG)
        click.echo(f"  Created config at {config_path}")
    else:
        click.echo(f"  Config already exists at {config_path}")

    click.echo()
    click.echo(f"CALM initialized at {home}")
    click.echo()
    click.echo("Next steps:")
    click.echo("  1. Start Qdrant: docker run -d -p 6333:6333 qdrant/qdrant")
    click.echo("  2. Start server: calm server start")
    click.echo("  3. Check status: calm status")
