"""Tests for dependency checking."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from calm.install.dependencies import (
    DependencyCheck,
    check_all_dependencies,
    check_docker,
    check_python_version,
    check_uv,
)


class TestCheckPythonVersion:
    """Tests for check_python_version."""

    def test_current_python_passes(self) -> None:
        """Current Python should pass (we require 3.12+)."""
        result = check_python_version()
        assert result.available
        assert result.found_version is not None

    def test_version_format(self) -> None:
        """Version should be formatted correctly."""
        result = check_python_version()
        assert result.found_version is not None
        assert result.found_version.count(".") >= 1

    def test_returns_dependency_check(self) -> None:
        """Should return a DependencyCheck instance."""
        result = check_python_version()
        assert isinstance(result, DependencyCheck)
        assert result.name == "Python"
        assert result.required_version == "3.12+"


class TestCheckDocker:
    """Tests for check_docker."""

    def test_docker_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle Docker not installed."""
        monkeypatch.setattr("shutil.which", lambda x: None)
        result = check_docker()
        assert not result.available
        assert "docker.com" in result.install_hint

    def test_docker_command_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle Docker command raising FileNotFoundError."""
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/docker")

        def mock_run(*args: Any, **kwargs: Any) -> None:
            raise FileNotFoundError("docker not found")

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker()
        assert not result.available

    def test_docker_daemon_not_running(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle Docker daemon not running."""
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/docker")

        call_count = 0

        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # docker --version succeeds
                return subprocess.CompletedProcess(
                    args=[], returncode=0, stdout="Docker version 24.0.7", stderr=""
                )
            else:
                # docker info fails (daemon not running)
                return subprocess.CompletedProcess(
                    args=[],
                    returncode=1,
                    stdout="",
                    stderr="Cannot connect to Docker daemon",
                )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker()
        assert not result.available
        assert "not running" in result.install_hint.lower() or result.found_version is not None

    def test_docker_timeout(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle Docker command timeout."""
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/docker")

        def mock_run(*args: Any, **kwargs: Any) -> None:
            raise subprocess.TimeoutExpired(cmd="docker", timeout=10)

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker()
        assert not result.available


class TestCheckUv:
    """Tests for check_uv."""

    def test_uv_not_installed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle uv not installed."""
        monkeypatch.setattr("shutil.which", lambda x: None)
        result = check_uv()
        assert not result.available
        assert "astral.sh" in result.install_hint

    def test_uv_version_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Handle successful uv version check."""
        monkeypatch.setattr("shutil.which", lambda x: "/usr/local/bin/uv")

        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="uv 0.1.24", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_uv()
        assert result.available
        assert result.found_version == "0.1.24"


class TestCheckAllDependencies:
    """Tests for check_all_dependencies."""

    def test_returns_list_and_status(self) -> None:
        """Should return list of checks and overall status."""
        checks, all_passed = check_all_dependencies(skip_docker=True)
        assert isinstance(checks, list)
        assert len(checks) >= 2  # At least Python and uv
        assert isinstance(all_passed, bool)

    def test_skip_docker(self) -> None:
        """Should not include Docker check when skipped."""
        checks, _ = check_all_dependencies(skip_docker=True)
        docker_checks = [c for c in checks if c.name == "Docker"]
        assert len(docker_checks) == 0

    def test_include_docker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should include Docker check when not skipped."""
        # Mock docker to return a predictable result
        monkeypatch.setattr("shutil.which", lambda x: None if x == "docker" else f"/usr/bin/{x}")

        checks, _ = check_all_dependencies(skip_docker=False)
        docker_checks = [c for c in checks if c.name == "Docker"]
        assert len(docker_checks) == 1
