"""JSON configuration merging utilities.

Provides safe JSON config reading, merging, and atomic writing.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any


class ConfigError(Exception):
    """Error during config manipulation."""

    pass


def read_json_config(path: Path) -> dict[str, Any]:
    """Read JSON config file, creating empty dict if missing.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON as dict

    Raises:
        ConfigError: If file exists but is invalid JSON
    """
    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ConfigError(
                f"Invalid JSON in {path}: expected object, got {type(data).__name__}"
            )
        return data
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}") from e


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically (write temp, rename).

    Args:
        path: Target path
        data: Data to write

    Raises:
        ConfigError: If write fails
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Use same directory for temp file (rename must be same filesystem)
    try:
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
    except OSError as e:
        raise ConfigError(f"Cannot create temp file in {path.parent}: {e}") from e

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")  # Trailing newline
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise ConfigError(f"Failed to write {path}: {e}") from e


def merge_mcp_server(
    config: dict[str, Any],
    server_command: list[str],
) -> dict[str, Any]:
    """Merge CALM MCP server into config.

    Args:
        config: Existing claude.json content
        server_command: Command to start server (e.g., ["uv", "run", ...])

    Returns:
        Updated config dict (original not mutated)
    """
    result = config.copy()

    # Ensure mcpServers exists
    if "mcpServers" not in result:
        result["mcpServers"] = {}
    else:
        # Deep copy to avoid mutating original
        result["mcpServers"] = dict(result["mcpServers"])

    # Add/update calm server
    result["mcpServers"]["calm"] = {
        "command": server_command[0],
        "args": server_command[1:],
    }

    return result


def _is_calm_hook(hook: dict[str, Any]) -> bool:
    """Check if a hook is a CALM hook."""
    hooks = hook.get("hooks", [])
    for h in hooks:
        cmd = h.get("command", "")
        if "calm.hooks." in cmd or "python -m calm.hooks" in cmd:
            return True
    return False


def _is_old_clams_hook(hook: dict[str, Any]) -> bool:
    """Check if a hook is an old clams_scripts hook."""
    hooks = hook.get("hooks", [])
    for h in hooks:
        cmd = h.get("command", "")
        if "clams_scripts/hooks" in cmd:
            return True
    return False


def _clean_old_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    """Remove old clams_scripts hook references."""
    result: dict[str, Any] = {}
    for hook_type, hook_list in hooks.items():
        if not isinstance(hook_list, list):
            result[hook_type] = hook_list
            continue
        cleaned = [h for h in hook_list if not _is_old_clams_hook(h)]
        result[hook_type] = cleaned
    return result


def merge_hooks(
    settings: dict[str, Any],
    clean_old: bool = True,
) -> dict[str, Any]:
    """Merge CALM hooks into settings.

    Args:
        settings: Existing settings.json content
        clean_old: Remove old clams_scripts hook references

    Returns:
        Updated settings dict (original not mutated)
    """
    result = settings.copy()

    # Define CALM hooks
    calm_hooks: dict[str, list[dict[str, Any]]] = {
        "SessionStart": [
            {
                "matcher": "startup",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.session_start"}
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -m calm.hooks.user_prompt_submit",
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.pre_tool_use"}
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash(pytest:*)|Bash(npm test:*)|Bash(cargo test:*)",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.post_tool_use"}
                ],
            }
        ],
    }

    # Get or create hooks section
    existing_hooks = result.get("hooks", {})
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}
    result["hooks"] = dict(existing_hooks)

    # Clean old references if requested
    if clean_old:
        result["hooks"] = _clean_old_hooks(result["hooks"])

    # Merge each hook type
    for hook_type, hook_list in calm_hooks.items():
        if hook_type not in result["hooks"]:
            result["hooks"][hook_type] = []
        else:
            result["hooks"][hook_type] = list(result["hooks"][hook_type])

        # Remove any existing CALM hooks (for idempotency)
        result["hooks"][hook_type] = [
            h for h in result["hooks"][hook_type] if not _is_calm_hook(h)
        ]

        # Add new CALM hooks
        result["hooks"][hook_type].extend(hook_list)

    return result


def register_mcp_server(
    claude_json_path: Path,
    dev_mode: bool = False,
    dev_directory: Path | None = None,
    dry_run: bool = False,
) -> str:
    """Register CALM MCP server in claude.json.

    Args:
        claude_json_path: Path to ~/.claude.json
        dev_mode: Use development directory path
        dev_directory: Path to development directory (for dev_mode)
        dry_run: If True, don't write changes

    Returns:
        Description of what was done

    Raises:
        ConfigError: If registration fails
    """
    # Build server command
    if dev_mode:
        if dev_directory is None:
            dev_directory = Path.cwd()
        server_command = [
            "uv",
            "run",
            "--directory",
            str(dev_directory),
            "calm",
            "server",
            "run",
        ]
    else:
        # Production mode - use installed package
        server_command = ["calm", "server", "run"]

    # Read existing config
    config = read_json_config(claude_json_path)

    # Merge CALM server
    updated = merge_mcp_server(config, server_command)

    if dry_run:
        return f"Would update {claude_json_path} with CALM MCP server"

    # Write atomically
    atomic_write_json(claude_json_path, updated)

    return f"Registered CALM MCP server in {claude_json_path}"


def register_hooks(
    settings_path: Path,
    dry_run: bool = False,
) -> str:
    """Register CALM hooks in settings.json.

    Args:
        settings_path: Path to ~/.claude/settings.json
        dry_run: If True, don't write changes

    Returns:
        Description of what was done

    Raises:
        ConfigError: If registration fails
    """
    # Ensure parent directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing settings
    settings = read_json_config(settings_path)

    # Merge hooks
    updated = merge_hooks(settings, clean_old=True)

    if dry_run:
        return f"Would update {settings_path} with CALM hooks"

    # Write atomically
    atomic_write_json(settings_path, updated)

    return f"Registered CALM hooks in {settings_path}"
