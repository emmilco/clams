#!/usr/bin/env python3
"""CALM Cutover - Migrate from CLAMS/CLAWS to CALM.

One-off migration script that performs the atomic switch from the old
CLAMS/CLAWS system to the unified CALM system. Idempotent: safe to run
multiple times.

Usage:
    python scripts/cutover.py [--dry-run] [--verbose] [--skip-server]
    python scripts/cutover.py --repo-root /path/to/repo
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CutoverOptions:
    """Options controlling cutover behavior."""

    dry_run: bool = False
    verbose: bool = False
    skip_server: bool = False
    clams_home: Path = field(default_factory=lambda: Path.home() / ".clams")
    calm_home: Path = field(default_factory=lambda: Path.home() / ".calm")
    claws_db: Path | None = None
    repo_root: Path | None = None
    claude_json: Path = field(default_factory=lambda: Path.home() / ".claude.json")
    settings_json: Path = field(
        default_factory=lambda: Path.home() / ".claude" / "settings.json"
    )
    dev_mode: bool = True


@dataclass
class CutoverResult:
    """Result of cutover attempt."""

    success: bool = True
    steps_completed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    counts: dict[str, dict[str, int]] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_repo_root() -> Path:
    """Detect the git repository root from cwd."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return Path.cwd()


def _detect_claws_db(repo_root: Path) -> Path:
    """Locate the CLAWS database relative to repo root."""
    return repo_root / ".claude" / "claws.db"


def _resolve_worktree_path(path: str | None, repo_root: Path) -> str | None:
    """Convert a relative worktree path to absolute."""
    if path is None:
        return None
    if path.startswith(".worktrees/") or (
        not path.startswith("/") and "worktrees" in path
    ):
        return str(repo_root / path)
    return path


def _map_worker_status(old_status: str) -> str:
    """Map old worker status values to new."""
    mapping: dict[str, str] = {
        "idle": "completed",
        "stale": "session_ended",
    }
    return mapping.get(old_status, old_status)


