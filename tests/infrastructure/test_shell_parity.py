"""Shell script configuration parity verification tests.

This module verifies that shell scripts (hooks) use configuration values
that match ServerSettings or properly source exported configuration.

Reference: SPEC-024 (Configuration Parity Verification)
Related bugs: BUG-033 (server command in hooks)
"""

import re
import tempfile
from pathlib import Path

import yaml

from clams.server.config import ServerSettings

from .conftest import get_repo_root


class TestConfigExport:
    """Verify ServerSettings.export_for_shell() produces correct output."""

    def test_export_includes_server_configuration(self) -> None:
        """Verify exported config includes server command, host, and port."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert f"CLAMS_SERVER_COMMAND={settings.server_command}" in content, (
                "Exported config missing CLAMS_SERVER_COMMAND. See SPEC-024."
            )
            assert f"CLAMS_HTTP_HOST={settings.http_host}" in content, (
                "Exported config missing CLAMS_HTTP_HOST. See SPEC-024."
            )
            assert f"CLAMS_HTTP_PORT={settings.http_port}" in content, (
                "Exported config missing CLAMS_HTTP_PORT. See SPEC-024."
            )

    def test_export_includes_timeout_configuration(self) -> None:
        """Verify exported config includes all timeout values."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert (
                f"CLAMS_VERIFICATION_TIMEOUT={settings.verification_timeout}" in content
            ), "Exported config missing CLAMS_VERIFICATION_TIMEOUT. See SPEC-024."
            assert (
                f"CLAMS_HTTP_CALL_TIMEOUT={settings.http_call_timeout}" in content
            ), "Exported config missing CLAMS_HTTP_CALL_TIMEOUT. See SPEC-024."
            assert f"CLAMS_QDRANT_TIMEOUT={settings.qdrant_timeout}" in content, (
                "Exported config missing CLAMS_QDRANT_TIMEOUT. See SPEC-024."
            )

    def test_export_includes_clustering_configuration(self) -> None:
        """Verify exported config includes HDBSCAN parameters."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert (
                f"CLAMS_HDBSCAN_MIN_CLUSTER_SIZE={settings.hdbscan_min_cluster_size}"
                in content
            ), "Exported config missing CLAMS_HDBSCAN_MIN_CLUSTER_SIZE. See SPEC-024."
            assert (
                f"CLAMS_HDBSCAN_MIN_SAMPLES={settings.hdbscan_min_samples}" in content
            ), "Exported config missing CLAMS_HDBSCAN_MIN_SAMPLES. See SPEC-024."

    def test_export_includes_ghap_configuration(self) -> None:
        """Verify exported config includes GHAP settings."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            assert (
                f"CLAMS_GHAP_CHECK_FREQUENCY={settings.ghap_check_frequency}" in content
            ), "Exported config missing CLAMS_GHAP_CHECK_FREQUENCY. See SPEC-024."

    def test_export_creates_parent_directories(self) -> None:
        """Verify export_for_shell creates parent directories if needed."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "dir" / "config.env"
            settings.export_for_shell(config_path)

            assert config_path.exists(), (
                "export_for_shell should create parent directories"
            )

    def test_export_is_shell_sourceable(self) -> None:
        """Verify exported config can be sourced by shell."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # Verify no shell syntax errors (basic check)
            # Each non-comment, non-empty line should be VAR=value
            for line in content.split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                assert "=" in line, (
                    f"Invalid shell assignment: {line}. "
                    "Exported config must be shell-sourceable."
                )

                # Verify no spaces around =
                var_part = line.split("=")[0]
                assert " " not in var_part, (
                    f"Invalid shell assignment: {line}. "
                    "Variable names cannot contain spaces."
                )


