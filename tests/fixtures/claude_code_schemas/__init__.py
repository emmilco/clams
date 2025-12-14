"""Claude Code hook schema fixtures.

This module provides JSON schema definitions for Claude Code hook output formats.

Documentation: https://docs.anthropic.com/en/docs/claude-code/hooks

Bug References:
- BUG-050: SessionStart hook was using incorrect schema
- BUG-051: UserPromptSubmit hook was using incorrect schema
"""

import json
from pathlib import Path
from typing import Any

SCHEMAS_DIR = Path(__file__).parent


def load_schema(hook_name: str) -> dict[str, Any]:
    """Load a JSON schema for the specified hook.

    Args:
        hook_name: Name of the hook (e.g., 'session_start', 'user_prompt_submit')

    Returns:
        The JSON schema as a dictionary

    Raises:
        FileNotFoundError: If schema file doesn't exist
        json.JSONDecodeError: If schema file is invalid JSON
    """
    schema_path = SCHEMAS_DIR / f"{hook_name}.json"
    with open(schema_path) as f:
        result: dict[str, Any] = json.load(f)
        return result


def get_available_schemas() -> list[str]:
    """Get list of available schema names.

    Returns:
        List of schema names (without .json extension)
    """
    return [p.stem for p in SCHEMAS_DIR.glob("*.json")]


# Schema constants for convenience
HOOK_EVENT_NAMES = {
    "session_start": "SessionStart",
    "user_prompt_submit": "UserPromptSubmit",
    "session_end": "SessionEnd",
}

# Documentation URL
CLAUDE_CODE_HOOKS_DOCS = "https://docs.anthropic.com/en/docs/claude-code/hooks"
