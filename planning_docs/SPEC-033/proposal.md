# SPEC-033: Platform-Specific Pre-Checks - Technical Proposal

## Problem Statement

CLAMS runs on multiple platforms (macOS, Linux) with varying hardware capabilities and external dependencies. Platform-specific issues have caused several bugs:

1. **BUG-042**: Daemon crashes on macOS due to MPS fork safety
2. **BUG-014**: Memory leaks on Apple Silicon when using MPS for embeddings
3. **Ripgrep dependency**: Tests skip silently when `rg` is not installed
4. **Service availability**: Integration tests require Docker/Qdrant but just exclude tests

Currently, platform detection is scattered across test files with ad-hoc `skipif` decorators. Gate checks fail all skipped tests, creating friction when platform skips are legitimate.

## Proposed Solution

Create a centralized platform detection module with pytest integration that:
1. Detects platform capabilities once per test session
2. Provides consistent markers for platform-dependent tests
3. Integrates with gate checks to distinguish platform skips from code skips

## Alternative Approaches Considered

### Alternative 1: Pytest Plugin (Rejected)
**Approach**: Create a separate pytest plugin package (e.g., `pytest-clams-platform`).

**Rejection rationale**:
- Adds deployment complexity for a single-project need
- Version synchronization issues between plugin and main codebase
- Overkill for internal tooling

### Alternative 2: Environment Variables Only (Rejected)
**Approach**: Check environment variables (e.g., `CLAMS_HAS_MPS=true`) instead of runtime detection.

**Rejection rationale**:
- Requires manual setup on each machine
- Easy to misconfigure (stale values)
- Runtime detection is more reliable

### Alternative 3: Test Fixtures Without Markers (Rejected)
**Approach**: Use fixtures that raise `pytest.skip()` inside tests instead of markers.

**Rejection rationale**:
- Skip decision happens after test collection, not before
- Gate check cannot distinguish skip reasons from test output
- Markers provide better documentation and IDE support

## Detailed Design

### 1. Platform Detection Module

**File**: `src/clams/utils/platform.py`

```python
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
            return response.status == 200
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
            lines.append(f"  - docker: installed but daemon not running")
    else:
        lines.append("  - docker: not installed")

    lines.append("")
    lines.append("Services:")

    if info.qdrant_available:
        lines.append(f"  - Qdrant: available at {info.qdrant_url}")
    else:
        lines.append(f"  - Qdrant: not available at {info.qdrant_url}")

    return "\n".join(lines)
```

### 2. Pytest Integration

**File**: `tests/conftest.py` (additions)

```python
# Add to existing conftest.py

from clams.utils.platform import get_platform_info, PlatformInfo


def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers including platform markers."""
    # Existing markers...
    config.addinivalue_line(
        "markers",
        "no_resource_tracking: skip resource leak checking for this test",
    )

    # Platform markers
    config.addinivalue_line(
        "markers",
        "requires_mps: test requires MPS (Apple Silicon GPU)",
    )
    config.addinivalue_line(
        "markers",
        "requires_cuda: test requires CUDA (NVIDIA GPU)",
    )
    config.addinivalue_line(
        "markers",
        "requires_ripgrep: test requires ripgrep (rg) installed",
    )
    config.addinivalue_line(
        "markers",
        "requires_docker: test requires Docker daemon running",
    )
    config.addinivalue_line(
        "markers",
        "requires_qdrant: test requires Qdrant service available",
    )
    config.addinivalue_line(
        "markers",
        "macos_only: test only runs on macOS",
    )
    config.addinivalue_line(
        "markers",
        "linux_only: test only runs on Linux",
    )


@pytest.fixture(scope="session")
def platform_info() -> PlatformInfo:
    """Session-scoped platform capability info.

    Use this fixture to access platform detection results within tests.
    Detection happens once per test session.
    """
    return get_platform_info()


# Platform skip reasons - consistent wording for gate check pattern matching
_PLATFORM_SKIP_REASONS = {
    "requires_mps": "Platform: requires MPS (Apple Silicon GPU)",
    "requires_cuda": "Platform: requires CUDA (NVIDIA GPU)",
    "requires_ripgrep": "Platform: requires ripgrep. Install: brew install ripgrep",
    "requires_docker": "Platform: requires Docker daemon. Start Docker first.",
    "requires_qdrant": "Platform: requires Qdrant. Run: docker compose up -d",
    "macos_only": "Platform: test only runs on macOS",
    "linux_only": "Platform: test only runs on Linux",
}


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests based on platform requirements.

    This hook runs after test collection and adds skip markers to tests
    whose platform requirements are not met.
    """
    info = get_platform_info()

    # Map marker name to (condition, skip_reason)
    marker_checks: dict[str, tuple[bool, str]] = {
        "requires_mps": (
            info.mps_available,
            _PLATFORM_SKIP_REASONS["requires_mps"],
        ),
        "requires_cuda": (
            info.cuda_available,
            _PLATFORM_SKIP_REASONS["requires_cuda"],
        ),
        "requires_ripgrep": (
            info.has_ripgrep,
            _PLATFORM_SKIP_REASONS["requires_ripgrep"],
        ),
        "requires_docker": (
            info.docker_running,
            _PLATFORM_SKIP_REASONS["requires_docker"],
        ),
        "requires_qdrant": (
            info.qdrant_available,
            _PLATFORM_SKIP_REASONS["requires_qdrant"],
        ),
        "macos_only": (
            info.is_macos,
            _PLATFORM_SKIP_REASONS["macos_only"],
        ),
        "linux_only": (
            info.is_linux,
            _PLATFORM_SKIP_REASONS["linux_only"],
        ),
    }

    for item in items:
        for marker_name, (condition, reason) in marker_checks.items():
            if item.get_closest_marker(marker_name) and not condition:
                item.add_marker(pytest.mark.skip(reason=reason))
```

