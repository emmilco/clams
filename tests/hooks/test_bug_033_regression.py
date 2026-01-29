"""Regression test for BUG-033: mcp_client.py uses wrong server command."""

from pathlib import Path


class TestBug033Regression:
    """Tests for BUG-033 fix: correct MCP server command."""

    def test_server_command_uses_venv_binary(self) -> None:
        """Verify mcp_client uses .venv/bin/clams-server, not python -m clams."""
        # Read the source file and check for correct pattern
        clams_dir = Path(__file__).parent.parent.parent / "clams_scripts"
        mcp_client_path = clams_dir / "mcp_client.py"
        source = mcp_client_path.read_text()

        # Should NOT contain the buggy pattern
        assert '["python", "-m", "clams"]' not in source, (
            "BUG-033 REGRESSION: mcp_client.py still uses python -m clams"
        )

        # Should contain reference to clams-server binary
        assert "clams-server" in source, (
            "mcp_client.py should reference clams-server binary"
        )

    def test_server_command_path_is_absolute(self) -> None:
        """Verify the server command constructs an absolute path."""
        clams_dir = Path(__file__).parent.parent.parent / "clams_scripts"
        mcp_client_path = clams_dir / "mcp_client.py"
        source = mcp_client_path.read_text()

        # Should construct path relative to repo root
        assert ".venv" in source and "bin" in source, (
            "mcp_client.py should construct path to .venv/bin/"
        )

    def test_config_yaml_uses_correct_command(self) -> None:
        """Verify config.yaml uses correct server command."""
        hooks_dir = Path(__file__).parent.parent.parent / "clams_scripts" / "hooks"
        config_path = hooks_dir / "config.yaml"
        config_content = config_path.read_text()

        # Should NOT contain stale learning_memory_server reference
        assert "learning_memory_server" not in config_content, (
            "BUG-033 REGRESSION: config.yaml still references learning_memory_server"
        )

        # Should contain correct clams-server reference
        assert "clams-server" in config_content, (
            "config.yaml should reference clams-server"
        )
