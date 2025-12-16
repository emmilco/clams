"""Tests for server configuration.

Tests the canonical configuration module (R8-A: Create Canonical Configuration Module).
Reference: BUG-033 (server command issues), BUG-037 (timeout issues)
"""

import os
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from clams.server.config import ServerSettings


class TestDefaultSettings:
    """Test default configuration values."""

    def test_storage_paths(self) -> None:
        """Test default storage path settings."""
        settings = ServerSettings()

        assert settings.storage_path == "~/.clams"
        assert settings.sqlite_path == "~/.clams/metadata.db"
        assert settings.journal_path == ".claude/journal"

    def test_server_configuration(self) -> None:
        """Test default server configuration.

        Reference: BUG-033 - Must use venv binary, not python -m.
        """
        settings = ServerSettings()

        assert settings.server_command == ".venv/bin/clams-server"
        assert settings.http_host == "127.0.0.1"
        assert settings.http_port == 6334

    def test_pid_and_log_file_paths(self) -> None:
        """Test default PID file and log file settings.

        Reference: SPEC-029 - Canonical configuration module.
        """
        settings = ServerSettings()

        assert settings.pid_file == "~/.clams/server.pid"
        assert settings.log_file == "~/.clams/server.log"

    def test_timeout_configuration(self) -> None:
        """Test default timeout settings.

        Reference: BUG-037 - Verification timeout must account for heavy imports.
        """
        settings = ServerSettings()

        # 15 seconds accounts for PyTorch import time (BUG-037)
        assert settings.verification_timeout == 15
        # 5 seconds for hook HTTP calls
        assert settings.http_call_timeout == 5
        # 5.0 seconds for Qdrant operations
        assert settings.qdrant_timeout == 5.0

    def test_qdrant_configuration(self) -> None:
        """Test default Qdrant settings."""
        settings = ServerSettings()

        assert settings.qdrant_url == "http://localhost:6333"

    def test_embedding_configuration(self) -> None:
        """Test default embedding model settings."""
        settings = ServerSettings()

        assert settings.embedding_model == "nomic-ai/nomic-embed-text-v1.5"
        assert settings.embedding_dimension == 768
        assert settings.code_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert settings.semantic_model == "nomic-ai/nomic-embed-text-v1.5"

    def test_clustering_configuration(self) -> None:
        """Test default HDBSCAN clustering settings.

        These values should match production defaults per R6-B.
        """
        settings = ServerSettings()

        assert settings.hdbscan_min_cluster_size == 5
        assert settings.hdbscan_min_samples == 3

    def test_ghap_configuration(self) -> None:
        """Test default GHAP settings."""
        settings = ServerSettings()

        assert settings.ghap_check_frequency == 10

    def test_logging_configuration(self) -> None:
        """Test default logging settings."""
        settings = ServerSettings()

        assert settings.log_level == "INFO"
        assert settings.log_format == "json"

    def test_git_configuration(self) -> None:
        """Test default git settings."""
        settings = ServerSettings()

        assert settings.repo_path is None


class TestEnvironmentOverride:
    """Test environment variable overrides."""

    def test_storage_path_override(self) -> None:
        """Test that storage path can be overridden via environment."""
        with patch.dict(os.environ, {"CLAMS_STORAGE_PATH": "/custom/path"}):
            settings = ServerSettings()
            assert settings.storage_path == "/custom/path"

    def test_log_level_override(self) -> None:
        """Test that log level can be overridden via environment."""
        with patch.dict(os.environ, {"CLAMS_LOG_LEVEL": "DEBUG"}):
            settings = ServerSettings()
            assert settings.log_level == "DEBUG"

    def test_embedding_dimension_override(self) -> None:
        """Test that embedding dimension can be overridden via environment."""
        with patch.dict(os.environ, {"CLAMS_EMBEDDING_DIMENSION": "512"}):
            settings = ServerSettings()
            assert settings.embedding_dimension == 512

    def test_server_command_override(self) -> None:
        """Test that server command can be overridden via environment."""
        with patch.dict(os.environ, {"CLAMS_SERVER_COMMAND": "/custom/clams"}):
            settings = ServerSettings()
            assert settings.server_command == "/custom/clams"

    def test_timeout_override(self) -> None:
        """Test that timeouts can be overridden via environment."""
        with patch.dict(
            os.environ,
            {
                "CLAMS_VERIFICATION_TIMEOUT": "30",
                "CLAMS_HTTP_CALL_TIMEOUT": "10",
            },
        ):
            settings = ServerSettings()
            assert settings.verification_timeout == 30
            assert settings.http_call_timeout == 10


