"""Integration tests for CALM installation."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from calm.install import InstallOptions, InstallResult, install


class TestFullInstallation:
    """Tests for complete installation flow."""

    def test_basic_installation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test complete installation to temp directory."""
        # Mock HOME to tmp_path
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,  # Don't require Docker for unit tests
            skip_mcp=True,  # Don't modify real config
            skip_hooks=True,  # Don't modify real config
            skip_server=True,  # Don't start server
        )

        result = install(options)

        assert result.status == "success", f"Errors: {result.errors}"
        assert calm_home.exists()
        assert (calm_home / "roles").exists()
        assert (calm_home / "workflows").exists()
        assert (calm_home / "skills").exists()
        assert (calm_home / "metadata.db").exists()

    def test_creates_role_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that role files are created."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Check some role files exist
        roles_dir = calm_home / "roles"
        assert (roles_dir / "backend.md").exists()
        assert (roles_dir / "architect.md").exists()
        assert (roles_dir / "reviewer.md").exists()

    def test_creates_skill_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that skill files are created."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Check skill files exist
        skills_dir = calm_home / "skills"
        assert (skills_dir / "orchestrate.md").exists()
        assert (skills_dir / "wrapup.md").exists()
        assert (skills_dir / "reflection.md").exists()

    def test_creates_workflow_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that workflow file is created."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Check workflow file exists
        workflows_dir = calm_home / "workflows"
        assert (workflows_dir / "default.md").exists()

    def test_creates_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Test that config file is created."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Check config file exists
        assert (calm_home / "config.yaml").exists()


class TestIdempotentInstallation:
    """Tests for idempotent installation."""

    def test_run_twice_same_result(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Running install twice should produce same result."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        # First install
        result1 = install(options)
        assert result1.status == "success"

        # Get file contents after first install
        backend_md = (calm_home / "roles" / "backend.md").read_text()

        # Second install
        result2 = install(options)
        assert result2.status == "success"

        # Files should be unchanged (skipped, not overwritten)
        assert (calm_home / "roles" / "backend.md").read_text() == backend_md

    def test_force_overwrites(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--force should replace existing files."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        # First install
        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )
        install(options)

        # Modify a file
        backend_path = calm_home / "roles" / "backend.md"
        backend_path.write_text("modified content")

        # Second install with force
        options.force = True
        result = install(options)
        assert result.status == "success"

        # File should be restored to template
        assert backend_path.read_text() != "modified content"


class TestDryRun:
    """Tests for dry run mode."""

    def test_dry_run_no_changes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dry run should not create any files or directories."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
            dry_run=True,
        )

        result = install(options)
        assert result.status == "success"

        # Nothing should be created
        assert not calm_home.exists()

    def test_dry_run_reports_actions(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Dry run should report what would be done."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
            dry_run=True,
        )

        install(options)

        captured = capsys.readouterr()
        assert "dry run" in captured.out.lower()


class TestSkipFlags:
    """Tests for skip flags."""

    def test_skip_qdrant(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skip Qdrant flag should skip Qdrant setup."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Qdrant step should be skipped
        from calm.install import InstallStep
        assert InstallStep.START_QDRANT in result.steps_skipped

    def test_skip_mcp(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skip MCP flag should skip MCP registration."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # MCP step should be skipped
        from calm.install import InstallStep
        assert InstallStep.REGISTER_MCP in result.steps_skipped

        # No claude.json should be created/modified in tmp
        assert not (tmp_path / ".claude.json").exists()

    def test_skip_hooks(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skip hooks flag should skip hook registration."""
        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"

        # Hooks step should be skipped
        from calm.install import InstallStep
        assert InstallStep.REGISTER_HOOKS in result.steps_skipped

        # No settings.json should be created in tmp
        assert not (tmp_path / ".claude" / "settings.json").exists()
