"""Production command verification tests.

This module verifies that test utilities return commands matching production
hook usage. It extends SPEC-024's configuration parity work to cover
command invocation patterns.

Reference: SPEC-025 (Production Command Verification in Tests)
Related bugs: BUG-033 (Hook server command mismatch)
"""

import inspect
from pathlib import Path

import pytest

from tests.conftest import get_server_command

from .conftest import get_repo_root


class TestGetServerCommandUtility:
    """Verify get_server_command() utility behavior."""

    def test_default_returns_binary_with_http(self) -> None:
        """Verify default command uses binary with --http flag."""
        cmd = get_server_command()

        assert "clams-server" in cmd[0] or "clams.server.main" in " ".join(cmd)
        assert "--http" in cmd

    def test_daemon_flag_included_when_requested(self) -> None:
        """Verify --daemon flag is included when daemon=True."""
        cmd = get_server_command(daemon=True)

        assert "--daemon" in cmd

    def test_host_and_port_included_when_specified(self) -> None:
        """Verify host and port are included when specified."""
        cmd = get_server_command(host="0.0.0.0", port=8080)

        assert "--host" in cmd
        host_idx = cmd.index("--host")
        assert cmd[host_idx + 1] == "0.0.0.0"

        assert "--port" in cmd
        port_idx = cmd.index("--port")
        assert cmd[port_idx + 1] == "8080"

    def test_module_mode_returns_python_m_command(self) -> None:
        """Verify use_module=True returns python -m style command."""
        cmd = get_server_command(use_module=True)

        # Should use python -m pattern
        assert "-m" in cmd
        assert "clams.server.main" in cmd

    def test_binary_mode_returns_clams_server(self) -> None:
        """Verify use_module=False (default) returns clams-server binary."""
        cmd = get_server_command(use_module=False)

        # Should use binary directly
        assert "clams-server" in cmd[0]
        assert "-m" not in cmd

    def test_http_flag_can_be_disabled(self) -> None:
        """Verify http=False omits the --http flag."""
        cmd = get_server_command(http=False)

        assert "--http" not in cmd

    def test_all_flags_combined(self) -> None:
        """Verify all flags work together correctly."""
        cmd = get_server_command(
            http=True,
            daemon=True,
            host="127.0.0.1",
            port=6334,
            use_module=True,
        )

        assert "-m" in cmd
        assert "clams.server.main" in cmd
        assert "--http" in cmd
        assert "--daemon" in cmd
        assert "--host" in cmd
        assert "127.0.0.1" in cmd
        assert "--port" in cmd
        assert "6334" in cmd

    def test_warns_when_venv_not_found(self, tmp_path: Path) -> None:
        """Verify warning exists in code for when venv python/binary not found.

        Note: This test verifies the warning exists in the source code.
        The actual warning path is only exercised when venv is missing,
        which is typically not the case in CI.
        """
        # Verify the warning mechanism exists in the code
        from tests import conftest

        source = inspect.getsource(conftest.get_server_command)
        assert "warnings.warn" in source, (
            "get_server_command should warn when venv not found. See SPEC-025."
        )
        assert "UserWarning" in source, (
            "get_server_command should issue UserWarning on fallback."
        )


