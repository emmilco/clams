"""Tests for CALM configuration module."""

import os
from unittest.mock import patch

from calm.config import CALM_HOME, DEFAULT_CONFIG, CalmSettings


class TestCalmSettings:
    """Tests for CalmSettings class."""

    def test_default_values(self) -> None:
        """Test that default values are set correctly."""
        settings = CalmSettings()

        assert settings.home == CALM_HOME
        assert settings.server_host == "127.0.0.1"
        assert settings.server_port == 6335
        assert settings.log_level == "info"
        assert settings.qdrant_url == "http://localhost:6333"

    def test_env_override(self) -> None:
        """Test that environment variables override defaults."""
        with patch.dict(os.environ, {"CALM_SERVER_PORT": "8080"}):
            settings = CalmSettings()
            assert settings.server_port == 8080

    def test_workflows_dir_property(self) -> None:
        """Test workflows_dir property."""
        settings = CalmSettings()
        assert settings.workflows_dir == settings.home / "workflows"

    def test_roles_dir_property(self) -> None:
        """Test roles_dir property."""
        settings = CalmSettings()
        assert settings.roles_dir == settings.home / "roles"

    def test_sessions_dir_property(self) -> None:
        """Test sessions_dir property."""
        settings = CalmSettings()
        assert settings.sessions_dir == settings.home / "sessions"


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_is_valid_yaml(self) -> None:
        """Test that DEFAULT_CONFIG is valid YAML."""
        import yaml
        config = yaml.safe_load(DEFAULT_CONFIG)
        assert isinstance(config, dict)
        assert "server" in config
        assert config["server"]["port"] == 6335
