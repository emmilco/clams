"""Shared utilities for CALM hooks.

Hooks communicate via stdin/stdout:
- Input: JSON object with hook-specific fields
- Output: Plain text to inject into context (or empty string)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any, TypedDict


class HookError(Exception):
    """Error during hook execution."""


class SessionStartInput(TypedDict, total=False):
    """Input for SessionStart hook."""

    working_directory: str


class UserPromptSubmitInput(TypedDict, total=False):
    """Input for UserPromptSubmit hook."""

    prompt: str


class PreToolUseInput(TypedDict, total=False):
    """Input for PreToolUse hook."""

    tool_name: str
    tool_input: dict[str, Any]


class PostToolUseInput(TypedDict, total=False):
    """Input for PostToolUse hook."""

    tool_name: str
    tool_input: dict[str, Any]
    tool_output: str


def get_calm_home() -> Path:
    """Get path to CALM home directory.

    Returns:
        Path to CALM home (from settings or default ~/.calm)
    """
    try:
        from calm.config import settings

        return settings.home
    except ImportError:
        return Path.home() / ".calm"


def get_db_path() -> Path:
    """Get path to CALM database.

    Returns:
        Path to database (from settings or default ~/.calm/metadata.db)
    """
    try:
        from calm.config import settings

        return settings.db_path
    except ImportError:
        return Path.home() / ".calm" / "metadata.db"


def get_pid_path() -> Path:
    """Get path to server PID file.

    Returns:
        Path to PID file (from settings or default ~/.calm/server.pid)
    """
    try:
        from calm.config import settings

        return settings.pid_file
    except ImportError:
        return Path.home() / ".calm" / "server.pid"


def get_tool_count_path() -> Path:
    """Get path to tool count file.

    Returns:
        Path to tool count file (used for PreToolUse counter persistence)
    """
    return get_calm_home() / "tool_count"


def get_session_id_path() -> Path:
    """Get path to session ID file.

    Returns:
        Path to session ID file (used to detect session changes)
    """
    return get_calm_home() / "session_id"


def read_json_input() -> dict[str, Any]:
    """Read JSON from stdin.

    Returns:
        Parsed JSON object, or empty dict on error
    """
    try:
        raw = sys.stdin.read()
        if not raw.strip():
            return {}
        result = json.loads(raw)
        if not isinstance(result, dict):
            return {}
        return result
    except (json.JSONDecodeError, OSError):
        return {}


def write_output(text: str) -> None:
    """Write output to stdout.

    Args:
        text: Text to write (empty string for no output)
    """
    if text:
        sys.stdout.write(text)
        sys.stdout.flush()


def truncate_output(text: str, max_chars: int) -> str:
    """Truncate output to character limit.

    Args:
        text: Text to truncate
        max_chars: Maximum characters allowed

    Returns:
        Truncated text (with ellipsis if truncated)
    """
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 3] + "..."


def is_server_running() -> bool:
    """Check if CALM server is running.

    Returns:
        True if PID file exists and process is running
    """
    pid_path = get_pid_path()
    if not pid_path.exists():
        return False

    try:
        pid = int(pid_path.read_text().strip())
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return True
    except (ValueError, OSError, ProcessLookupError):
        return False
