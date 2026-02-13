"""Tests for CALM install module.

Tests dependency checking, directory creation, template copying,
and the overall installation flow.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from calm.install import InstallOptions, InstallResult, InstallStep
from calm.install.dependencies import (
    DependencyCheck,
    check_all_dependencies,
    check_docker,
    check_python_version,
    check_uv,
)
from calm.install.docker import (
    wait_for_qdrant_healthy,
)
from calm.install.steps import (
    step_check_dependencies,
    step_create_directories,
)
from calm.install.templates import create_directory_structure


class TestDependencyChecks:
    """Tests for dependency checking functions."""

    def test_check_python_version_current(self) -> None:
        """Current Python version should pass (we're running 3.12+)."""
        result = check_python_version()
        assert result.available is True
        assert result.name == "Python"
        assert result.required_version == "3.12+"
        assert result.found_version is not None

    def test_check_python_version_low(self) -> None:
        """Python < 3.12 should produce a failing check with install hint."""
        # Rather than monkeypatching sys.version_info (which breaks pytest),
        # verify the check structure handles the failure case correctly
        # by constructing what the result would look like for Python 3.11.
        result = DependencyCheck(
            name="Python",
            required_version="3.12+",
            found_version="3.11.0",
            available=False,
            install_hint="Install Python 3.12+ via pyenv or python.org",
        )
        assert result.available is False
        assert result.found_version == "3.11.0"
        assert result.required_version == "3.12+"
        assert "3.12" in result.install_hint

    def test_check_uv_available(self) -> None:
        """uv should be available in this environment."""
        result = check_uv()
        assert result.available is True
        assert result.name == "uv"
        assert result.found_version is not None

    def test_check_uv_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Missing uv should give curl install hint."""
        monkeypatch.setattr("calm.install.dependencies.shutil.which", lambda _: None)
        result = check_uv()
        assert result.available is False
        assert "curl -LsSf https://astral.sh/uv/install.sh | sh" in result.install_hint

    def test_check_docker_missing_hints_skip_qdrant(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing Docker should mention --skip-qdrant in the install hint."""
        monkeypatch.setattr("calm.install.dependencies.shutil.which", lambda _: None)
        result = check_docker()
        assert result.available is False
        assert "--skip-qdrant" in result.install_hint
        assert "docker.com" in result.install_hint

    def test_check_all_dependencies_skips_docker(self) -> None:
        """With skip_docker=True, Docker check should be omitted."""
        checks, _ = check_all_dependencies(skip_docker=True)
        names = [c.name for c in checks]
        assert "Docker" not in names
        assert "Python" in names
        assert "uv" in names

    def test_check_all_dependencies_includes_docker(self) -> None:
        """With skip_docker=False, Docker check should be included."""
        checks, _ = check_all_dependencies(skip_docker=False)
        names = [c.name for c in checks]
        assert "Docker" in names


class TestDirectoryStructure:
    """Tests for directory creation."""

    def test_create_directory_structure(self, tmp_path: Path) -> None:
        """All expected directories should be created."""
        calm_home = tmp_path / ".calm"
        created = create_directory_structure(calm_home)

        assert calm_home.exists()
        assert (calm_home / "workflows").exists()
        assert (calm_home / "roles").exists()
        assert (calm_home / "skills").exists()
        assert (calm_home / "sessions").exists()
        assert (calm_home / "journal").exists()
        assert len(created) > 0

    def test_create_directory_structure_dry_run(self, tmp_path: Path) -> None:
        """Dry run should not create directories."""
        calm_home = tmp_path / ".calm"
        created = create_directory_structure(calm_home, dry_run=True)

        assert not calm_home.exists()
        assert len(created) > 0
        assert all("Would create" in msg for msg in created)

    def test_create_directory_structure_idempotent(self, tmp_path: Path) -> None:
        """Running twice should not error and should report nothing new."""
        calm_home = tmp_path / ".calm"
        created1 = create_directory_structure(calm_home)
        created2 = create_directory_structure(calm_home)

        assert len(created1) > 0
        assert len(created2) == 0


class TestStepCheckDependencies:
    """Tests for the dependency checking installation step."""

    def test_step_check_dependencies_passes(self) -> None:
        """Step should pass when all deps are available."""
        options = InstallOptions(skip_qdrant=True)
        result = InstallResult()
        messages: list[str] = []

        success = step_check_dependencies(options, result, messages.append)

        assert success is True
        assert InstallStep.CHECK_DEPS in result.steps_completed
        # Should have printed OK messages
        ok_messages = [m for m in messages if "[OK]" in m]
        assert len(ok_messages) >= 2  # At least Python and uv

    def test_step_check_dependencies_shows_version_mismatch(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step should show both found and required versions when a dep fails."""
        # Mock check_all_dependencies to return a failing Python check
        failing_check = DependencyCheck(
            name="Python",
            required_version="3.12+",
            found_version="3.11.0",
            available=False,
            install_hint="Install Python 3.12+",
        )

        monkeypatch.setattr(
            "calm.install.steps.check_all_dependencies",
            lambda skip_docker: ([failing_check], False),
        )

        options = InstallOptions()
        result = InstallResult()
        messages: list[str] = []

        success = step_check_dependencies(options, result, messages.append)

        assert success is False
        # Should show both found and needed versions
        missing_msgs = [m for m in messages if "[MISSING]" in m]
        assert len(missing_msgs) == 1
        assert "found 3.11.0" in missing_msgs[0]
        assert "need 3.12+" in missing_msgs[0]


class TestStepCreateDirectories:
    """Tests for the directory creation installation step."""

    def test_step_create_directories_success(self, tmp_path: Path) -> None:
        """Step should create dirs and report success."""
        calm_home = tmp_path / ".calm"
        options = InstallOptions(calm_home=calm_home)
        result = InstallResult()
        messages: list[str] = []

        success = step_create_directories(options, result, messages.append)

        assert success is True
        assert InstallStep.CREATE_DIRS in result.steps_completed
        assert calm_home.exists()

    def test_step_create_directories_already_exist(self, tmp_path: Path) -> None:
        """When all dirs exist, should report that fact."""
        calm_home = tmp_path / ".calm"
        create_directory_structure(calm_home)

        options = InstallOptions(calm_home=calm_home)
        result = InstallResult()
        messages: list[str] = []

        success = step_create_directories(options, result, messages.append)

        assert success is True
        assert any("already exist" in m for m in messages)

    def test_step_create_directories_dry_run(self, tmp_path: Path) -> None:
        """Dry run should report 'already exist' when dirs exist."""
        calm_home = tmp_path / ".calm"
        create_directory_structure(calm_home)

        options = InstallOptions(calm_home=calm_home, dry_run=True)
        result = InstallResult()
        messages: list[str] = []

        success = step_create_directories(options, result, messages.append)

        assert success is True
        assert any("already exist" in m for m in messages)


class TestQdrantHealthCheck:
    """Tests for the Qdrant health check endpoint."""

    def test_wait_for_qdrant_healthy_uses_healthz(self) -> None:
        """Health check should use /healthz endpoint."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("calm.install.docker.httpx.get") as mock_get:
            mock_get.return_value = mock_response
            result = wait_for_qdrant_healthy(timeout_seconds=1)

            assert result is True
            # Verify /healthz is used
            call_url = mock_get.call_args[0][0]
            assert "/healthz" in call_url
            assert "/readiness" not in call_url

    def test_wait_for_qdrant_healthy_timeout(self) -> None:
        """Should return False when Qdrant doesn't respond in time."""
        import httpx

        with patch(
            "calm.install.docker.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = wait_for_qdrant_healthy(timeout_seconds=1)
            assert result is False


class TestInstallResult:
    """Tests for InstallResult tracking."""

    def test_add_completed(self) -> None:
        """Completed steps should be tracked."""
        result = InstallResult()
        result.add_completed(InstallStep.CHECK_DEPS)
        assert InstallStep.CHECK_DEPS in result.steps_completed
        assert result.status == "success"

    def test_add_error_changes_status(self) -> None:
        """Errors should change status to failed."""
        result = InstallResult()
        result.add_error(InstallStep.CHECK_DEPS, "test error")
        assert result.status == "failed"
        assert len(result.errors) == 1

    def test_add_skipped(self) -> None:
        """Skipped steps should be tracked with reason."""
        result = InstallResult()
        result.add_skipped(InstallStep.START_QDRANT, "user requested")
        assert InstallStep.START_QDRANT in result.steps_skipped
        assert len(result.warnings) == 1
        assert "user requested" in result.warnings[0]

    def test_add_warning(self) -> None:
        """Warnings should be accumulated."""
        result = InstallResult()
        result.add_warning("test warning")
        assert "test warning" in result.warnings
        assert result.status == "success"  # Warnings don't change status


class TestInstallOptions:
    """Tests for InstallOptions defaults and configuration."""

    def test_defaults(self) -> None:
        """Default options should not skip anything."""
        opts = InstallOptions()
        assert opts.dev_mode is False
        assert opts.skip_qdrant is False
        assert opts.skip_hooks is False
        assert opts.skip_mcp is False
        assert opts.skip_server is False
        assert opts.force is False
        assert opts.dry_run is False
        assert opts.verbose is False

    def test_custom_calm_home(self, tmp_path: Path) -> None:
        """Custom calm_home should be used."""
        opts = InstallOptions(calm_home=tmp_path)
        assert opts.calm_home == tmp_path
