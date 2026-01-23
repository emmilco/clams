"""Platform capability detection for CLAMS.

Provides centralized detection of platform-specific features including:
- OS detection (macOS, Linux)
- Hardware detection (Apple Silicon, NVIDIA GPU)
- PyTorch backend availability (MPS, CUDA)
- External tool availability (ripgrep, Docker)
- Service availability (Qdrant)

Usage:
    from clams.utils.platform import get_platform_info, check_requirements

    info = get_platform_info()
    if info.mps_available:
        # Handle MPS-specific logic

    ok, missing = check_requirements(["ripgrep", "docker"])
    if not ok:
        print(f"Missing: {missing}")
"""

from __future__ import annotations

import functools
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class PlatformInfo:
    """Immutable platform capability snapshot.

    All detection happens at construction time. Use get_platform_info()
    to get a cached instance.

    Attributes:
        os_name: Lowercase OS name ("darwin", "linux")
        os_version: Full platform version string
        machine: CPU architecture ("arm64", "x86_64")
        is_macos: True if running on macOS
        is_linux: True if running on Linux
        is_apple_silicon: True if Apple Silicon (arm64 on macOS)
        has_nvidia_gpu: True if NVIDIA GPU detected
        mps_available: True if PyTorch MPS backend available
        cuda_available: True if PyTorch CUDA backend available
        has_ripgrep: True if ripgrep (rg) is installed
        ripgrep_path: Path to ripgrep binary, or None
        has_docker: True if Docker CLI is installed
        docker_path: Path to docker binary, or None
        docker_running: True if Docker daemon is running
        qdrant_available: True if Qdrant service responds
        qdrant_url: URL used for Qdrant check
    """

    os_name: str
    os_version: str
    machine: str
    is_macos: bool
    is_linux: bool
    is_apple_silicon: bool
    has_nvidia_gpu: bool
    mps_available: bool
    cuda_available: bool
    has_ripgrep: bool
    ripgrep_path: str | None
    has_docker: bool
    docker_path: str | None
    docker_running: bool
    qdrant_available: bool
    qdrant_url: str


def _check_docker_running() -> bool:
    """Check if Docker daemon is running.

    Runs `docker info` with timeout to verify daemon accessibility.

    Returns:
        True if Docker daemon responds successfully
    """
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _check_qdrant_available(url: str) -> bool:
    """Check if Qdrant service is responding.

    Makes HTTP request to Qdrant health endpoint.

    Args:
        url: Base URL for Qdrant service

    Returns:
        True if Qdrant responds with HTTP 200
    """
    try:
        import urllib.request

        # Qdrant health endpoint
        health_url = f"{url.rstrip('/')}/healthz"
        req = urllib.request.Request(health_url, method="GET")
        with urllib.request.urlopen(req, timeout=2) as response:
            return bool(response.status == 200)
    except Exception:
        return False


def _check_pytorch_backends() -> tuple[bool, bool]:
    """Check PyTorch MPS and CUDA availability.

    Imports torch lazily to avoid import-time overhead for tests
    that don't need PyTorch.

    Returns:
        Tuple of (mps_available, cuda_available)
    """
    try:
        import torch

        mps = torch.backends.mps.is_available()
        cuda = torch.cuda.is_available()
        return mps, cuda
    except ImportError:
        return False, False