class TestShellScriptConfiguration:
    """Verify shell scripts use correct configuration values."""

    def test_session_start_uses_repo_relative_paths(self) -> None:
        """Verify session_start.sh constructs paths from REPO_ROOT.

        The hook should determine paths relative to the repository root,
        not rely on PATH or hardcoded absolute paths.
        """
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        # Should determine script location
        assert "SCRIPT_DIR=" in content, (
            "session_start.sh should determine SCRIPT_DIR. See SPEC-024."
        )

        # Should navigate to repo root
        assert "REPO_ROOT=" in content, (
            "session_start.sh should determine REPO_ROOT. See SPEC-024."
        )

        # Should use REPO_ROOT for server path
        assert "$REPO_ROOT" in content, (
            "session_start.sh should use $REPO_ROOT for paths. See SPEC-024."
        )

    def test_session_start_uses_venv_python(self) -> None:
        """Verify session_start.sh uses the venv Python for daemon mode.

        The hook should use .venv/bin/python to ensure the correct
        environment is used, avoiding BUG-033 type issues.
        """
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        assert ".venv/bin/python" in content or "clams-server" in content, (
            "session_start.sh should use .venv/bin/python or clams-server binary. "
            "See BUG-033 and SPEC-024."
        )

    def test_session_start_has_fallback(self) -> None:
        """Verify session_start.sh has fallback if venv unavailable."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        assert "command -v clams-server" in content, (
            "session_start.sh should check for clams-server in PATH as fallback. "
            "See SPEC-024."
        )

    def test_session_start_uses_configurable_port(self) -> None:
        """Verify session_start.sh uses configurable port, not hardcoded."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        settings = ServerSettings()

        # Should use environment variable with default
        # Pattern: SERVER_PORT="${CLAMS_PORT:-6334}" or similar
        port_pattern = r'SERVER_PORT=.*\$\{.*:-(\d+)\}'
        match = re.search(port_pattern, content)

        assert match, (
            "session_start.sh should use configurable port with default. "
            'Expected pattern like: SERVER_PORT="${CLAMS_PORT:-6334}". '
            "See SPEC-024."
        )

        default_port = int(match.group(1))
        assert default_port == settings.http_port, (
            f"session_start.sh default port is {default_port}, "
            f"but ServerSettings.http_port is {settings.http_port}. "
            "These should match. See SPEC-024."
        )

    def test_session_start_uses_configurable_host(self) -> None:
        """Verify session_start.sh uses configurable host, not hardcoded."""
        hook_path = get_repo_root() / "clams" / "hooks" / "session_start.sh"
        content = hook_path.read_text()

        settings = ServerSettings()

        # Pattern: SERVER_HOST="${CLAMS_HOST:-127.0.0.1}" or similar
        host_pattern = r'SERVER_HOST=.*\$\{.*:-([^}]+)\}'
        match = re.search(host_pattern, content)

        assert match, (
            "session_start.sh should use configurable host with default. "
            "See SPEC-024."
        )

        default_host = match.group(1)
        assert default_host == settings.http_host, (
            f"session_start.sh default host is {default_host}, "
            f"but ServerSettings.http_host is {settings.http_host}. "
            "These should match. See SPEC-024."
        )


class TestHooksConfigYaml:
    """Verify hooks/config.yaml values match ServerSettings."""

    def test_hooks_config_timeout_compatible_with_settings(self) -> None:
        """Verify hooks config timeouts are compatible with ServerSettings.

        The mcp.connection_timeout should be >= ServerSettings.http_call_timeout
        to allow for server startup time.
        """
        settings = ServerSettings()
        config_path = get_repo_root() / "clams" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        mcp_timeout = config.get("mcp", {}).get("connection_timeout", 10)

        # Connection timeout should allow for verification
        assert mcp_timeout >= settings.http_call_timeout, (
            f"hooks/config.yaml mcp.connection_timeout ({mcp_timeout}) "
            f"should be >= ServerSettings.http_call_timeout "
            f"({settings.http_call_timeout}). "
            "See SPEC-024."
        )

    def test_hooks_config_ghap_frequency_matches_settings(self) -> None:
        """Verify hooks config GHAP frequency matches ServerSettings.

        The hooks/config.yaml ghap_checkin.frequency should match
        ServerSettings.ghap_check_frequency.
        """
        settings = ServerSettings()
        config_path = get_repo_root() / "clams" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        hooks_config = config.get("hooks", {})
        ghap_config = hooks_config.get("ghap_checkin", {})
        hook_frequency = ghap_config.get("frequency")

        assert hook_frequency == settings.ghap_check_frequency, (
            f"hooks/config.yaml ghap_checkin.frequency is {hook_frequency}, "
            f"but ServerSettings.ghap_check_frequency is "
            f"{settings.ghap_check_frequency}. "
            "These should match. See SPEC-024."
        )

    def test_hooks_config_server_command_matches_settings(self) -> None:
        """Verify hooks config server command matches ServerSettings.

        The hooks/config.yaml mcp.server_command should match
        ServerSettings.server_command.
        """
        settings = ServerSettings()
        config_path = get_repo_root() / "clams" / "hooks" / "config.yaml"

        with open(config_path) as f:
            config = yaml.safe_load(f)

        mcp_config = config.get("mcp", {})
        server_command = mcp_config.get("server_command", [])

        # config.yaml uses array format, ServerSettings uses string
        # Check if the string form matches
        if isinstance(server_command, list):
            command_str = server_command[0] if server_command else ""
        else:
            command_str = server_command

        assert command_str == settings.server_command, (
            f"hooks/config.yaml mcp.server_command is {command_str}, "
            f"but ServerSettings.server_command is {settings.server_command}. "
            "These should match. See SPEC-024."
        )
