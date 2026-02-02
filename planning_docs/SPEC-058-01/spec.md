# SPEC-058-01: CALM Foundation

## Summary

Create the `calm` Python package alongside the existing `clams` package, establishing the core infrastructure for the unified system.

## Parent Spec

See [SPEC-058](../SPEC-058/spec.md) for full system design.

## Scope

This phase establishes:
1. Package structure (`src/calm/`)
2. pyproject.toml entry points
3. `calm init` command (creates `~/.calm/` directory structure)
4. `calm server start/stop/status` commands
5. Basic MCP server skeleton (no tools yet)
6. Database initialization (`~/.calm/metadata.db`)

## Deliverables

### 1. Package Structure

```
src/calm/
├── __init__.py
├── __main__.py          # CLI entry point
├── cli/
│   ├── __init__.py
│   ├── main.py          # Click app
│   ├── init.py          # calm init
│   └── server.py        # calm server start/stop/status
├── server/
│   ├── __init__.py
│   ├── app.py           # MCP server application
│   └── daemon.py        # Daemonization logic
├── db/
│   ├── __init__.py
│   ├── schema.py        # Schema definitions
│   └── connection.py    # Database connection management
└── config.py            # Configuration management
```

### 2. pyproject.toml Updates

```toml
[project.scripts]
calm = "calm.cli.main:cli"

[project.entry-points."mcp.servers"]
calm = "calm.server.app:create_server"
```

### 3. CLI Commands

| Command | Behavior |
|---------|----------|
| `calm init` | Creates `~/.calm/` with subdirs, initializes `metadata.db` |
| `calm server start` | Starts MCP server daemon |
| `calm server stop` | Stops running daemon |
| `calm server status` | Shows daemon status |

### 4. Directory Structure Created by `calm init`

```
~/.calm/
├── config.yaml          # User preferences (created with defaults)
├── metadata.db          # SQLite database
├── workflows/           # Workflow definitions (empty initially)
├── roles/               # Role files (empty initially)
└── sessions/            # Session logs (empty initially)
```

### 5. Database Schema

Initialize all tables from SPEC-058 schema:
- memories
- session_journal
- ghap_entries
- tasks
- workers
- reviews
- test_runs
- counters

## Acceptance Criteria

- [ ] `pip install -e .` installs `calm` command
- [ ] `calm init` creates `~/.calm/` directory structure
- [ ] `calm init` creates `metadata.db` with all tables
- [ ] `calm init` is idempotent (safe to run multiple times)
- [ ] `calm server start` launches daemon on port 6335
- [ ] `calm server stop` cleanly stops daemon
- [ ] `calm server status` reports running/stopped
- [ ] Existing `clams` package continues to work unchanged
- [ ] All new code passes mypy --strict
- [ ] All new code has tests

## Non-Goals

- No MCP tools implemented (Phase 2-5)
- No migration from existing data (Phase 7)
- No hook scripts (Phase 5)
