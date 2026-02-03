"""Dependency checking for CALM installation.

Verifies that required system dependencies are available.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass


@dataclass
class DependencyCheck:
    """Result of a single dependency check."""

    name: str
    required_version: str | None
    found_version: str | None
    available: bool
    install_hint: str


def check_python_version() -> DependencyCheck:
    """Check Python version >= 3.12."""
    version_info = sys.version_info
    version_str = f"{version_info.major}.{version_info.minor}.{version_info.micro}"
    available = version_info >= (3, 12)

    return DependencyCheck(
        name="Python",
        required_version="3.12+",
        found_version=version_str,
        available=available,
        install_hint="Install Python 3.12+ via pyenv or python.org",
    )


def check_docker() -> DependencyCheck:
    """Check Docker is installed and daemon is running."""
    # Check if docker command exists
    docker_path = shutil.which("docker")
    if not docker_path:
        return DependencyCheck(
            name="Docker",
            required_version=None,
            found_version=None,
            available=False,
            install_hint="Install Docker Desktop from docker.com",
        )

    # Check docker version
    try:
        result = subprocess.run(
            ["docker", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return DependencyCheck(
                name="Docker",
                required_version=None,
                found_version=None,
                available=False,
                install_hint="Install Docker Desktop from docker.com",
            )

        # Parse version from output like "Docker version 24.0.7, build afdd53b"
        version_output = result.stdout.strip()
        version = None
        if "version" in version_output.lower():
            parts = version_output.split()
            for i, part in enumerate(parts):
                if part.lower() == "version" and i + 1 < len(parts):
                    version = parts[i + 1].rstrip(",")
                    break

        # Check if daemon is running
        daemon_result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if daemon_result.returncode != 0:
            return DependencyCheck(
                name="Docker",
                required_version=None,
                found_version=version,
                available=False,
                install_hint=(
                    "Docker daemon is not running. "
                    "Start Docker Desktop or run: sudo systemctl start docker"
                ),
            )

        return DependencyCheck(
            name="Docker",
            required_version=None,
            found_version=version,
            available=True,
            install_hint="Install Docker Desktop from docker.com",
        )

    except subprocess.TimeoutExpired:
        return DependencyCheck(
            name="Docker",
            required_version=None,
            found_version=None,
            available=False,
            install_hint=(
                "Docker command timed out. "
                "Ensure Docker daemon is running."
            ),
        )
    except FileNotFoundError:
        return DependencyCheck(
            name="Docker",
            required_version=None,
            found_version=None,
            available=False,
            install_hint="Install Docker Desktop from docker.com",
        )


def check_uv() -> DependencyCheck:
    """Check uv package manager is installed."""
    uv_path = shutil.which("uv")
    if not uv_path:
        return DependencyCheck(
            name="uv",
            required_version=None,
            found_version=None,
            available=False,
            install_hint=(
                "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
            ),
        )

    try:
        result = subprocess.run(
            ["uv", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return DependencyCheck(
                name="uv",
                required_version=None,
                found_version=None,
                available=False,
                install_hint=(
                    "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
                ),
            )

        # Parse version from output like "uv 0.1.24"
        version_output = result.stdout.strip()
        version = None
        parts = version_output.split()
        if len(parts) >= 2:
            version = parts[1]

        return DependencyCheck(
            name="uv",
            required_version=None,
            found_version=version,
            available=True,
            install_hint=(
                "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
            ),
        )

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return DependencyCheck(
            name="uv",
            required_version=None,
            found_version=None,
            available=False,
            install_hint=(
                "Install uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
            ),
        )


def check_all_dependencies(
    skip_docker: bool = False,
) -> tuple[list[DependencyCheck], bool]:
    """Check all required dependencies.

    Args:
        skip_docker: Skip Docker check (for --skip-qdrant mode)

    Returns:
        Tuple of (list of dependency check results, all_passed)
    """
    checks = [
        check_python_version(),
        check_uv(),
    ]

    if not skip_docker:
        checks.append(check_docker())

    all_passed = all(check.available for check in checks)
    return checks, all_passed
