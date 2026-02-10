"""Shared utilities for CALM hooks.

Hooks communicate via stdin/stdout:
- Input: JSON object with hook-specific fields
- Output: Plain text to inject into context (or empty string)
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

# Maximum size for hook error log before rotation (1 MB)
_HOOK_LOG_MAX_BYTES = 1_048_576


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


def get_hook_error_log_path() -> Path:
    """Get path to hook error log file.

    Returns:
        Path to hook_errors.log in CALM home directory
    """
    return get_calm_home() / "hook_errors.log"


def log_hook_error(hook_name: str, exc: BaseException) -> None:
    """Log a hook error to the hook error log file.

    Writes timestamp, hook name, exception type, message, and traceback
    to ~/.calm/hook_errors.log. Performs log rotation if the file exceeds
    1 MB (renames to hook_errors.log.1, keeping only 1 backup).

    This function never raises exceptions -- it silently ignores any I/O
    errors during logging itself.

    Args:
        hook_name: Name of the hook that encountered the error
        exc: The exception that was caught
    """
    try:
        log_path = get_hook_error_log_path()

        # Ensure parent directory exists
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Log rotation: if file exceeds max size, rotate
        if log_path.exists():
            try:
                file_size = log_path.stat().st_size
            except OSError:
                file_size = 0
            if file_size >= _HOOK_LOG_MAX_BYTES:
                backup_path = log_path.with_suffix(".log.1")
                try:
                    log_path.rename(backup_path)
                except OSError:
                    pass  # If rotation fails, just keep writing

        # Format the log entry
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")  # noqa: UP017
        exc_type = type(exc).__name__
        exc_msg = str(exc)
        tb = traceback.format_exception(type(exc), exc, exc.__traceback__)
        tb_str = "".join(tb).rstrip()

        entry = (
            f"[{timestamp}] hook={hook_name} "
            f"exception={exc_type} message={exc_msg}\n"
            f"{tb_str}\n\n"
        )

        # Append to log file
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    except Exception:
        pass  # Never let logging itself break a hook


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
