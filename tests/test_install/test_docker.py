"""Tests for Docker/Qdrant management."""

from __future__ import annotations

import subprocess
from typing import Any

import pytest

from calm.install.docker import (
    ContainerState,
    QdrantStatus,
    check_docker_running,
    create_qdrant_container,
    get_qdrant_status,
    start_qdrant_container,
)


class TestCheckDockerRunning:
    """Tests for check_docker_running."""

    def test_docker_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when docker command not found."""
        def mock_run(*args: Any, **kwargs: Any) -> None:
            raise FileNotFoundError("docker not found")

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker_running()
        assert result is False

    def test_docker_info_fails(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return False when docker info fails."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker_running()
        assert result is False

    def test_docker_info_succeeds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should return True when docker info succeeds."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        result = check_docker_running()
        assert result is True


class TestGetQdrantStatus:
    """Tests for get_qdrant_status."""

    def test_container_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should detect when container doesn't exist."""
        call_count = 0

        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # docker info succeeds
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            else:
                # docker ps -a returns empty (no container)
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        status = get_qdrant_status()
        assert status.state == ContainerState.NOT_FOUND

    def test_container_stopped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should detect when container exists but is stopped."""
        call_count = 0

        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # docker info succeeds
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            elif call_count == 2:
                # docker ps -a finds container
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="abc123", stderr="")
            else:
                # docker ps (running only) returns empty
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        status = get_qdrant_status()
        assert status.state == ContainerState.STOPPED
        assert status.container_id == "abc123"

    def test_container_running(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should detect when container is running."""
        call_count = 0

        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # docker info succeeds
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
            elif call_count == 2:
                # docker ps -a finds container
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="abc123", stderr="")
            else:
                # docker ps (running only) finds container
                return subprocess.CompletedProcess(args=[], returncode=0, stdout="abc123", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        status = get_qdrant_status()
        assert status.state == ContainerState.RUNNING
        assert status.container_id == "abc123"


class TestCreateQdrantContainer:
    """Tests for create_qdrant_container."""

    def test_dry_run(self) -> None:
        """Dry run should not create container."""
        success, message = create_qdrant_container(dry_run=True)
        assert success
        assert "Would create" in message

    def test_port_in_use(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should handle port already in use."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="Error: port is already allocated",
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        success, message = create_qdrant_container(dry_run=False)
        assert not success
        assert "6333" in message or "already in use" in message

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should handle successful container creation."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[], returncode=0, stdout="container_id_123", stderr=""
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        success, message = create_qdrant_container(dry_run=False)
        assert success
        assert "container_id_123" in message or "Created" in message


class TestStartQdrantContainer:
    """Tests for start_qdrant_container."""

    def test_dry_run(self) -> None:
        """Dry run should not start container."""
        success, message = start_qdrant_container(dry_run=True)
        assert success
        assert "Would start" in message

    def test_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should handle successful container start."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", mock_run)
        success, message = start_qdrant_container(dry_run=False)
        assert success
        assert "Started" in message

    def test_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Should handle failed container start."""
        def mock_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=[], returncode=1, stdout="", stderr="Error starting"
            )

        monkeypatch.setattr(subprocess, "run", mock_run)
        success, message = start_qdrant_container(dry_run=False)
        assert not success
        assert "Failed" in message