def _detect_nvidia_gpu() -> bool:
    """Detect NVIDIA GPU via nvidia-smi.

    Returns:
        True if nvidia-smi reports at least one GPU
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0 and b"GPU" in result.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


@functools.lru_cache(maxsize=1)
def get_platform_info(qdrant_url: str | None = None) -> PlatformInfo:
    """Get cached platform capability info.

    Detection is expensive (subprocess calls, network requests, torch import),
    so results are cached. Call once per process.

    Args:
        qdrant_url: URL for Qdrant availability check. Defaults to
                    CLAMS_QDRANT_URL env var or "http://localhost:6333"

    Returns:
        PlatformInfo with all detected capabilities
    """
    # Determine Qdrant URL from environment or default
    if qdrant_url is None:
        qdrant_url = os.environ.get("CLAMS_QDRANT_URL", "http://localhost:6333")

    os_name = platform.system().lower()
    os_version = platform.platform()
    machine = platform.machine()

    is_macos = os_name == "darwin"
    is_linux = os_name == "linux"
    is_apple_silicon = is_macos and machine == "arm64"

    # External tools
    ripgrep_path = shutil.which("rg")
    docker_path = shutil.which("docker")

    # Service checks (potentially slow)
    docker_running = _check_docker_running() if docker_path else False
    qdrant_available = _check_qdrant_available(qdrant_url)

    # PyTorch backends (imports torch - can be slow first time)
    mps_available, cuda_available = _check_pytorch_backends()

    # NVIDIA GPU - only check if CUDA not available (nvidia-smi is slow)
    has_nvidia_gpu = cuda_available or _detect_nvidia_gpu()

    return PlatformInfo(
        os_name=os_name,
        os_version=os_version,
        machine=machine,
        is_macos=is_macos,
        is_linux=is_linux,
        is_apple_silicon=is_apple_silicon,
        has_nvidia_gpu=has_nvidia_gpu,
        mps_available=mps_available,
        cuda_available=cuda_available,
        has_ripgrep=ripgrep_path is not None,
        ripgrep_path=ripgrep_path,
        has_docker=docker_path is not None,
        docker_path=docker_path,
        docker_running=docker_running,
        qdrant_available=qdrant_available,
        qdrant_url=qdrant_url,
    )


# Requirement name to PlatformInfo attribute mapping
_REQUIREMENT_ATTRS: dict[str, str] = {
    "mps": "mps_available",
    "cuda": "cuda_available",
    "ripgrep": "has_ripgrep",
    "docker": "docker_running",
    "qdrant": "qdrant_available",
    "macos": "is_macos",
    "linux": "is_linux",
    "apple_silicon": "is_apple_silicon",
    "nvidia_gpu": "has_nvidia_gpu",
}


def check_requirements(
    requirements: list[str],
    qdrant_url: str | None = None,
) -> tuple[bool, list[str]]:
    """Check if platform meets requirements.

    Args:
        requirements: List of requirement names. Valid names:
            - "mps": MPS (Apple Metal) available
            - "cuda": CUDA available
            - "ripgrep": ripgrep installed
            - "docker": Docker daemon running
            - "qdrant": Qdrant service available
            - "macos": Running on macOS
            - "linux": Running on Linux
            - "apple_silicon": Apple Silicon Mac
            - "nvidia_gpu": NVIDIA GPU present
        qdrant_url: Optional Qdrant URL override

    Returns:
        Tuple of (all_requirements_met, list_of_missing_requirements)

    Raises:
        ValueError: If unknown requirement name provided
    """
    info = get_platform_info(qdrant_url)

    missing: list[str] = []
    for req in requirements:
        attr = _REQUIREMENT_ATTRS.get(req)
        if attr is None:
            raise ValueError(
                f"Unknown requirement '{req}'. "
                f"Valid: {list(_REQUIREMENT_ATTRS.keys())}"
            )
        if not getattr(info, attr):
            missing.append(req)

    return len(missing) == 0, missing


def format_report(info: PlatformInfo) -> str:
    """Format platform info as human-readable report.

    Args:
        info: PlatformInfo to format

    Returns:
        Multi-line string with platform summary
    """
    lines: list[str] = []

    # OS info
    if info.is_macos:
        arch = "Apple Silicon (arm64)" if info.is_apple_silicon else "Intel (x86_64)"
        lines.append(f"Platform: macOS ({info.os_version})")
        lines.append(f"Architecture: {arch}")
    elif info.is_linux:
        lines.append(f"Platform: Linux ({info.os_version})")
        lines.append(f"Architecture: {info.machine}")
    else:
        lines.append(f"Platform: {info.os_name} ({info.os_version})")

    lines.append("")
    lines.append("PyTorch Backends:")

    if info.mps_available:
        lines.append("  - MPS: available (disabled for embeddings due to memory leak)")
    else:
        lines.append("  - MPS: not available")

    if info.cuda_available:
        lines.append("  - CUDA: available")
    elif info.has_nvidia_gpu:
        lines.append("  - CUDA: GPU detected but CUDA not configured")
    else:
        lines.append("  - CUDA: not available")

    lines.append("")
    lines.append("External Tools:")

    if info.has_ripgrep:
        lines.append(f"  - ripgrep: installed ({info.ripgrep_path})")
    else:
        lines.append("  - ripgrep: not installed (install: brew install ripgrep)")

    if info.has_docker:
        if info.docker_running:
            lines.append(f"  - docker: installed, daemon running ({info.docker_path})")
        else:
            lines.append("  - docker: installed but daemon not running")
    else:
        lines.append("  - docker: not installed")

    lines.append("")
    lines.append("Services:")

    if info.qdrant_available:
        lines.append(f"  - Qdrant: available at {info.qdrant_url}")
    else:
        lines.append(f"  - Qdrant: not available at {info.qdrant_url}")

    return "\n".join(lines)
