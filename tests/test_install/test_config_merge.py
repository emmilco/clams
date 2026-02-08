"""Tests for config merging utilities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from calm.install.config_merge import (
    ConfigError,
    atomic_write_json,
    merge_hooks,
    merge_mcp_server,
    read_json_config,
    register_hooks,
    register_mcp_server,
)


class TestReadJsonConfig:
    """Tests for read_json_config."""

    def test_read_existing_file(self, tmp_path: Path) -> None:
        """Should read existing JSON file."""
        path = tmp_path / "test.json"
        path.write_text('{"key": "value"}')

        result = read_json_config(path)
        assert result == {"key": "value"}

    def test_read_missing_file(self, tmp_path: Path) -> None:
        """Should return empty dict for missing file."""
        path = tmp_path / "nonexistent.json"
        result = read_json_config(path)
        assert result == {}

    def test_read_empty_file(self, tmp_path: Path) -> None:
        """Should return empty dict for empty file."""
        path = tmp_path / "empty.json"
        path.write_text("")

        result = read_json_config(path)
        assert result == {}

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        """Should raise ConfigError for invalid JSON."""
        path = tmp_path / "invalid.json"
        path.write_text("not valid json")

        with pytest.raises(ConfigError) as excinfo:
            read_json_config(path)
        assert "Invalid JSON" in str(excinfo.value)

    def test_read_non_object_json(self, tmp_path: Path) -> None:
        """Should raise ConfigError for non-object JSON."""
        path = tmp_path / "array.json"
        path.write_text("[1, 2, 3]")

        with pytest.raises(ConfigError) as excinfo:
            read_json_config(path)
        assert "expected object" in str(excinfo.value)


class TestAtomicWriteJson:
    """Tests for atomic_write_json."""

    def test_creates_file(self, tmp_path: Path) -> None:
        """Should create file with correct content."""
        path = tmp_path / "test.json"
        data = {"key": "value"}

        atomic_write_json(path, data)

        assert path.exists()
        assert json.loads(path.read_text()) == data

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories."""
        path = tmp_path / "deep" / "nested" / "test.json"
        data = {"key": "value"}

        atomic_write_json(path, data)

        assert path.exists()

    def test_overwrites_existing(self, tmp_path: Path) -> None:
        """Should overwrite existing file."""
        path = tmp_path / "test.json"
        path.write_text('{"old": "data"}')

        atomic_write_json(path, {"new": "data"})

        assert json.loads(path.read_text()) == {"new": "data"}

    def test_no_corruption_on_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Original file should be unchanged on write error."""
        path = tmp_path / "test.json"
        original = {"original": True}
        path.write_text(json.dumps(original))

        # Make json.dump fail
        def fail_dump(*args: Any, **kwargs: Any) -> None:
            raise OSError("Simulated failure")

        monkeypatch.setattr(json, "dump", fail_dump)

        with pytest.raises(ConfigError):
            atomic_write_json(path, {"new": True})

        # Original should be unchanged
        assert json.loads(path.read_text()) == original


class TestMergeMcpServer:
    """Tests for merge_mcp_server."""

    def test_empty_config(self) -> None:
        """Should create mcpServers section with SSE entry."""
        result = merge_mcp_server({}, "http://127.0.0.1:6335/sse")
        assert "mcpServers" in result
        assert "calm" in result["mcpServers"]
        assert result["mcpServers"]["calm"]["type"] == "sse"
        assert result["mcpServers"]["calm"]["url"] == "http://127.0.0.1:6335/sse"

    def test_preserves_other_servers(self) -> None:
        """Should preserve existing MCP servers."""
        config = {"mcpServers": {"other": {"command": "other"}}}
        result = merge_mcp_server(config, "http://127.0.0.1:6335/sse")

        assert "other" in result["mcpServers"]
        assert "calm" in result["mcpServers"]

    def test_preserves_other_keys(self) -> None:
        """Should preserve non-mcpServers keys."""
        config = {"someOtherKey": "value", "mcpServers": {}}
        result = merge_mcp_server(config, "http://127.0.0.1:6335/sse")

        assert result["someOtherKey"] == "value"

    def test_updates_existing_calm(self) -> None:
        """Should update existing calm server entry to SSE."""
        config = {
            "mcpServers": {
                "calm": {"command": "old", "args": ["old"]}
            }
        }
        result = merge_mcp_server(config, "http://127.0.0.1:9000/sse")

        assert result["mcpServers"]["calm"]["type"] == "sse"
        assert result["mcpServers"]["calm"]["url"] == "http://127.0.0.1:9000/sse"
        assert "command" not in result["mcpServers"]["calm"]
        assert "args" not in result["mcpServers"]["calm"]

    def test_does_not_mutate_original(self) -> None:
        """Should not mutate the original config."""
        config = {"mcpServers": {"other": {"command": "other"}}}
        original_copy = json.loads(json.dumps(config))

        merge_mcp_server(config, "http://127.0.0.1:6335/sse")

        assert config == original_copy


class TestMergeHooks:
    """Tests for merge_hooks."""

    def test_empty_settings(self) -> None:
        """Should create hooks section."""
        result = merge_hooks({})
        assert "hooks" in result
        assert "SessionStart" in result["hooks"]
        assert "UserPromptSubmit" in result["hooks"]
        assert "PreToolUse" in result["hooks"]
        assert "PostToolUse" in result["hooks"]

    def test_preserves_other_settings(self) -> None:
        """Should preserve non-hook settings."""
        settings = {"alwaysThinkingEnabled": True}
        result = merge_hooks(settings)

        assert result["alwaysThinkingEnabled"] is True
        assert "hooks" in result

    def test_cleans_old_clams_hooks(self) -> None:
        """Should remove old clams_scripts references."""
        settings = {
            "hooks": {
                "SessionStart": [
                    {"hooks": [{"command": "clams_scripts/hooks/session_start.py"}]}
                ]
            }
        }
        result = merge_hooks(settings, clean_old=True)

        # Old hook should be removed, CALM hook should be added
        session_hooks = result["hooks"]["SessionStart"]
        assert len(session_hooks) == 1
        assert "calm.hooks" in session_hooks[0]["hooks"][0]["command"]

    def test_idempotent(self) -> None:
        """Running merge twice should produce same result."""
        settings: dict[str, Any] = {}
        result1 = merge_hooks(settings)
        result2 = merge_hooks(result1)

        # Should have same number of hooks
        for hook_type in ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"]:
            assert len(result1["hooks"][hook_type]) == len(result2["hooks"][hook_type])

    def test_preserves_user_hooks(self) -> None:
        """Should preserve user's non-CALM hooks."""
        settings = {
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Write",
                        "hooks": [{"type": "command", "command": "echo custom"}]
                    }
                ]
            }
        }
        result = merge_hooks(settings)

        # Should have both user hook and CALM hook
        pre_tool_hooks = result["hooks"]["PreToolUse"]
        assert len(pre_tool_hooks) == 2


