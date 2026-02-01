"""Tests for CALM init CLI command."""

from pathlib import Path

import pytest
from click.testing import CliRunner

from calm.cli.main import cli
from calm.config import DEFAULT_CONFIG


class TestInitCommand:
    """Tests for the init command."""

    def test_creates_directory_structure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that init creates the expected directory structure."""
        calm_home = tmp_path / ".calm"

        # Set environment variables to override settings
        monkeypatch.setenv("CALM_HOME", str(calm_home))
        monkeypatch.setenv("CALM_DB_PATH", str(calm_home / "metadata.db"))
        monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
        monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

        # Patch CALM_HOME constant used by init command
        import calm.config
        monkeypatch.setattr(calm.config, "CALM_HOME", calm_home)

        # Create new settings with overridden env vars
        from calm.config import CalmSettings
        new_settings = CalmSettings()

        # Patch settings in all modules that import it
        monkeypatch.setattr(calm.config, "settings", new_settings)
        import calm.cli.init_cmd
        monkeypatch.setattr(calm.cli.init_cmd, "settings", new_settings)
        monkeypatch.setattr(calm.cli.init_cmd, "CALM_HOME", calm_home)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0, result.output
        assert calm_home.exists()
        assert (calm_home / "workflows").exists()
        assert (calm_home / "roles").exists()
        assert (calm_home / "sessions").exists()

    def test_creates_database(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that init creates the database."""
        calm_home = tmp_path / ".calm"
        db_path = calm_home / "metadata.db"

        monkeypatch.setenv("CALM_HOME", str(calm_home))
        monkeypatch.setenv("CALM_DB_PATH", str(db_path))
        monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
        monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

        import calm.config
        monkeypatch.setattr(calm.config, "CALM_HOME", calm_home)

        from calm.config import CalmSettings
        new_settings = CalmSettings()
        monkeypatch.setattr(calm.config, "settings", new_settings)
        import calm.cli.init_cmd
        monkeypatch.setattr(calm.cli.init_cmd, "settings", new_settings)
        monkeypatch.setattr(calm.cli.init_cmd, "CALM_HOME", calm_home)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0, result.output
        assert db_path.exists()

    def test_creates_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that init creates config.yaml."""
        calm_home = tmp_path / ".calm"

        monkeypatch.setenv("CALM_HOME", str(calm_home))
        monkeypatch.setenv("CALM_DB_PATH", str(calm_home / "metadata.db"))
        monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
        monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

        import calm.config
        monkeypatch.setattr(calm.config, "CALM_HOME", calm_home)

        from calm.config import CalmSettings
        new_settings = CalmSettings()
        monkeypatch.setattr(calm.config, "settings", new_settings)
        import calm.cli.init_cmd
        monkeypatch.setattr(calm.cli.init_cmd, "settings", new_settings)
        monkeypatch.setattr(calm.cli.init_cmd, "CALM_HOME", calm_home)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0, result.output

        config_path = calm_home / "config.yaml"
        assert config_path.exists()
        assert config_path.read_text() == DEFAULT_CONFIG

    def test_idempotent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that init is idempotent."""
        calm_home = tmp_path / ".calm"

        monkeypatch.setenv("CALM_HOME", str(calm_home))
        monkeypatch.setenv("CALM_DB_PATH", str(calm_home / "metadata.db"))
        monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
        monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

        import calm.config
        monkeypatch.setattr(calm.config, "CALM_HOME", calm_home)

        from calm.config import CalmSettings
        new_settings = CalmSettings()
        monkeypatch.setattr(calm.config, "settings", new_settings)
        import calm.cli.init_cmd
        monkeypatch.setattr(calm.cli.init_cmd, "settings", new_settings)
        monkeypatch.setattr(calm.cli.init_cmd, "CALM_HOME", calm_home)

        runner = CliRunner()

        # Run init twice
        result1 = runner.invoke(cli, ["init"])
        result2 = runner.invoke(cli, ["init"])

        assert result1.exit_code == 0, result1.output
        assert result2.exit_code == 0, result2.output

    def test_does_not_overwrite_existing_config(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that init does not overwrite existing config.yaml."""
        calm_home = tmp_path / ".calm"
        calm_home.mkdir(parents=True)

        config_path = calm_home / "config.yaml"
        custom_content = "# Custom config\nserver:\n  port: 9999\n"
        config_path.write_text(custom_content)

        monkeypatch.setenv("CALM_HOME", str(calm_home))
        monkeypatch.setenv("CALM_DB_PATH", str(calm_home / "metadata.db"))
        monkeypatch.setenv("CALM_PID_FILE", str(calm_home / "server.pid"))
        monkeypatch.setenv("CALM_LOG_FILE", str(calm_home / "server.log"))

        import calm.config
        monkeypatch.setattr(calm.config, "CALM_HOME", calm_home)

        from calm.config import CalmSettings
        new_settings = CalmSettings()
        monkeypatch.setattr(calm.config, "settings", new_settings)
        import calm.cli.init_cmd
        monkeypatch.setattr(calm.cli.init_cmd, "settings", new_settings)
        monkeypatch.setattr(calm.cli.init_cmd, "CALM_HOME", calm_home)

        runner = CliRunner()
        result = runner.invoke(cli, ["init"])

        assert result.exit_code == 0, result.output
        assert config_path.read_text() == custom_content
        assert "already exists" in result.output


class TestVersionCommand:
    """Tests for version output."""

    def test_version_option(self) -> None:
        """Test --version option."""
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "calm" in result.output
        assert "0.1.0" in result.output
