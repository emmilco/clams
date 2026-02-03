"""Docker/Qdrant container management for CALM installation.

Provides utilities for managing the Qdrant Docker container.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from enum import Enum

import httpx


class ContainerState(str, Enum):
    """Qdrant container state."""

    NOT_FOUND = "not_found"
    STOPPED = "stopped"
    RUNNING = "running"
    UNHEALTHY = "unhealthy"


@dataclass
class QdrantStatus:
    """Qdrant container status."""

    state: ContainerState
    container_id: str | None = None
    error: str | None = None


def check_docker_running() -> bool:
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def get_qdrant_status() -> QdrantStatus:
    """Get current Qdrant container status."""
    if not check_docker_running():
        return QdrantStatus(
            state=ContainerState.UNHEALTHY,
            error="Docker daemon is not running",
        )

    try:
        # Check if container exists (running or stopped)
        result = subprocess.run(
            [
                "docker",
                "ps",
                "-a",
                "--filter",
                "name=^qdrant$",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        container_id = result.stdout.strip()
        if not container_id:
            return QdrantStatus(state=ContainerState.NOT_FOUND)

        # Check if container is running
        running_result = subprocess.run(
            [
                "docker",
                "ps",
                "--filter",
                "name=^qdrant$",
                "--format",
                "{{.ID}}",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if running_result.stdout.strip():
            return QdrantStatus(
                state=ContainerState.RUNNING,
                container_id=container_id,
            )
        else:
            return QdrantStatus(
                state=ContainerState.STOPPED,
                container_id=container_id,
            )

    except subprocess.TimeoutExpired:
        return QdrantStatus(
            state=ContainerState.UNHEALTHY,
            error="Docker command timed out",
        )
    except FileNotFoundError:
        return QdrantStatus(
            state=ContainerState.UNHEALTHY,
            error="Docker not found",
        )


def create_qdrant_container(dry_run: bool = False) -> tuple[bool, str]:
    """Create new Qdrant container.

    Args:
        dry_run: If True, don't actually create

    Returns:
        Tuple of (success, message_or_error)
    """
    if dry_run:
        return True, "Would create Qdrant container"

    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--name",
                "qdrant",
                "-p",
                "6333:6333",
                "-v",
                "qdrant_data:/qdrant/storage",
                "qdrant/qdrant",
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            if "port is already allocated" in stderr:
                return False, "Port 6333 is already in use"
            return False, f"Failed to create container: {stderr}"

        return True, f"Created Qdrant container: {result.stdout.strip()}"

    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except FileNotFoundError:
        return False, "Docker not found"


def start_qdrant_container(dry_run: bool = False) -> tuple[bool, str]:
    """Start existing Qdrant container.

    Args:
        dry_run: If True, don't actually start

    Returns:
        Tuple of (success, message_or_error)
    """
    if dry_run:
        return True, "Would start Qdrant container"

    try:
        result = subprocess.run(
            ["docker", "start", "qdrant"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return False, f"Failed to start container: {result.stderr.strip()}"

        return True, "Started Qdrant container"

    except subprocess.TimeoutExpired:
        return False, "Docker command timed out"
    except FileNotFoundError:
        return False, "Docker not found"


def wait_for_qdrant_healthy(
    timeout_seconds: int = 30,
    qdrant_url: str = "http://localhost:6333",
) -> bool:
    """Wait for Qdrant to become healthy.

    Args:
        timeout_seconds: Maximum time to wait
        qdrant_url: Qdrant server URL

    Returns:
        True if healthy within timeout
    """
    start_time = time.time()
    wait_interval = 0.5
    max_interval = 2.0

    while time.time() - start_time < timeout_seconds:
        try:
            response = httpx.get(
                f"{qdrant_url}/readiness",
                timeout=5.0,
            )
            if response.status_code == 200:
                return True
        except (httpx.RequestError, httpx.TimeoutException):
            pass

        time.sleep(wait_interval)
        # Exponential backoff
        wait_interval = min(wait_interval * 1.5, max_interval)

    return False


def ensure_qdrant_running(
    dry_run: bool = False,
    timeout_seconds: int = 30,
) -> tuple[bool, str]:
    """Ensure Qdrant is running and healthy.

    Creates container if needed, starts if stopped, waits for healthy.

    Args:
        dry_run: If True, don't actually make changes
        timeout_seconds: Maximum time to wait for healthy state

    Returns:
        Tuple of (success, message_or_error)
    """
    status = get_qdrant_status()

    if status.error:
        return False, status.error

    if status.state == ContainerState.NOT_FOUND:
        # Create and start container
        success, message = create_qdrant_container(dry_run)
        if not success:
            return False, message
        if dry_run:
            return True, message

        # Wait for healthy
        if wait_for_qdrant_healthy(timeout_seconds):
            return True, f"{message}. Qdrant is healthy."
        else:
            return (
                False,
                f"{message}. Qdrant failed health check after {timeout_seconds}s",
            )

    elif status.state == ContainerState.STOPPED:
        # Start existing container
        success, message = start_qdrant_container(dry_run)
        if not success:
            return False, message
        if dry_run:
            return True, message

        # Wait for healthy
        if wait_for_qdrant_healthy(timeout_seconds):
            return True, f"{message}. Qdrant is healthy."
        else:
            return (
                False,
                f"{message}. Qdrant failed health check after {timeout_seconds}s",
            )

    elif status.state == ContainerState.RUNNING:
        if dry_run:
            return True, "Qdrant container already running"

        # Verify it's healthy
        if wait_for_qdrant_healthy(timeout_seconds=5):
            return True, "Qdrant container already running and healthy"
        else:
            return False, "Qdrant container running but not responding to health checks"

    else:
        return False, f"Unexpected container state: {status.state}"