class TestRegisterMcpServer:
    """Tests for register_mcp_server."""

    def test_creates_file_if_missing(self, tmp_path: Path) -> None:
        """Should create claude.json if missing with SSE config."""
        path = tmp_path / ".claude.json"

        register_mcp_server(path)

        assert path.exists()
        config = json.loads(path.read_text())
        assert "mcpServers" in config
        assert "calm" in config["mcpServers"]
        calm_entry = config["mcpServers"]["calm"]
        assert calm_entry["type"] == "sse"
        assert "url" in calm_entry
        assert calm_entry["url"].endswith("/sse")

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        """Dry run should not create file."""
        path = tmp_path / ".claude.json"

        message = register_mcp_server(path, dry_run=True)

        assert "Would update" in message
        assert not path.exists()

    def test_registered_server_uses_sse_transport(self, tmp_path: Path) -> None:
        """Registered server must use SSE transport, not command-based."""
        path = tmp_path / ".claude.json"
        register_mcp_server(path)
        config = json.loads(path.read_text())
        calm_entry = config["mcpServers"]["calm"]
        assert calm_entry["type"] == "sse"
        assert "url" in calm_entry
        assert calm_entry["url"].endswith("/sse")
        assert "command" not in calm_entry
        assert "args" not in calm_entry


class TestRegisterHooks:
    """Tests for register_hooks."""

    def test_creates_file_and_directory(self, tmp_path: Path) -> None:
        """Should create settings.json and parent directory."""
        path = tmp_path / ".claude" / "settings.json"

        register_hooks(path)

        assert path.exists()
        settings = json.loads(path.read_text())
        assert "hooks" in settings

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        """Dry run should not create file."""
        path = tmp_path / ".claude" / "settings.json"

        message = register_hooks(path, dry_run=True)

        assert "Would update" in message
        assert not path.exists()