class TestSettingsMetadata:
    """Test settings metadata and model configuration."""

    def test_env_prefix(self) -> None:
        """Test that settings use CLAMS_ prefix."""
        settings = ServerSettings()
        assert settings.model_config["env_prefix"] == "CLAMS_"


class TestExportForShell:
    """Test shell configuration export functionality."""

    def test_export_creates_file(self) -> None:
        """Test that export_for_shell creates the config file."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            assert config_path.exists()

    def test_export_creates_parent_directories(self) -> None:
        """Test that export_for_shell creates parent directories."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nested" / "dir" / "config.env"
            settings.export_for_shell(config_path)

            assert config_path.exists()
            assert config_path.parent.exists()

    def test_export_accepts_string_path(self) -> None:
        """Test that export_for_shell accepts string paths."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = f"{tmpdir}/config.env"
            settings.export_for_shell(config_path)

            assert Path(config_path).exists()

    def test_export_contains_required_values(self) -> None:
        """Test that exported config contains all required values."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # Server configuration
            assert "CLAMS_SERVER_COMMAND=.venv/bin/clams-server" in content
            assert "CLAMS_HTTP_HOST=127.0.0.1" in content
            assert "CLAMS_HTTP_PORT=6334" in content

            # Timeouts
            assert "CLAMS_VERIFICATION_TIMEOUT=15" in content
            assert "CLAMS_HTTP_CALL_TIMEOUT=5" in content

            # Clustering
            assert "CLAMS_HDBSCAN_MIN_CLUSTER_SIZE=5" in content
            assert "CLAMS_HDBSCAN_MIN_SAMPLES=3" in content

    def test_export_contains_pid_and_log_file(self) -> None:
        """Test that exported config contains PID and log file paths.

        Reference: SPEC-029 - Shell scripts need access to PID/log paths.
        """
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # PID and log file should be exported
            assert "CLAMS_PID_FILE=" in content
            assert "CLAMS_LOG_FILE=" in content

    def test_export_expands_tilde_paths(self) -> None:
        """Test that paths with ~ are expanded in shell export.

        Reference: SPEC-029 - Shell scripts receive absolute paths.
        """
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # Paths should NOT contain ~ (should be expanded)
            # Extract lines with file paths
            for line in content.splitlines():
                if "=" in line and ("PATH" in line or "FILE" in line):
                    key, value = line.split("=", 1)
                    # Skip non-path lines like JOURNAL_PATH (relative path)
                    if key == "CLAMS_JOURNAL_PATH":
                        continue
                    assert "~" not in value, (
                        f"Path {key} should be expanded, got: {value}"
                    )

    def test_export_contains_collection_names(self) -> None:
        """Test that exported config contains collection names.

        Reference: SPEC-029 - Shell scripts may need collection names.
        """
        from clams.search.collections import CollectionName

        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            content = config_path.read_text()

            # Collection names should be exported
            assert f"CLAMS_COLLECTION_MEMORIES={CollectionName.MEMORIES}" in content
            assert f"CLAMS_COLLECTION_CODE={CollectionName.CODE}" in content
            assert f"CLAMS_COLLECTION_COMMITS={CollectionName.COMMITS}" in content
            assert f"CLAMS_COLLECTION_VALUES={CollectionName.VALUES}" in content
            assert (
                f"CLAMS_COLLECTION_GHAP_FULL={CollectionName.EXPERIENCES_FULL}"
                in content
            )

    def test_export_all_paths_readable_by_bash(self) -> None:
        """Test that all exported paths can be read by bash.

        Reference: SPEC-029 - Hooks source this file.
        """
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            # Source the file and echo PID_FILE to verify paths work
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"source {config_path} && echo $CLAMS_PID_FILE",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            # Should be absolute path (expanded)
            assert result.stdout.strip().startswith("/")

    def test_export_is_shell_sourceable(self) -> None:
        """Test that exported config can be sourced by bash.

        This is a critical test: hooks source this file, so it must be
        valid bash syntax.
        """
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            # Source the file and echo a value to verify it works
            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f"source {config_path} && echo $CLAMS_SERVER_COMMAND",
                ],
                capture_output=True,
                text=True,
            )

            assert result.returncode == 0
            assert result.stdout.strip() == ".venv/bin/clams-server"

    def test_export_values_roundtrip(self) -> None:
        """Test that exported values match the settings object."""
        settings = ServerSettings()

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.env"
            settings.export_for_shell(config_path)

            # Parse the exported file
            exported = {}
            for line in config_path.read_text().splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    exported[key] = value

            # Verify key values match
            assert exported["CLAMS_SERVER_COMMAND"] == settings.server_command
            assert exported["CLAMS_HTTP_HOST"] == settings.http_host
            assert exported["CLAMS_HTTP_PORT"] == str(settings.http_port)
            assert (
                exported["CLAMS_VERIFICATION_TIMEOUT"]
                == str(settings.verification_timeout)
            )
            assert exported["CLAMS_HTTP_CALL_TIMEOUT"] == str(settings.http_call_timeout)
            assert (
                exported["CLAMS_HDBSCAN_MIN_CLUSTER_SIZE"]
                == str(settings.hdbscan_min_cluster_size)
            )
            assert (
                exported["CLAMS_HDBSCAN_MIN_SAMPLES"]
                == str(settings.hdbscan_min_samples)
            )

    def test_export_with_custom_values(self) -> None:
        """Test that exported config reflects custom values."""
        with patch.dict(
            os.environ,
            {
                "CLAMS_SERVER_COMMAND": "/custom/server",
                "CLAMS_VERIFICATION_TIMEOUT": "30",
            },
        ):
            settings = ServerSettings()

            with tempfile.TemporaryDirectory() as tmpdir:
                config_path = Path(tmpdir) / "config.env"
                settings.export_for_shell(config_path)

                content = config_path.read_text()

                assert "CLAMS_SERVER_COMMAND=/custom/server" in content
                assert "CLAMS_VERIFICATION_TIMEOUT=30" in content


