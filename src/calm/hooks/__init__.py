"""CALM hooks for Claude Code integration.

This module provides hook scripts that integrate CALM with Claude Code's
execution lifecycle. Hooks communicate via stdin/stdout:
- Input: JSON object with hook-specific fields
- Output: Plain text to inject into context (or empty string)

Available hooks:
- SessionStart: Announces CALM availability on session start
- UserPromptSubmit: Injects relevant context from memories/experiences
- PreToolUse: Reminds about active GHAP hypothesis
- PostToolUse: Parses test results and suggests GHAP resolution
"""

from calm.hooks.common import (
    HookError,
    PostToolUseInput,
    PreToolUseInput,
    SessionStartInput,
    UserPromptSubmitInput,
    get_calm_home,
    get_db_path,
    get_pid_path,
    get_session_id_path,
    get_tool_count_path,
    is_server_running,
    read_json_input,
    truncate_output,
    write_output,
)

__all__ = [
    "HookError",
    "PostToolUseInput",
    "PreToolUseInput",
    "SessionStartInput",
    "UserPromptSubmitInput",
    "get_calm_home",
    "get_db_path",
    "get_pid_path",
    "get_session_id_path",
    "get_tool_count_path",
    "is_server_running",
    "read_json_input",
    "truncate_output",
    "write_output",
]