### 3. Gate Check Integration

**File**: `.claude/gates/check_platform.sh` (new)

```bash
#!/usr/bin/env bash
#
# check_platform.sh: Pre-flight platform capability check
#
# Runs before test suite to detect and report platform capabilities.
# This is informational - it does not fail the gate.
#
# Usage: check_platform.sh [worktree_path]

set -euo pipefail

WORKTREE="${1:-.}"
cd "$WORKTREE"

echo "=== Platform Pre-Flight Check ==="
echo ""

# Run platform detection via Python module
if [[ -f ".venv/bin/python" ]]; then
    PYTHON=".venv/bin/python"
else
    PYTHON="python3"
fi

export PYTHONPATH="${WORKTREE}/src:${PYTHONPATH:-}"

$PYTHON -c "
from clams.utils.platform import get_platform_info, format_report

info = get_platform_info()
print(format_report(info))

# Platform-specific warnings
warnings = []

# MPS fork safety warning (BUG-042)
if info.is_macos and info.mps_available:
    warnings.append(
        'MPS is available. Daemon mode uses subprocess to avoid fork() issues. '
        'PyTorch imports must happen AFTER daemonization.'
    )

# Memory warning (BUG-014)
if info.mps_available:
    warnings.append(
        'MPS available but disabled for embeddings (memory leak workaround). '
        'Embedding operations will use CPU.'
    )

# Missing optional dependencies
if not info.has_ripgrep:
    warnings.append('ripgrep not installed - git blame analysis will be limited')

if not info.docker_running:
    warnings.append('Docker not running - integration tests will be skipped')

if not info.qdrant_available:
    warnings.append('Qdrant not available - vector storage tests will be skipped')

if warnings:
    print()
    print('=== Platform Warnings ===')
    for w in warnings:
        print(f'  - {w}')

print()
print('Platform check complete.')
"

exit 0
```

**File**: `.claude/gates/check_tests_python.sh` (modifications)

The key change is to distinguish platform skips from code-related skips. Update the skip handling section (around line 316-322):

```bash
# Current logic (fails on ANY skips):
# if [[ "$skipped" -gt 0 ]]; then
#     echo ""
#     echo "FAIL: $skipped tests were skipped"
#     echo "Skipped tests are not allowed - they hide missing dependencies or broken code."
#     return 1
# fi

# New logic: Allow platform skips, fail on other skips
if [[ "$skipped" -gt 0 ]]; then
    # Count platform skips by checking skip reasons in test output
    # Platform skips have "Platform:" prefix in skip reason
    local platform_skips=0
    if [[ -f "test_output.log" ]]; then
        platform_skips=$(grep -c "SKIPPED.*Platform:" test_output.log 2>/dev/null || echo "0")
    fi

    local other_skips=$((skipped - platform_skips))

    if [[ "$other_skips" -gt 0 ]]; then
        echo ""
        echo "FAIL: $other_skips non-platform tests were skipped"
        echo "Skipped tests hide missing dependencies or broken code."
        if [[ "$platform_skips" -gt 0 ]]; then
            echo "($platform_skips platform-related skips are acceptable)"
        fi
        return 1
    fi

    if [[ "$platform_skips" -gt 0 ]]; then
        echo ""
        echo "NOTE: $platform_skips tests skipped due to platform requirements (acceptable)"
    fi
fi
```

### 4. Test Migration

Update existing tests to use the new markers:

**File**: `tests/embedding/test_bug_014_mps_workaround.py`