class TestGetConfigEnvPath:
    """Test config path discovery."""

    def test_default_path(self) -> None:
        """Test default config.env path."""
        settings = ServerSettings()
        path = settings.get_config_env_path()

        assert path == Path.home() / ".clams" / "config.env"

    def test_custom_storage_path(self) -> None:
        """Test config path with custom storage path."""
        with patch.dict(os.environ, {"CLAMS_STORAGE_PATH": "/custom/storage"}):
            settings = ServerSettings()
            path = settings.get_config_env_path()

            assert path == Path("/custom/storage/config.env")


class TestFieldDescriptions:
    """Test that all fields have descriptions for documentation."""

    def test_all_fields_have_descriptions(self) -> None:
        """Verify all ServerSettings fields have descriptions.

        This ensures documentation quality per R8-A requirements.
        """
        # Access model_fields from the class, not instance (Pydantic v2.11+)
        for field_name, field_info in ServerSettings.model_fields.items():
            assert field_info.description is not None, (
                f"Field '{field_name}' is missing a description"
            )
            assert len(field_info.description) > 10, (
                f"Field '{field_name}' has a too-short description"
            )


class TestStorageSettingsRemoval:
    """Test that StorageSettings has been removed.

    Reference: SPEC-029 - Single source of truth from ServerSettings.
    """

    def test_storage_settings_import_fails(self) -> None:
        """Verify StorageSettings is no longer available.

        Reference: SPEC-029 - Eliminates duplicate configuration.
        """
        with pytest.raises(ImportError):
            from clams.storage import StorageSettings  # noqa: F401

    def test_qdrant_vector_store_uses_server_settings(self) -> None:
        """Verify QdrantVectorStore gets defaults from ServerSettings."""
        from clams.storage.qdrant import QdrantVectorStore

        # Create instance with explicit in-memory mode
        store = QdrantVectorStore(url=":memory:")

        # Verify defaults come from ServerSettings, not old StorageSettings
        settings = ServerSettings()
        assert store._timeout == settings.qdrant_timeout


class TestConfigurationParity:
    """Test configuration parity between Python and hooks.

    Reference: R6-B - Configuration Parity Verification
    """

    def test_clustering_uses_production_defaults(self) -> None:
        """Verify clustering config uses production defaults.

        Reference: BUG-031 showed tests used different values than production.
        """
        settings = ServerSettings()

        # These must match production values per R6-B
        assert settings.hdbscan_min_cluster_size == 5
        assert settings.hdbscan_min_samples == 3

    @pytest.mark.skipif(
        not Path("clams/hooks/config.yaml").exists(),
        reason="Hooks config not found",
    )
    def test_server_command_matches_hooks_config(self) -> None:
        """Verify server command matches hooks config.yaml.

        Reference: BUG-033 - hooks used wrong server command.
        """
        import yaml

        settings = ServerSettings()

        with open("clams/hooks/config.yaml") as f:
            hooks_config = yaml.safe_load(f)

        # Get server command from hooks config
        hooks_server_cmd = hooks_config.get("mcp", {}).get("server_command", [])
        if hooks_server_cmd:
            # hooks config stores as list, ServerSettings stores as string
            assert settings.server_command == hooks_server_cmd[0], (
                f"Server command mismatch: "
                f"ServerSettings={settings.server_command}, "
                f"hooks={hooks_server_cmd[0]}"
            )
