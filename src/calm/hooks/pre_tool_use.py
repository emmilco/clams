"""PreToolUse hook for CALM.

Reminds about active GHAP hypothesis when check-in is due.

Input (stdin): {"tool_name": "Bash", "tool_input": {...}}
Output (stdout): GHAP reminder (max 800 chars), or empty if no reminder due

Note: Since each hook invocation is a separate process, we persist the tool
count to a file (~/.calm/tool_count). The counter resets when a new session
starts (detected via session ID in the environment).
"""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from calm.hooks.common import (
    get_db_path,
    get_tool_count_path,
    read_json_input,
    truncate_output,
    write_output,
)

MAX_OUTPUT_CHARS = 800
DEFAULT_FREQUENCY = 10


def get_current_session_id() -> str:
    """Get the current session ID from environment.

    Claude Code sets CLAUDE_SESSION_ID in the environment for each session.

    Returns:
        Session ID string, or empty string if not available
    """
    return os.environ.get("CLAUDE_SESSION_ID", "")


def read_tool_count() -> tuple[int, str]:
    """Read tool count and session ID from file.

    Returns:
        Tuple of (tool_count, session_id). Returns (0, "") if file doesn't exist.
    """
    count_path = get_tool_count_path()
    try:
        if not count_path.exists():
            return (0, "")
        data = json.loads(count_path.read_text())
        return (data.get("count", 0), data.get("session_id", ""))
    except (json.JSONDecodeError, OSError, KeyError):
        return (0, "")


def write_tool_count(count: int, session_id: str) -> None:
    """Write tool count and session ID to file atomically.

    Args:
        count: Tool count value
        session_id: Current session ID
    """
    count_path = get_tool_count_path()
    try:
        # Ensure parent directory exists
        count_path.parent.mkdir(parents=True, exist_ok=True)

        # Write atomically using temp file + rename
        tmp_path = count_path.with_suffix(".tmp")
        data = {"count": count, "session_id": session_id}
        tmp_path.write_text(json.dumps(data))
        tmp_path.rename(count_path)
    except OSError:
        pass  # Fail silently - counter is not critical


def get_active_ghap(db_path: Path) -> dict[str, Any] | None:
    """Get the current active GHAP entry.

    Args:
        db_path: Path to database

    Returns:
        Dict with GHAP details or None
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT goal, hypothesis, prediction, action
            FROM ghap_entries
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                "goal": row["goal"],
                "hypothesis": row["hypothesis"],
                "prediction": row["prediction"],
                "action": row["action"],
            }
        return None
    except (sqlite3.Error, OSError):
        return None


def format_reminder(ghap: dict[str, Any]) -> str:
    """Format the GHAP check-in reminder.

    Args:
        ghap: GHAP details dict

    Returns:
        Formatted reminder string
    """
    goal = ghap["goal"][:80]
    hypothesis = ghap["hypothesis"][:80]
    prediction = ghap["prediction"][:80]

    lines = [
        "## GHAP Check-in",
        "",
        "You have an active hypothesis:",
        f"- Goal: {goal}",
        f"- Hypothesis: {hypothesis}",
        f"- Prediction: {prediction}",
        "",
        "Is this still your working hypothesis? Consider:",
        "- `update_ghap` if your hypothesis has changed",
        "- `resolve_ghap` if you've confirmed or falsified it",
    ]
    return "\n".join(lines)


def main() -> None:
    """Main entry point for PreToolUse hook."""
    # Read input (not used for logic, but validates the call)
    input_data = read_json_input()
    if not input_data.get("tool_name"):
        write_output("")
        return

    # Get current session and stored session
    current_session = get_current_session_id()
    stored_count, stored_session = read_tool_count()

    # Reset counter if session changed
    if current_session and current_session != stored_session:
        stored_count = 0

    # Increment tool count
    tool_count = stored_count + 1

    # Check if reminder is due
    if tool_count < DEFAULT_FREQUENCY:
        write_tool_count(tool_count, current_session)
        write_output("")
        return

    # Check database
    db_path = get_db_path()
    if not db_path.exists():
        write_tool_count(tool_count, current_session)
        write_output("")
        return

    # Get active GHAP
    ghap = get_active_ghap(db_path)
    if not ghap:
        write_tool_count(tool_count, current_session)
        write_output("")
        return

    # Reset counter and output reminder
    write_tool_count(0, current_session)
    output = format_reminder(ghap)
    output = truncate_output(output, MAX_OUTPUT_CHARS)
    write_output(output)


if __name__ == "__main__":
    main()