```python
# Before:
@pytest.mark.skipif(
    not torch.backends.mps.is_available(),
    reason="Only relevant on Apple Silicon with MPS",
)
def test_bug_014_embedding_model_uses_cpu_on_mps():

# After:
@pytest.mark.requires_mps
def test_bug_014_embedding_model_uses_cpu_on_mps():
```

**File**: `tests/server/test_bug_042_regression.py`

```python
# Before:
@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="MPS fork safety only affects macOS"
)
def test_bug_042_daemon_start_does_not_crash():

# After:
@pytest.mark.macos_only
def test_bug_042_daemon_start_does_not_crash():
```

**File**: `tests/git/test_analyzer.py`

```python
# Before:
HAS_RIPGREP = shutil.which("rg") is not None
requires_ripgrep = pytest.mark.skipif(
    not HAS_RIPGREP, reason="ripgrep (rg) not installed"
)

@requires_ripgrep
async def test_blame_search(self, test_repo, analyzer):

# After:
@pytest.mark.requires_ripgrep
async def test_blame_search(self, test_repo, analyzer):
```

### 5. pyproject.toml Updates

Add the new markers to pyproject.toml:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
timeout = 60
addopts = "-m 'not slow'"
markers = [
    "slow: marks tests as slow (>15s, excluded by default)",
    "integration: marks tests as integration tests requiring external services",
    "cold_start: tests that verify behavior with no pre-existing data",
    # Platform requirement markers
    "requires_mps: test requires MPS (Apple Silicon GPU)",
    "requires_cuda: test requires CUDA (NVIDIA GPU)",
    "requires_ripgrep: test requires ripgrep (rg) installed",
    "requires_docker: test requires Docker daemon running",
    "requires_qdrant: test requires Qdrant service available",
    "macos_only: test only runs on macOS",
    "linux_only: test only runs on Linux",
]
```

## File-by-File Implementation Plan

### Phase 1: Platform Detection Module

| File | Action | Description |
|------|--------|-------------|
| `src/clams/utils/platform.py` | CREATE | Platform detection module with `PlatformInfo`, `get_platform_info()`, `check_requirements()`, `format_report()` |
| `src/clams/utils/__init__.py` | MODIFY | Export platform module symbols |

### Phase 2: Pytest Integration

| File | Action | Description |
|------|--------|-------------|
| `tests/conftest.py` | MODIFY | Add platform markers registration, `pytest_collection_modifyitems` hook, `platform_info` fixture |
| `pyproject.toml` | MODIFY | Add marker documentation |

### Phase 3: Gate Check Updates

| File | Action | Description |
|------|--------|-------------|
| `.claude/gates/check_platform.sh` | CREATE | Pre-flight platform check script |
| `.claude/gates/check_tests_python.sh` | MODIFY | Distinguish platform skips from code skips |
| `.claude/gates/check_tests.sh` | MODIFY | Same modification as check_tests_python.sh |

### Phase 4: Test Migration

| File | Action | Description |
|------|--------|-------------|
| `tests/embedding/test_bug_014_mps_workaround.py` | MODIFY | Replace inline skipif with `@pytest.mark.requires_mps` |
| `tests/server/test_bug_042_regression.py` | MODIFY | Replace inline skipif with `@pytest.mark.macos_only` |
| `tests/git/test_analyzer.py` | MODIFY | Replace `requires_ripgrep` skipif marker with `@pytest.mark.requires_ripgrep` |

### Phase 5: Tests for Platform Module

| File | Action | Description |
|------|--------|-------------|
| `tests/utils/test_platform.py` | CREATE | Tests for platform detection module |

## Testing Strategy

### Unit Tests for Platform Module

```python
# tests/utils/test_platform.py

"""Tests for platform detection module."""

import pytest

from clams.utils.platform import (
    PlatformInfo,
    check_requirements,
    format_report,
    get_platform_info,
)


class TestGetPlatformInfo:
    """Tests for get_platform_info()."""

    def test_returns_platform_info(self):
        """get_platform_info returns PlatformInfo instance."""
        info = get_platform_info()
        assert isinstance(info, PlatformInfo)

    def test_detects_os(self):
        """Correctly detects current OS."""
        import platform as stdlib_platform

        info = get_platform_info()
        expected_os = stdlib_platform.system().lower()
        assert info.os_name == expected_os

        if expected_os == "darwin":
            assert info.is_macos is True
            assert info.is_linux is False
        elif expected_os == "linux":
            assert info.is_macos is False
            assert info.is_linux is True

    def test_caches_result(self):
        """Result is cached (same object returned)."""
        info1 = get_platform_info()
        info2 = get_platform_info()
        assert info1 is info2

    def test_ripgrep_detection(self):
        """Ripgrep detection matches shutil.which result."""
        import shutil

        info = get_platform_info()
        expected = shutil.which("rg") is not None
        assert info.has_ripgrep == expected

        if info.has_ripgrep:
            assert info.ripgrep_path is not None
        else:
            assert info.ripgrep_path is None

    def test_respects_qdrant_env_var(self, monkeypatch):
        """CLAMS_QDRANT_URL environment variable is respected."""
        # Clear cache to test with new env var
        get_platform_info.cache_clear()

        custom_url = "http://custom-qdrant:6333"
        monkeypatch.setenv("CLAMS_QDRANT_URL", custom_url)

        info = get_platform_info()
        assert info.qdrant_url == custom_url

        # Cleanup
        get_platform_info.cache_clear()


