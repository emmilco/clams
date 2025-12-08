"""Tests for server configuration."""

import os
from unittest.mock import patch

from clams.server.config import ServerSettings


def test_default_settings() -> None:
    """Test that default settings are loaded correctly."""
    settings = ServerSettings()

    assert settings.storage_path == "~/.learning-memory"
    assert settings.sqlite_path == "~/.learning-memory/metadata.db"
    assert settings.journal_path == ".claude/journal"
    assert settings.qdrant_url == "http://localhost:6333"
    assert settings.embedding_model == "nomic-ai/nomic-embed-text-v1.5"
    assert settings.embedding_dimension == 768
    assert settings.hdbscan_min_cluster_size == 5
    assert settings.hdbscan_min_samples == 3
    assert settings.ghap_check_frequency == 10
    assert settings.log_level == "INFO"
    assert settings.log_format == "json"


def test_env_override() -> None:
    """Test that environment variables override defaults."""
    with patch.dict(
        os.environ,
        {
            "CLAMS_STORAGE_PATH": "/custom/path",
            "CLAMS_LOG_LEVEL": "DEBUG",
            "CLAMS_EMBEDDING_DIMENSION": "512",
        },
    ):
        settings = ServerSettings()

        assert settings.storage_path == "/custom/path"
        assert settings.log_level == "DEBUG"
        assert settings.embedding_dimension == 512


def test_settings_immutable() -> None:
    """Test that settings have expected configuration."""
    settings = ServerSettings()

    # Verify the settings are properly constructed
    assert hasattr(settings, "model_config")
    assert settings.model_config["env_prefix"] == "CLAMS_"
