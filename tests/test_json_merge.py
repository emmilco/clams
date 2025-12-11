"""Unit tests for scripts/json_merge.py."""

import json
import sys
import tempfile
from pathlib import Path

# Add scripts directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from json_merge import merge_mcp_server, merge_hooks, remove_mcp_server, remove_hooks


def test_merge_mcp_server_new() -> None:
    """Test adding server to empty config."""
    config: dict[str, dict[str, dict[str, str]]] = {}
    server_config = {"type": "stdio", "command": "/path/to/server"}

    result, changed = merge_mcp_server(config, "test", server_config)

    assert changed
    assert result["mcpServers"]["test"] == server_config


def test_merge_mcp_server_existing() -> None:
    """Test adding server when already exists."""
    config = {"mcpServers": {"test": {"type": "stdio", "command": "/old"}}}
    server_config = {"type": "stdio", "command": "/new"}

    result, changed = merge_mcp_server(config, "test", server_config)

    assert changed
    assert result["mcpServers"]["test"]["command"] == "/new"


def test_merge_mcp_server_no_change() -> None:
    """Test that identical config returns no change."""
    config = {"mcpServers": {"test": {"type": "stdio", "command": "/path"}}}
    server_config = {"type": "stdio", "command": "/path"}

    result, changed = merge_mcp_server(config, "test", server_config)

    assert not changed
    assert result["mcpServers"]["test"]["command"] == "/path"


def test_merge_hooks_preserves_existing() -> None:
    """Test that merging hooks preserves other hooks."""
    config = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "/other/hook.sh"}]}
            ]
        }
    }

    new_hooks = {
        "SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": "/clams/hook.sh"}]}
        ]
    }

    result, changed = merge_hooks(config, new_hooks)

    assert changed
    assert len(result["hooks"]["SessionStart"]) == 2
    assert result["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "/other/hook.sh"
    assert result["hooks"]["SessionStart"][1]["hooks"][0]["command"] == "/clams/hook.sh"


def test_merge_hooks_new_event() -> None:
    """Test adding hooks for a new event type."""
    config: dict[str, dict[str, list[dict[str, list[dict[str, str]]]]]] = {"hooks": {}}

    new_hooks = {
        "UserPromptSubmit": [
            {"hooks": [{"type": "command", "command": "/path/to/hook.sh"}]}
        ]
    }

    result, changed = merge_hooks(config, new_hooks)

    assert changed
    assert len(result["hooks"]["UserPromptSubmit"]) == 1
    assert result["hooks"]["UserPromptSubmit"][0]["hooks"][0]["command"] == "/path/to/hook.sh"


def test_merge_hooks_updates_existing() -> None:
    """Test updating an existing hook entry."""
    config = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "/clams/hook.sh"}]}
            ]
        }
    }

    new_hooks = {
        "SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": "/clams/hook.sh"}]}
        ]
    }

    result, changed = merge_hooks(config, new_hooks)

    assert changed
    assert len(result["hooks"]["SessionStart"]) == 1
    assert result["hooks"]["SessionStart"][0]["matcher"] == "startup"


def test_merge_hooks_no_change() -> None:
    """Test that identical hook returns no change."""
    config = {
        "hooks": {
            "SessionStart": [
                {"matcher": "startup", "hooks": [{"type": "command", "command": "/clams/hook.sh"}]}
            ]
        }
    }

    new_hooks = {
        "SessionStart": [
            {"matcher": "startup", "hooks": [{"type": "command", "command": "/clams/hook.sh"}]}
        ]
    }

    result, changed = merge_hooks(config, new_hooks)

    assert not changed


def test_remove_mcp_server() -> None:
    """Test removing an MCP server."""
    config = {
        "mcpServers": {
            "clams": {"type": "stdio", "command": "/path"},
            "other": {"type": "stdio", "command": "/other"}
        }
    }

    result, changed = remove_mcp_server(config, "clams")

    assert changed
    assert "clams" not in result["mcpServers"]
    assert "other" in result["mcpServers"]


def test_remove_mcp_server_not_found() -> None:
    """Test removing a server that doesn't exist."""
    config = {"mcpServers": {"other": {"type": "stdio", "command": "/other"}}}

    result, changed = remove_mcp_server(config, "clams")

    assert not changed
    assert "other" in result["mcpServers"]


def test_remove_hooks() -> None:
    """Test removing hook entries by command."""
    config = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "/clams/hook.sh"}]},
                {"hooks": [{"type": "command", "command": "/other/hook.sh"}]}
            ]
        }
    }

    result, changed = remove_hooks(config, ["/clams/hook.sh"])

    assert changed
    assert len(result["hooks"]["SessionStart"]) == 1
    assert result["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "/other/hook.sh"


def test_remove_hooks_multiple_commands() -> None:
    """Test removing multiple hook commands."""
    config = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "/clams/hook1.sh"}]},
                {"hooks": [{"type": "command", "command": "/clams/hook2.sh"}]},
                {"hooks": [{"type": "command", "command": "/other/hook.sh"}]}
            ]
        }
    }

    result, changed = remove_hooks(config, ["/clams/hook1.sh", "/clams/hook2.sh"])

    assert changed
    assert len(result["hooks"]["SessionStart"]) == 1
    assert result["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "/other/hook.sh"


def test_remove_hooks_not_found() -> None:
    """Test removing hooks that don't exist."""
    config = {
        "hooks": {
            "SessionStart": [
                {"hooks": [{"type": "command", "command": "/other/hook.sh"}]}
            ]
        }
    }

    result, changed = remove_hooks(config, ["/clams/hook.sh"])

    assert not changed
    assert len(result["hooks"]["SessionStart"]) == 1