class TestCommandMatchesHooks:
    """Verify test utility commands match production hook patterns."""

    def test_module_command_matches_session_start_hook(self) -> None:
        """Verify get_server_command(use_module=True) matches session_start.sh.

        The hook uses: "$REPO_ROOT/.venv/bin/python" -m clams.server.main --http --daemon
        """
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        hook_content = hook_path.read_text()

        # Extract the command pattern from the hook
        # Pattern: .venv/bin/python -m clams.server.main
        assert ".venv/bin/python" in hook_content, (
            "session_start.sh should use .venv/bin/python"
        )
        assert "-m clams.server.main" in hook_content, (
            "session_start.sh should use -m clams.server.main"
        )
        assert "--http" in hook_content, "session_start.sh should use --http flag"
        assert "--daemon" in hook_content, "session_start.sh should use --daemon flag"

        # Verify our utility produces matching structure
        cmd = get_server_command(http=True, daemon=True, use_module=True)

        # Check structural match (path may vary, but pattern is same)
        assert "-m" in cmd
        assert "clams.server.main" in cmd
        assert "--http" in cmd
        assert "--daemon" in cmd

    def test_binary_command_matches_mcp_test_fixture(self) -> None:
        """Verify get_server_command() matches test_mcp_protocol.py fixture.

        The test uses: .venv/bin/clams-server (via StdioServerParameters)
        """
        test_path = get_repo_root() / "tests" / "integration" / "test_mcp_protocol.py"
        test_content = test_path.read_text()

        # Verify test uses clams-server binary
        assert ".venv/bin/clams-server" in test_content, (
            "test_mcp_protocol.py should use .venv/bin/clams-server"
        )

        # Verify our utility produces matching command
        cmd = get_server_command(http=False)  # MCP test uses stdio, not http

        # Should use clams-server binary
        assert "clams-server" in cmd[0], (
            "get_server_command() should return clams-server binary by default"
        )

    def test_host_port_match_server_settings(self) -> None:
        """Verify default host/port from utility matches ServerSettings."""
        from clams.server.config import ServerSettings

        settings = ServerSettings()

        # When host/port not specified, utility doesn't add them
        # But when specified, they should match production defaults
        cmd = get_server_command(
            host=settings.http_host,
            port=settings.http_port,
        )

        assert "--host" in cmd
        host_idx = cmd.index("--host")
        assert cmd[host_idx + 1] == settings.http_host

        assert "--port" in cmd
        port_idx = cmd.index("--port")
        assert cmd[port_idx + 1] == str(settings.http_port)


class TestCommandUsageInTests:
    """Verify integration tests use the canonical command utility.

    These tests ensure that integration tests don't hardcode commands
    that might diverge from production.
    """

    def test_mcp_protocol_test_uses_correct_pattern(self) -> None:
        """Verify test_mcp_protocol.py uses .venv/bin/clams-server.

        This test documents the expected pattern. The test should use
        the canonical path that matches ServerSettings.server_command.
        """
        from clams.server.config import ServerSettings

        settings = ServerSettings()
        test_path = get_repo_root() / "tests" / "integration" / "test_mcp_protocol.py"
        test_content = test_path.read_text()

        # Verify the test uses the same command as ServerSettings
        assert settings.server_command in test_content, (
            f"test_mcp_protocol.py should use {settings.server_command} "
            "(from ServerSettings.server_command). See SPEC-025."
        )

    def test_hook_validation_tests_use_correct_pattern(self) -> None:
        """Verify hook tests use commands matching production hooks."""
        hooks_test_path = get_repo_root() / "tests" / "hooks"

        if not hooks_test_path.exists():
            pytest.skip("No hooks test directory")

        # Check any test files that start servers
        for test_file in hooks_test_path.glob("test_*.py"):
            content = test_file.read_text()

            # If the file starts a server, verify it uses correct pattern
            if "subprocess" in content and "clams" in content:
                # Should use .venv/bin/python or clams-server, not bare python
                if "python -m clams" in content:
                    assert ".venv" in content or "venv" in content, (
                        f"{test_file.name} uses 'python -m clams' without venv. "
                        "Should use .venv/bin/python or get_server_command(). "
                        "See SPEC-025."
                    )


class TestCommandReturnValue:
    """Verify command return value structure and usability."""

    def test_returns_list_of_strings(self) -> None:
        """Verify return type is list[str] for subprocess compatibility."""
        cmd = get_server_command()

        assert isinstance(cmd, list)
        assert all(isinstance(arg, str) for arg in cmd)

    def test_command_usable_with_subprocess(self) -> None:
        """Verify command can be used directly with subprocess.

        Note: Does not actually run the command, just verifies structure.
        """
        import shlex

        cmd = get_server_command(http=True, daemon=True, host="127.0.0.1", port=6334)

        # Should be able to join into shell command
        shell_cmd = shlex.join(cmd)
        assert isinstance(shell_cmd, str)

        # Should contain expected components
        assert "clams-server" in shell_cmd or "clams.server.main" in shell_cmd

    def test_first_element_is_executable(self) -> None:
        """Verify first element of command is the executable."""
        cmd = get_server_command()

        # First element should be path to executable
        assert cmd[0].endswith("clams-server") or cmd[0] == "clams-server"

        cmd_module = get_server_command(use_module=True)
        # For module mode, first element is python executable
        assert "python" in cmd_module[0]