def _count_rows(conn: sqlite3.Connection, table: str) -> int:
    """Count rows in a table. Returns 0 if table doesn't exist."""
    try:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row = cursor.fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Check if a table exists in the database."""
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cursor.fetchone() is not None


def _remove_old_mcp_server(config: dict[str, Any]) -> dict[str, Any]:
    """Remove the old 'clams' key from mcpServers in config."""
    result = dict(config)
    servers = result.get("mcpServers")
    if isinstance(servers, dict) and "clams" in servers:
        result["mcpServers"] = {k: v for k, v in servers.items() if k != "clams"}
    return result


def _migrate_journal_entries(
    jsonl_path: Path,
    target_conn: sqlite3.Connection,
) -> int:
    """Parse JSONL session entries and insert into session_journal table."""
    if not jsonl_path.exists():
        return 0

    content = jsonl_path.read_text(encoding="utf-8").strip()
    if not content:
        return 0

    count = 0
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            target_conn.execute(
                "INSERT OR REPLACE INTO session_journal "
                "(id, created_at, working_directory, project_name, "
                "session_log_path, summary, friction_points, next_steps) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    entry.get("id", ""),
                    entry.get("created_at", ""),
                    entry.get("working_directory", ""),
                    entry.get("project_name"),
                    entry.get("session_log_path"),
                    entry.get("summary", ""),
                    json.dumps(entry["friction_points"])
                    if "friction_points" in entry
                    else None,
                    json.dumps(entry["next_steps"])
                    if "next_steps" in entry
                    else None,
                ),
            )
            count += 1
        except (json.JSONDecodeError, KeyError):
            continue

    target_conn.commit()
    return count


def output(message: str, *, verbose_only: bool = False, verbose: bool = False) -> None:
    """Print a message. If verbose_only=True, only print when verbose=True."""
    if verbose_only and not verbose:
        return
    print(message)


# ---------------------------------------------------------------------------
# Phase functions
# ---------------------------------------------------------------------------


def stop_old_server(options: CutoverOptions) -> tuple[bool, str]:
    """Stop the old CLAMS MCP server process."""
    if options.dry_run:
        return True, "Would stop old CLAMS server"

    try:
        result = subprocess.run(
            ["pkill", "-f", "clams.server"],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return True, "Stopped old CLAMS server"
        return True, "Old CLAMS server was not running (already stopped)"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return True, "Warning: Could not check for old server process"


def create_backups(options: CutoverOptions) -> tuple[bool, list[str]]:
    """Create backups of all source files before modification."""
    messages: list[str] = []

    sources = [
        (options.clams_home / "metadata.db", "CLAMS metadata.db"),
        (options.claws_db, "CLAWS claws.db") if options.claws_db else (None, ""),
        (options.claude_json, "claude.json"),
        (options.settings_json, "settings.json"),
    ]

    for source_item, label in sources:
        if source_item is None:
            continue
        source = Path(source_item)
        if not source.exists():
            messages.append(f"Skipped backup of {label} (does not exist)")
            continue

        backup = source.parent / f"{source.name}.pre-cutover"
        if backup.exists():
            messages.append(
                f"Skipped backup of {label} (backup already exists at {backup})"
            )
            continue

        if options.dry_run:
            messages.append(f"Would back up {label}: {source} -> {backup}")
            continue

        shutil.copy2(source, backup)
        messages.append(f"Backed up {label}: {source} -> {backup}")

    return True, messages


def ensure_calm_infrastructure(
    options: CutoverOptions,
) -> tuple[bool, list[str]]:
    """Set up CALM target directory and database."""
    messages: list[str] = []

    if options.dry_run:
        messages.append("Would create CALM directories and initialize database")
        return True, messages

    # Import here to allow the script to report dry-run info even without
    # the calm package installed.
    from calm.db.schema import init_database
    from calm.install.templates import copy_all_templates, create_directory_structure

    # Create directory structure
    created = create_directory_structure(options.calm_home)
    messages.extend(created)

    # Initialize database
    db_path = options.calm_home / "metadata.db"
    init_database(db_path)
    messages.append(f"Initialized database at {db_path}")

    # Copy templates
    copied, _skipped, errors = copy_all_templates(options.calm_home)
    messages.extend(copied)
    if errors:
        messages.extend(f"Template error: {e}" for e in errors)

    return True, messages


def migrate_clams_data(
    options: CutoverOptions,
    target_db: Path,
) -> tuple[bool, dict[str, dict[str, int]]]:
    """Migrate CLAMS metadata.db tables to CALM metadata.db."""
    counts: dict[str, dict[str, int]] = {}
    source_path = options.clams_home / "metadata.db"

    if not source_path.exists():
        return True, counts

    source_conn = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    source_conn.row_factory = sqlite3.Row

    try:
        if options.dry_run:
            for table in ("indexed_files", "projects", "git_index_state"):
                src_count = _count_rows(source_conn, table)
                counts[table] = {"source": src_count, "migrated": 0}
            # Check journal
            journal_path = options.clams_home / "journal" / "session_entries.jsonl"
            journal_count = 0
            if journal_path.exists():
                content = journal_path.read_text(encoding="utf-8").strip()
                if content:
                    journal_count = sum(
                        1 for line in content.splitlines() if line.strip()
                    )
            counts["session_journal"] = {"source": journal_count, "migrated": 0}
            return True, counts

        target_conn = sqlite3.connect(target_db)
        try:
            # Migrate compatible tables
            for table in ("indexed_files", "projects", "git_index_state"):
                if not _table_exists(source_conn, table):
                    counts[table] = {"source": 0, "migrated": 0}
                    continue

                rows = source_conn.execute(f"SELECT * FROM {table}").fetchall()  # noqa: S608
                src_count = len(rows)
                if src_count == 0:
                    counts[table] = {"source": 0, "migrated": 0}
                    continue

                # Get column names
                query = f"SELECT * FROM {table} LIMIT 0"  # noqa: S608
                col_names = [
                    desc[0] for desc in source_conn.execute(query).description
                ]
                placeholders = ", ".join("?" for _ in col_names)
                cols = ", ".join(col_names)

                migrated = 0
                for row in rows:
                    try:
                        stmt = f"INSERT OR REPLACE INTO {table} ({cols}) VALUES ({placeholders})"  # noqa: S608, E501
                        target_conn.execute(stmt, tuple(row))
                        migrated += 1
                    except sqlite3.Error:
                        continue

                target_conn.commit()
                counts[table] = {"source": src_count, "migrated": migrated}

            # Migrate journal JSONL
            journal_path = options.clams_home / "journal" / "session_entries.jsonl"
            journal_count = _migrate_journal_entries(journal_path, target_conn)
            # Also check archive
            archive_dir = options.clams_home / "journal" / "archive"
            if archive_dir.exists():
                for archive_file in sorted(archive_dir.glob("*.jsonl")):
                    journal_count += _migrate_journal_entries(
                        archive_file, target_conn
                    )
            counts["session_journal"] = {
                "source": journal_count,
                "migrated": journal_count,
            }

        finally:
            target_conn.close()
    finally:
        source_conn.close()

    return True, counts


def migrate_claws_data(
    options: CutoverOptions,
    target_db: Path,
) -> tuple[bool, dict[str, dict[str, int]]]:
    """Migrate CLAWS orchestration data to CALM metadata.db."""
    counts: dict[str, dict[str, int]] = {}

    if options.claws_db is None or not options.claws_db.exists():
        return True, counts

    repo_root = options.repo_root or _detect_repo_root()
    source_conn = sqlite3.connect(
        f"file:{options.claws_db}?mode=ro", uri=True
    )
    source_conn.row_factory = sqlite3.Row

    try:
        if options.dry_run:
            table_map: dict[str, str] = {
                "tasks": "tasks",
                "workers": "workers",
                "reviews": "reviews",
                "test_runs": "test_runs",
                "system_counters": "counters",
                "phase_transitions": "phase_transitions",
                "gate_passes": "gate_passes",
                "sessions": "sessions",
            }
            for old_table, new_table in table_map.items():
                src_count = _count_rows(source_conn, old_table)
                counts[new_table] = {"source": src_count, "migrated": 0}
            return True, counts

        target_conn = sqlite3.connect(target_db)
        try:
            # --- tasks ---
            if _table_exists(source_conn, "tasks"):
                rows = source_conn.execute("SELECT * FROM tasks").fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    wt_path = _resolve_worktree_path(
                        r.get("worktree_path"), repo_root
                    )
                    target_conn.execute(
                        "INSERT OR REPLACE INTO tasks "
                        "(id, title, spec_id, task_type, phase, specialist, "
                        "notes, blocked_by, worktree_path, project_path, "
                        "created_at, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r["title"],
                            r.get("spec_id"),
                            r.get("task_type", "feature"),
                            r["phase"],
                            r.get("assigned_specialist"),
                            r.get("notes"),
                            r.get("blocked_by"),
                            wt_path,
                            str(repo_root),
                            r.get("created_at", ""),
                            r.get("updated_at", ""),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["tasks"] = {"source": len(rows), "migrated": migrated}
            else:
                counts["tasks"] = {"source": 0, "migrated": 0}

            # --- workers ---
            if _table_exists(source_conn, "workers"):
                rows = source_conn.execute("SELECT * FROM workers").fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    status = _map_worker_status(r.get("status", "active"))
                    target_conn.execute(
                        "INSERT OR REPLACE INTO workers "
                        "(id, task_id, role, status, started_at, ended_at, "
                        "project_path) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r.get("current_task_id", ""),
                            r.get("specialist_type", ""),
                            status,
                            r.get("started_at", ""),
                            r.get("ended_at"),
                            str(repo_root),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["workers"] = {"source": len(rows), "migrated": migrated}
            else:
                counts["workers"] = {"source": 0, "migrated": 0}

            # --- reviews ---
            if _table_exists(source_conn, "reviews"):
                rows = source_conn.execute("SELECT * FROM reviews").fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    target_conn.execute(
                        "INSERT OR REPLACE INTO reviews "
                        "(id, task_id, review_type, result, worker_id, "
                        "reviewer_notes, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r["task_id"],
                            r.get("artifact_type", ""),
                            r.get("result", ""),
                            r.get("reviewer_worker_id"),
                            r.get("issues_found"),
                            r.get("created_at", ""),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["reviews"] = {"source": len(rows), "migrated": migrated}
            else:
                counts["reviews"] = {"source": 0, "migrated": 0}

            # --- test_runs ---
            if _table_exists(source_conn, "test_runs"):
                rows = source_conn.execute("SELECT * FROM test_runs").fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    target_conn.execute(
                        "INSERT OR REPLACE INTO test_runs "
                        "(id, task_id, passed, failed, skipped, "
                        "duration_seconds, failed_tests, run_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r["task_id"],
                            r.get("passed", 0),
                            r.get("failed", 0),
                            r.get("skipped", 0),
                            r.get("execution_time_seconds"),
                            r.get("failed_tests"),
                            r.get("run_at", ""),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["test_runs"] = {
                    "source": len(rows),
                    "migrated": migrated,
                }
            else:
                counts["test_runs"] = {"source": 0, "migrated": 0}

            # --- system_counters -> counters ---
            if _table_exists(source_conn, "system_counters"):
                rows = source_conn.execute(
                    "SELECT name, value FROM system_counters"
                ).fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    target_conn.execute(
                        "INSERT INTO counters (name, value) VALUES (?, ?) "
                        "ON CONFLICT(name) DO UPDATE "
                        "SET value = MAX(value, excluded.value)",
                        (r["name"], r["value"]),
                    )
                    migrated += 1
                target_conn.commit()
                counts["counters"] = {
                    "source": len(rows),
                    "migrated": migrated,
                }
            else:
                counts["counters"] = {"source": 0, "migrated": 0}

            # --- phase_transitions ---
            if _table_exists(source_conn, "phase_transitions"):
                rows = source_conn.execute(
                    "SELECT * FROM phase_transitions"
                ).fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    from_phase = r.get("from_phase")
                    if from_phase is None:
                        from_phase = ""
                    target_conn.execute(
                        "INSERT OR REPLACE INTO phase_transitions "
                        "(id, task_id, from_phase, to_phase, gate_result, "
                        "gate_details, transitioned_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r["task_id"],
                            from_phase,
                            r.get("to_phase", ""),
                            r.get("gate_result"),
                            r.get("gate_details"),
                            r.get("transitioned_at", ""),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["phase_transitions"] = {
                    "source": len(rows),
                    "migrated": migrated,
                }
            else:
                counts["phase_transitions"] = {"source": 0, "migrated": 0}

            # --- gate_passes ---
            if _table_exists(source_conn, "gate_passes"):
                rows = source_conn.execute(
                    "SELECT * FROM gate_passes"
                ).fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    try:
                        target_conn.execute(
                            "INSERT OR REPLACE INTO gate_passes "
                            "(id, task_id, transition, commit_sha, passed_at) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (
                                r["id"],
                                r["task_id"],
                                r["transition"],
                                r["commit_sha"],
                                r.get("passed_at", ""),
                            ),
                        )
                        migrated += 1
                    except sqlite3.Error:
                        continue
                target_conn.commit()
                counts["gate_passes"] = {
                    "source": len(rows),
                    "migrated": migrated,
                }
            else:
                counts["gate_passes"] = {"source": 0, "migrated": 0}

            # --- sessions ---
            if _table_exists(source_conn, "sessions"):
                rows = source_conn.execute(
                    "SELECT * FROM sessions"
                ).fetchall()
                migrated = 0
                for row in rows:
                    r = dict(row)
                    target_conn.execute(
                        "INSERT OR REPLACE INTO sessions "
                        "(id, created_at, handoff_content, "
                        "needs_continuation, resumed_at) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (
                            r["id"],
                            r.get("created_at", ""),
                            r.get("handoff_content"),
                            r.get("needs_continuation", 0),
                            r.get("resumed_at"),
                        ),
                    )
                    migrated += 1
                target_conn.commit()
                counts["sessions"] = {
                    "source": len(rows),
                    "migrated": migrated,
                }
            else:
                counts["sessions"] = {"source": 0, "migrated": 0}

        finally:
            target_conn.close()
    finally:
        source_conn.close()

    return True, counts


def update_configuration(options: CutoverOptions) -> tuple[bool, list[str]]:
    """Update MCP server and hook configuration."""
    messages: list[str] = []

    if options.dry_run:
        messages.append('Would remove "clams" from mcpServers in claude.json')
        messages.append('Would register "calm" in mcpServers in claude.json')
        messages.append("Would register CALM hooks in settings.json")
        messages.append("Would remove old clams_scripts hooks")
        return True, messages

    from calm.install.config_merge import (
        atomic_write_json,
        read_json_config,
        register_hooks,
        register_mcp_server,
    )

    # Remove old CLAMS server and register CALM server
    config = read_json_config(options.claude_json)
    config = _remove_old_mcp_server(config)
    atomic_write_json(options.claude_json, config)
    messages.append('Removed "clams" MCP server from claude.json')

    repo_root = options.repo_root or _detect_repo_root()
    msg = register_mcp_server(
        options.claude_json,
        dev_mode=options.dev_mode,
        dev_directory=repo_root,
    )
    messages.append(msg)

    # Register hooks (also cleans old clams hooks)
    msg = register_hooks(options.settings_json)
    messages.append(msg)

    return True, messages


def start_calm_server(options: CutoverOptions) -> tuple[bool, str]:
    """Start the CALM MCP server daemon and verify it responds."""
    if options.dry_run:
        return True, "Would start CALM server"

    if options.skip_server:
        return True, "Skipped server start (--skip-server)"

    try:
        from calm.install.docker import ensure_qdrant_running

        success, qdrant_msg = ensure_qdrant_running()
        if not success:
            msg = f"Warning: Qdrant not available ({qdrant_msg})"
            return True, f"{msg}, skipping server start"
    except Exception:
        return True, "Warning: Could not check Qdrant status, skipping server start"

    try:
        from calm.server.daemon import start_daemon

        start_daemon()
        return True, "Started CALM server daemon"
    except Exception as e:
        return False, f"Failed to start CALM server: {e}"


def verify_migration(
    options: CutoverOptions,
    counts: dict[str, dict[str, int]],
) -> tuple[bool, list[str]]:
    """Verify migration by comparing source and target counts."""
    messages: list[str] = []

    if options.dry_run:
        messages.append("Verification skipped (dry run)")
        return True, messages

    if not counts:
        messages.append("No data was migrated (source databases may not exist)")
        return True, messages

    messages.append("Migration verification:")
    messages.append(f"  {'Table':<25} {'Source':>8} {'Migrated':>10}")
    messages.append(f"  {'-' * 25} {'-' * 8} {'-' * 10}")

    total_source = 0
    total_migrated = 0
    has_warnings = False

    for table, table_counts in sorted(counts.items()):
        src = table_counts.get("source", 0)
        mig = table_counts.get("migrated", 0)
        total_source += src
        total_migrated += mig
        marker = ""
        if src != mig and src > 0:
            marker = " WARNING"
            has_warnings = True
        messages.append(f"  {table:<25} {src:>8} {mig:>10}{marker}")

    messages.append("")
    messages.append(
        f"Migration complete. {total_migrated} rows migrated "
        f"from {total_source} source rows."
    )

    if has_warnings:
        messages.append(
            "WARNING: Some counts differ. This may be normal for "
            "idempotent reruns."
        )

    return True, messages


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_cutover(options: CutoverOptions) -> CutoverResult:
    """Run the full cutover process."""
    result = CutoverResult()
    verbose = options.verbose

    # Resolve defaults
    if options.repo_root is None:
        options.repo_root = _detect_repo_root()
    if options.claws_db is None:
        options.claws_db = _detect_claws_db(options.repo_root)

    target_db = options.calm_home / "metadata.db"

    mode = " (dry run)" if options.dry_run else ""
    output(f"CALM Cutover{mode}\n")

    # [1/8] Stop old server
    output("[1/8] Stopping old CLAMS server...")
    ok, msg = stop_old_server(options)
    output(f"  {msg}")
    result.steps_completed.append("stop_old_server")
    if not ok:
        result.warnings.append(msg)
    output("")

    # [2/8] Create backups
    output("[2/8] Creating backups...")
    ok, msgs = create_backups(options)
    for m in msgs:
        output(f"  {m}")
    result.steps_completed.append("create_backups")
    output("")

    # [3/8] Ensure CALM infrastructure
    output("[3/8] Setting up CALM infrastructure...")
    ok, msgs = ensure_calm_infrastructure(options)
    for m in msgs:
        output(f"  {m}", verbose_only=True, verbose=verbose)
    if not ok:
        result.errors.append("Failed to set up CALM infrastructure")
        result.success = False
        return result
    result.steps_completed.append("ensure_calm_infrastructure")
    output("")

    # [4/8] Migrate CLAMS data
    output("[4/8] Migrating CLAMS data...")
    all_counts: dict[str, dict[str, int]] = {}
    ok, clams_counts = migrate_clams_data(options, target_db)
    all_counts.update(clams_counts)
    if clams_counts:
        for table, tc in clams_counts.items():
            src = tc.get("source", 0)
            mig = tc.get("migrated", 0)
            suffix = f" ({mig} migrated)" if not options.dry_run else ""
            output(f"  {table}: {src} rows{suffix}")
    else:
        output("  No CLAMS data to migrate (source not found)")
    result.steps_completed.append("migrate_clams_data")
    output("")

    # [5/8] Migrate CLAWS data
    output("[5/8] Migrating CLAWS data...")
    ok, claws_counts = migrate_claws_data(options, target_db)
    all_counts.update(claws_counts)
    if claws_counts:
        for table, tc in claws_counts.items():
            src = tc.get("source", 0)
            mig = tc.get("migrated", 0)
            suffix = f" ({mig} migrated)" if not options.dry_run else ""
            output(f"  {table}: {src} rows{suffix}")
    else:
        output("  No CLAWS data to migrate (source not found)")
    result.steps_completed.append("migrate_claws_data")
    output("")

    # [6/8] Update configuration
    output("[6/8] Updating configuration...")
    ok, msgs = update_configuration(options)
    for m in msgs:
        output(f"  {m}")
    result.steps_completed.append("update_configuration")
    output("")

    # [7/8] Start CALM server
    output("[7/8] Starting CALM server...")
    if options.skip_server or options.dry_run:
        skip_msg = "Skipped (dry run)" if options.dry_run else "Skipped (--skip-server)"
        output(f"  {skip_msg}")
    else:
        ok, msg = start_calm_server(options)
        output(f"  {msg}")
        if not ok:
            result.errors.append(msg)
            result.success = False
    result.steps_completed.append("start_calm_server")
    output("")

    # [8/8] Verify migration
    output("[8/8] Verifying migration...")
    ok, msgs = verify_migration(options, all_counts)
    for m in msgs:
        output(f"  {m}")
    result.steps_completed.append("verify_migration")
    result.counts = all_counts

    if options.dry_run:
        output("\nNo changes made.")

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="CALM Cutover - Migrate from CLAMS/CLAWS to CALM",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be done without making changes",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed output",
    )
    parser.add_argument(
        "--skip-server",
        action="store_true",
        help="Skip starting/stopping servers",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Git repository root (auto-detected if not specified)",
    )
    parser.add_argument(
        "--clams-dir",
        type=Path,
        default=None,
        help="CLAMS home directory (default: ~/.clams)",
    )
    parser.add_argument(
        "--calm-dir",
        type=Path,
        default=None,
        help="CALM home directory (default: ~/.calm)",
    )
    parser.add_argument(
        "--claude-dir",
        type=Path,
        default=None,
        help="Claude config directory root (for .claude.json location)",
    )

    args = parser.parse_args()

    options = CutoverOptions(
        dry_run=args.dry_run,
        verbose=args.verbose,
        skip_server=args.skip_server,
        repo_root=args.repo_root,
    )

    if args.clams_dir:
        options.clams_home = args.clams_dir
    if args.calm_dir:
        options.calm_home = args.calm_dir
    if args.claude_dir:
        options.claude_json = args.claude_dir / ".claude.json"
        options.settings_json = args.claude_dir / ".claude" / "settings.json"

    result = run_cutover(options)

    if not result.success:
        sys.exit(1)


if __name__ == "__main__":
    main()
