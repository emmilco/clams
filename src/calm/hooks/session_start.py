"""SessionStart hook for CALM.

Announces CALM availability, checks for orphaned GHAPs, and shows task count.

Input (stdin): {"working_directory": "/path/to/project"}
Output (stdout): Plain text context injection (max 600 chars)
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

from calm.hooks.common import (
    get_db_path,
    is_server_running,
    read_json_input,
    truncate_output,
    write_output,
)

MAX_OUTPUT_CHARS = 600
SERVER_TIMEOUT_SECONDS = 5


def ensure_server_running() -> bool:
    """Ensure CALM server is running.

    Attempts to start if not running, with timeout.

    Returns:
        True if server is running, False otherwise
    """
    if is_server_running():
        return True

    # Try to start server
    try:
        subprocess.Popen(
            [sys.executable, "-m", "calm", "server", "start"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False

    # Wait for server to start (with timeout)
    deadline = time.time() + SERVER_TIMEOUT_SECONDS
    while time.time() < deadline:
        if is_server_running():
            return True
        time.sleep(0.5)

    return False


def get_orphaned_ghap(db_path: Path) -> dict[str, str] | None:
    """Check for orphaned GHAP from previous session.

    Args:
        db_path: Path to database

    Returns:
        Dict with goal/hypothesis if orphan found, None otherwise
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Get active GHAP entry (status = 'active')
        cursor.execute(
            """
            SELECT goal, hypothesis
            FROM ghap_entries
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {"goal": row["goal"], "hypothesis": row["hypothesis"]}
        return None
    except (sqlite3.Error, OSError):
        return None


def get_active_tasks(
    db_path: Path,
    project_path: str,
) -> list[tuple[str, str]]:
    """Get active tasks for the current project.

    Args:
        db_path: Path to database
        project_path: Project directory path

    Returns:
        List of (task_id, phase) tuples
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, phase
            FROM tasks
            WHERE project_path = ? AND phase != 'DONE'
            ORDER BY created_at DESC
            LIMIT 10
            """,
            (project_path,),
        )
        rows = cursor.fetchall()
        conn.close()

        return [(row["id"], row["phase"]) for row in rows]
    except (sqlite3.Error, OSError):
        return []


def format_output(
    orphan: dict[str, str] | None,
    tasks: list[tuple[str, str]],
    server_available: bool,
) -> str:
    """Format the output message.

    Args:
        orphan: Orphaned GHAP info or None
        tasks: List of (task_id, phase) tuples
        server_available: Whether server is running

    Returns:
        Formatted output string
    """
    lines: list[str] = []

    # Server warning if unavailable
    if not server_available:
        lines.append("CALM available (server starting...).")
    else:
        lines.append("CALM (Claude Agent Learning & Management) is available.")

    lines.append("")

    # Orphaned GHAP warning
    if orphan:
        goal = orphan["goal"][:80]
        if len(orphan["goal"]) > 80:
            goal += "..."
        hypothesis = orphan["hypothesis"][:80]
        if len(orphan["hypothesis"]) > 80:
            hypothesis += "..."

        lines.append("[GHAP Warning] Previous session left an unresolved hypothesis:")
        lines.append(f"Goal: {goal}")
        lines.append(f"Hypothesis: {hypothesis}")
        lines.append("Consider resolving this GHAP before starting new work.")
        lines.append("")

    lines.append("Always active: /wrapup, /reflection, memory tools")

    # Task summary
    if tasks:
        task_summary = ", ".join(f"{t[0]} {t[1]}" for t in tasks[:3])
        lines.append(f"This project: {len(tasks)} active task(s) ({task_summary})")
        lines.append("Run /orchestrate to manage tasks and enable full workflow.")
    else:
        lines.append("Run /orchestrate to enable task tracking and workflow tools.")

    return "\n".join(lines)


def main() -> None:
    """Main entry point for SessionStart hook."""
    # Read input
    input_data = read_json_input()
    working_directory = input_data.get("working_directory") or os.getcwd()

    # Check database
    db_path = get_db_path()
    if not db_path.exists():
        write_output(
            "CALM available. Run `calm init` if not configured.\n"
            "Always active: /wrapup, /reflection, memory tools"
        )
        return

    # Ensure server is running (non-blocking)
    server_available = ensure_server_running()

    # Get orphaned GHAP
    orphan = get_orphaned_ghap(db_path)

    # Get active tasks
    tasks = get_active_tasks(db_path, working_directory)

    # Format and write output
    output = format_output(orphan, tasks, server_available)
    output = truncate_output(output, MAX_OUTPUT_CHARS)
    write_output(output)


if __name__ == "__main__":
    main()
