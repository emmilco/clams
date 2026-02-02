# SPEC-058-01: CALM Foundation - Proposal

## Overview

This proposal covers the implementation approach for creating the CALM foundation package.

## Implementation Plan

### Step 1: Package Structure

Create `src/calm/` with the following files:

```python
# src/calm/__init__.py
"""CALM - Claude Agent Learning & Management."""
__version__ = "0.1.0"

# src/calm/__main__.py
"""Allow running as python -m calm."""
from calm.cli.main import cli
cli()
```

### Step 2: Configuration Module

```python
# src/calm/config.py
from pathlib import Path
from pydantic_settings import BaseSettings

CALM_HOME = Path.home() / ".calm"
CALM_DB = CALM_HOME / "metadata.db"
CALM_CONFIG = CALM_HOME / "config.yaml"

class CalmSettings(BaseSettings):
    """CALM configuration."""
    home: Path = CALM_HOME
    db_path: Path = CALM_DB
    server_host: str = "127.0.0.1"
    server_port: int = 6335
    log_level: str = "info"
```

### Step 3: Database Schema

Implement in `src/calm/db/schema.py`:
- Use the full schema from SPEC-058
- Create `init_database(db_path: Path)` function
- Make it idempotent with `CREATE TABLE IF NOT EXISTS`

### Step 4: CLI with Click

```python
# src/calm/cli/main.py
import click

@click.group()
def cli():
    """CALM - Claude Agent Learning & Management."""
    pass

# Import and register subcommands
from calm.cli.init import init
from calm.cli.server import server

cli.add_command(init)
cli.add_command(server)
```

### Step 5: Init Command

```python
# src/calm/cli/init.py
import click
from pathlib import Path
from calm.config import CALM_HOME
from calm.db.schema import init_database

@click.command()
def init():
    """Initialize CALM directory and database."""
    # Create directories
    for subdir in ["workflows", "roles", "sessions"]:
        (CALM_HOME / subdir).mkdir(parents=True, exist_ok=True)

    # Initialize database
    init_database(CALM_HOME / "metadata.db")

    # Create default config if not exists
    config_path = CALM_HOME / "config.yaml"
    if not config_path.exists():
        config_path.write_text(DEFAULT_CONFIG)

    click.echo(f"CALM initialized at {CALM_HOME}")
```

### Step 6: Server Commands

```python
# src/calm/cli/server.py
import click
from calm.server.daemon import start_daemon, stop_daemon, get_status

@click.group()
def server():
    """Manage CALM server daemon."""
    pass

@server.command()
def start():
    """Start the CALM server daemon."""
    start_daemon()

@server.command()
def stop():
    """Stop the CALM server daemon."""
    stop_daemon()

@server.command()
def status():
    """Show CALM server status."""
    get_status()
```

### Step 7: MCP Server Skeleton

```python
# src/calm/server/app.py
from mcp.server import Server

def create_server() -> Server:
    """Create the CALM MCP server."""
    server = Server("calm")

    # Tools will be registered in later phases
    # For now, just a ping tool to verify server works

    @server.tool()
    async def ping() -> str:
        """Health check."""
        return "pong"

    return server
```

### Step 8: Daemon Management

Adapt existing daemon logic from `clams/server/daemon.py`:
- PID file at `~/.calm/server.pid`
- Log file at `~/.calm/server.log`
- Port 6335 (different from clams' 6334)

### Step 9: pyproject.toml

Add to existing pyproject.toml:

```toml
[project.scripts]
calm = "calm.cli.main:cli"
# Keep existing clams entry point

[project.entry-points."mcp.servers"]
calm = "calm.server.app:create_server"
# Keep existing clams entry point
```

## Testing Strategy

1. **Unit tests** for each module:
   - `tests/calm/test_config.py`
   - `tests/calm/test_db_schema.py`
   - `tests/calm/test_cli_init.py`
   - `tests/calm/test_cli_server.py`

2. **Integration tests**:
   - Full init → server start → ping → server stop cycle
   - Verify database tables created correctly
   - Verify idempotency of init

3. **Isolation**:
   - Use `tmp_path` fixture for `~/.calm/` in tests
   - Mock or use test ports for server tests

## File Changes

| File | Change |
|------|--------|
| `src/calm/__init__.py` | New |
| `src/calm/__main__.py` | New |
| `src/calm/config.py` | New |
| `src/calm/cli/__init__.py` | New |
| `src/calm/cli/main.py` | New |
| `src/calm/cli/init.py` | New |
| `src/calm/cli/server.py` | New |
| `src/calm/server/__init__.py` | New |
| `src/calm/server/app.py` | New |
| `src/calm/server/daemon.py` | New |
| `src/calm/db/__init__.py` | New |
| `src/calm/db/schema.py` | New |
| `src/calm/db/connection.py` | New |
| `pyproject.toml` | Modified |
| `tests/calm/` | New directory with tests |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Port conflict with clams (6334) | Use different port (6335) |
| Import conflicts | Separate package namespace |
| Test isolation | Use tmp_path, mock home directory |

## Estimated Complexity

Low-medium. Mostly scaffolding with patterns borrowed from existing clams code.