class TestCheckRequirements:
    """Tests for check_requirements()."""

    def test_empty_requirements_pass(self):
        """Empty requirements list always passes."""
        ok, missing = check_requirements([])
        assert ok is True
        assert missing == []

    def test_invalid_requirement_raises(self):
        """Invalid requirement name raises ValueError."""
        with pytest.raises(ValueError, match="Unknown requirement"):
            check_requirements(["invalid_requirement"])

    def test_returns_missing_requirements(self):
        """Missing requirements are returned in second element."""
        # Test with a requirement we know might not be met
        info = get_platform_info()

        if not info.qdrant_available:
            ok, missing = check_requirements(["qdrant"])
            assert ok is False
            assert "qdrant" in missing

    def test_all_valid_requirement_names(self):
        """All documented requirement names are valid."""
        valid_names = [
            "mps", "cuda", "ripgrep", "docker", "qdrant",
            "macos", "linux", "apple_silicon", "nvidia_gpu",
        ]

        # Should not raise
        for name in valid_names:
            check_requirements([name])


class TestFormatReport:
    """Tests for format_report()."""

    def test_produces_string(self):
        """format_report produces non-empty string."""
        info = get_platform_info()
        report = format_report(info)

        assert isinstance(report, str)
        assert len(report) > 0

    def test_contains_platform_info(self):
        """Report contains platform information."""
        info = get_platform_info()
        report = format_report(info)

        assert "Platform:" in report
        assert "PyTorch Backends:" in report
        assert "External Tools:" in report
        assert "Services:" in report

    def test_contains_mps_status(self):
        """Report includes MPS availability status."""
        info = get_platform_info()
        report = format_report(info)

        assert "MPS:" in report


class TestPlatformMarkers:
    """Tests verifying platform markers work correctly."""

    @pytest.mark.requires_ripgrep
    def test_requires_ripgrep_skips_when_missing(self):
        """Test with requires_ripgrep marker runs only when ripgrep available."""
        import shutil
        # If we get here, ripgrep must be available
        assert shutil.which("rg") is not None

    @pytest.mark.macos_only
    def test_macos_only_skips_on_linux(self):
        """Test with macos_only marker runs only on macOS."""
        import sys
        # If we get here, must be macOS
        assert sys.platform == "darwin"

    @pytest.mark.linux_only
    def test_linux_only_skips_on_macos(self):
        """Test with linux_only marker runs only on Linux."""
        import sys
        # If we get here, must be Linux
        assert sys.platform.startswith("linux")
```

### Integration Tests

The existing tests in `test_bug_014_mps_workaround.py` and `test_bug_042_regression.py` serve as integration tests once migrated to use the new markers.

### Gate Check Verification

Manually verify that:
1. Running `check_platform.sh` produces informative output
2. Tests with platform markers are correctly skipped when requirements not met
3. Platform skips do not fail the gate check
4. Non-platform skips still fail the gate check

## Migration Plan

All phases should be implemented together in a single PR to avoid a transition period where markers exist but gate checks don't recognize them:

1. **Phase 1**: Create platform detection module
2. **Phase 2**: Add pytest markers and hooks to conftest.py
3. **Phase 3**: Create check_platform.sh, update check_tests*.sh
4. **Phase 4**: Migrate existing tests to use new markers
5. **Phase 5**: Add tests for platform module

## Error Handling

- Platform detection failures (subprocess timeouts, network errors) return False for that capability
- PyTorch import failure returns False for MPS/CUDA
- Invalid requirement names raise ValueError with helpful message
- All detection functions have timeouts to prevent hangs

## Performance Considerations

- `get_platform_info()` is cached with `functools.lru_cache`
- Detection runs once per pytest session
- PyTorch is imported lazily only when checking backends
- Subprocess calls have 5-second timeouts
- HTTP requests have 2-second timeouts

## Security Considerations

- No user input is passed to subprocess commands
- URLs are validated as http/https only
- No arbitrary code execution
