# SPEC-033: Platform-Specific Pre-Checks

## Background

CLAMS runs on multiple platforms (macOS, Linux) with varying hardware capabilities. Several bugs have been caused by platform-specific issues that were not caught before tests or gate checks ran:

1. **BUG-042**: Daemon crashes on macOS due to MPS (Metal Performance Shaders) fork safety. The `daemonize()` function used `os.fork()`, but PyTorch had already initialized MPS via imports, causing a crash with `MPSGraphObject initialize may have been in progress in another thread when fork() was called`.

2. **BUG-014**: Extreme memory usage (15GB+) on macOS caused by PyTorch MPS backend memory leaks during embedding operations. The fix forced CPU usage on Apple Silicon, but tests didn't initially detect when they were running on MPS.

3. **Ripgrep dependency**: `GitAnalyzer` requires `rg` (ripgrep) for blame analysis. Tests currently skip if ripgrep is not installed (see `tests/git/test_analyzer.py`), but this is the only platform dependency that's explicitly checked.

4. **Qdrant/Docker availability**: Integration tests require Qdrant (typically via Docker), but tests marked with `pytest.mark.integration` are simply excluded rather than intelligently skipped based on service availability.

## Problem Statement

Platform-specific issues cause:
- **Silent test failures**: Tests may pass on CI but fail on developer machines (or vice versa)
- **Wasted debugging time**: Developers spend time investigating failures that are actually platform-related
- **Gate check failures**: Workers fail gate checks due to environment issues, not code bugs
- **Production crashes**: Platform requirements not caught until runtime

Currently, the codebase has ad-hoc platform checks scattered across test files:
- `torch.backends.mps.is_available()` used in `test_bug_014_mps_workaround.py`
- `sys.platform != "darwin"` used in `test_bug_042_regression.py`
- `shutil.which("rg")` used in `test_analyzer.py`
- No checks for Docker/Qdrant availability

There is no centralized system for:
1. Detecting platform capabilities before test runs
2. Providing consistent skip/warn behavior
3. Informing gate checks about platform limitations
4. Documenting which tests require which platform features

## Goals

1. **Centralized platform detection**: Single module (`src/clams/utils/platform.py`) that detects all platform-specific capabilities
2. **Consistent skip behavior**: pytest fixtures/markers that skip tests when platform requirements aren't met
3. **Pre-flight checks for gate checking**: Script that validates environment before running tests
4. **Clear warnings**: When tests are skipped due to platform issues, provide actionable messages
5. **Documentation**: Clear mapping of tests to their platform requirements

## Non-Goals

- Automatic installation of missing dependencies (out of scope)
- Cross-platform CI matrix configuration (CI-specific)
- Runtime platform adaptation (already handled per-component, e.g., MPS workaround in `nomic.py`)
- Windows support (CLAMS targets macOS/Linux only)

## Solution Overview

### 1. Platform Detection Module

Create `src/clams/utils/platform.py` with a `PlatformInfo` class:

```python
@dataclass
class PlatformInfo:
    """Platform capability detection results."""

    # OS Detection
    os_name: str          # "darwin", "linux"
    os_version: str       # e.g., "Darwin 25.1.0"
    is_macos: bool
    is_linux: bool

    # Hardware
    is_apple_silicon: bool
    has_nvidia_gpu: bool

    # PyTorch Backend
    mps_available: bool   # torch.backends.mps.is_available()
    cuda_available: bool  # torch.cuda.is_available()

    # External Dependencies
    has_ripgrep: bool     # shutil.which("rg") is not None
    has_docker: bool      # shutil.which("docker") is not None
    docker_running: bool  # docker info succeeds

    # Service Availability
    qdrant_available: bool  # Can connect to Qdrant URL
```

The module provides:
- `get_platform_info() -> PlatformInfo`: Cached detection (expensive checks run once)
- `check_requirements(requirements: list[str]) -> tuple[bool, list[str]]`: Check multiple requirements, return (all_met, missing_list)

### 2. Pytest Fixtures and Markers

Add to `tests/conftest.py`:

```python
# Register platform markers
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "requires_mps: test requires MPS (Apple Silicon GPU)"
    )
    config.addinivalue_line(
        "markers",
        "requires_cuda: test requires CUDA (NVIDIA GPU)"
    )
    config.addinivalue_line(
        "markers",
        "requires_ripgrep: test requires ripgrep (rg) installed"
    )
    config.addinivalue_line(
        "markers",
        "requires_docker: test requires Docker daemon running"
    )
    config.addinivalue_line(
        "markers",
        "requires_qdrant: test requires Qdrant service available"
    )
    config.addinivalue_line(
        "markers",
        "macos_only: test only runs on macOS"
    )
    config.addinivalue_line(
        "markers",
        "linux_only: test only runs on Linux"
    )

@pytest.fixture(scope="session")
def platform_info() -> PlatformInfo:
    """Session-scoped platform capability info."""
    from clams.utils.platform import get_platform_info
    return get_platform_info()

def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip tests based on platform requirements."""
    from clams.utils.platform import get_platform_info
    info = get_platform_info()

    for item in items:
        # Check each marker type
        if item.get_closest_marker("requires_mps") and not info.mps_available:
            item.add_marker(pytest.mark.skip(
                reason="Test requires MPS (Apple Silicon GPU)"
            ))
        if item.get_closest_marker("requires_cuda") and not info.cuda_available:
            item.add_marker(pytest.mark.skip(
                reason="Test requires CUDA (NVIDIA GPU)"
            ))
        if item.get_closest_marker("requires_ripgrep") and not info.has_ripgrep:
            item.add_marker(pytest.mark.skip(
                reason="Test requires ripgrep (rg). Install: brew install ripgrep"
            ))
        if item.get_closest_marker("requires_docker") and not info.docker_running:
            item.add_marker(pytest.mark.skip(
                reason="Test requires Docker. Start Docker daemon first."
            ))
        if item.get_closest_marker("requires_qdrant") and not info.qdrant_available:
            item.add_marker(pytest.mark.skip(
                reason="Test requires Qdrant. Run: docker-compose up -d"
            ))
        if item.get_closest_marker("macos_only") and not info.is_macos:
            item.add_marker(pytest.mark.skip(reason="Test only runs on macOS"))
        if item.get_closest_marker("linux_only") and not info.is_linux:
            item.add_marker(pytest.mark.skip(reason="Test only runs on Linux"))
```

### 3. Pre-Flight Check Script

Create `.claude/gates/check_platform.sh`:

```bash
#!/usr/bin/env bash
# Pre-flight platform check for gate validation
# Runs before test suite to detect environment issues

set -euo pipefail

echo "=== Platform Pre-Flight Check ==="

# Run platform check via Python
python -c "
from clams.utils.platform import get_platform_info, format_report

info = get_platform_info()
print(format_report(info))

# Check for critical issues
issues = []

# MPS fork safety warning (BUG-042)
if info.is_macos and info.mps_available:
    print('')
    print('WARNING: MPS is available. Daemon mode uses os.fork().')
    print('         Ensure PyTorch imports happen AFTER fork() to avoid crashes.')

# Memory warning (BUG-014)
if info.mps_available:
    print('')
    print('NOTE: MPS available but disabled for embeddings (memory leak workaround).')
    print('      Embedding operations will use CPU.')

# Missing optional dependencies
if not info.has_ripgrep:
    issues.append('ripgrep not installed - git blame analysis will be limited')

if not info.docker_running:
    issues.append('Docker not running - integration tests will be skipped')

if not info.qdrant_available:
    issues.append('Qdrant not available - vector storage tests will be skipped')

if issues:
    print('')
    print('=== Environment Notes ===')
    for issue in issues:
        print(f'  - {issue}')

print('')
print('Platform check complete.')
"
```

### 4. Integration with Gate Checks

Modify `.claude/gates/check_tests.sh` to run platform pre-flight:

```bash
# At the start of run_pytest()
echo "Running platform pre-flight check..."
if ! "$SCRIPT_DIR/check_platform.sh"; then
    echo "WARNING: Platform check found issues (see above)"
    # Don't fail - just warn. Tests will be skipped appropriately.
fi
```

### 5. Test Migration

Update existing tests to use the new markers:

| Current Pattern | New Pattern |
|----------------|-------------|
| `@pytest.mark.skipif(not torch.backends.mps.is_available(), reason=...)` | `@pytest.mark.requires_mps` |
| `@pytest.mark.skipif(sys.platform != "darwin", reason=...)` | `@pytest.mark.macos_only` |
| `requires_ripgrep = pytest.mark.skipif(not HAS_RIPGREP, ...)` | `@pytest.mark.requires_ripgrep` |

**Files to update:**
- `tests/embedding/test_bug_014_mps_workaround.py` - Use `@pytest.mark.requires_mps`
- `tests/server/test_bug_042_regression.py` - Use `@pytest.mark.macos_only`
- `tests/git/test_analyzer.py` - Use `@pytest.mark.requires_ripgrep`
- Integration tests - Use `@pytest.mark.requires_qdrant`

### 6. Platform Report Format

The `format_report()` function provides a human-readable summary:

```
Platform: macOS (Darwin 25.1.0)
Architecture: Apple Silicon (arm64)

PyTorch Backends:
  - MPS: available (disabled for embeddings)
  - CUDA: not available

External Tools:
  - ripgrep: installed (/opt/homebrew/bin/rg)
  - docker: installed, daemon running

Services:
  - Qdrant: available at http://localhost:6333
```

## Detailed Design

### Platform Detection Implementation

```python
# src/clams/utils/platform.py

from __future__ import annotations

import functools
import platform
import shutil
import subprocess
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class PlatformInfo:
    """Immutable platform capability snapshot."""

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
    """Check if Docker daemon is running."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _check_qdrant_available(url: str = "http://localhost:6333") -> bool:
    """Check if Qdrant service is responding."""
    try:
        import urllib.request
        with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
            return response.status == 200
    except Exception:
        return False


def _check_pytorch_backends() -> tuple[bool, bool]:
    """Check PyTorch MPS and CUDA availability.

    Returns:
        (mps_available, cuda_available)
    """
    try:
        import torch
        mps = torch.backends.mps.is_available()
        cuda = torch.cuda.is_available()
        return mps, cuda
    except ImportError:
        return False, False


def _detect_nvidia_gpu() -> bool:
    """Detect NVIDIA GPU via nvidia-smi."""
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
def get_platform_info(qdrant_url: str = "http://localhost:6333") -> PlatformInfo:
    """Get cached platform capability info.

    This function is cached because detection is expensive (subprocess calls,
    network requests, PyTorch import). Call once per process.

    Args:
        qdrant_url: URL to check for Qdrant availability

    Returns:
        PlatformInfo with all detected capabilities
    """
    os_name = platform.system().lower()
    os_version = platform.platform()
    machine = platform.machine()

    is_macos = os_name == "darwin"
    is_linux = os_name == "linux"
    is_apple_silicon = is_macos and machine == "arm64"

    # External tools
    ripgrep_path = shutil.which("rg")
    docker_path = shutil.which("docker")

    # Service checks
    docker_running = _check_docker_running() if docker_path else False
    qdrant_available = _check_qdrant_available(qdrant_url)

    # PyTorch backends (expensive - imports torch)
    mps_available, cuda_available = _check_pytorch_backends()

    # NVIDIA GPU (only check if CUDA not available, as nvidia-smi is slow)
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


def check_requirements(
    requirements: list[str],
    qdrant_url: str = "http://localhost:6333",
) -> tuple[bool, list[str]]:
    """Check if platform meets requirements.

    Args:
        requirements: List of requirement names (e.g., ["mps", "ripgrep", "qdrant"])
        qdrant_url: URL for Qdrant availability check

    Returns:
        (all_met, missing_requirements)
    """
    info = get_platform_info(qdrant_url)

    requirement_checks = {
        "mps": info.mps_available,
        "cuda": info.cuda_available,
        "ripgrep": info.has_ripgrep,
        "docker": info.docker_running,
        "qdrant": info.qdrant_available,
        "macos": info.is_macos,
        "linux": info.is_linux,
        "apple_silicon": info.is_apple_silicon,
        "nvidia_gpu": info.has_nvidia_gpu,
    }

    missing = [req for req in requirements if not requirement_checks.get(req, False)]
    return len(missing) == 0, missing


def format_report(info: PlatformInfo) -> str:
    """Format platform info as human-readable report."""
    lines = []

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
            lines.append(f"  - docker: installed but daemon not running ({info.docker_path})")
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

### Skipped Test Handling

The pytest collection hook auto-skips tests, but skipped tests should NOT fail gate checks (unlike the current behavior in `check_tests.sh` which fails on ANY skips).

**Rationale for allowing platform skips:**
- Platform-specific tests (e.g., MPS memory tests) cannot run on CI without that hardware
- Skipping due to missing optional dependencies (ripgrep, Docker) is acceptable
- The key distinction is: skips due to **missing code** are bad, skips due to **missing platform features** are acceptable

**Update to `check_tests.sh`:**

```bash
# Current: Fail if any tests were skipped
# if [[ "$skipped" -gt 0 ]]; then
#     echo "FAIL: $skipped tests were skipped"
#     return 1
# fi

# New: Only fail if skips are NOT due to platform requirements
# Check skip reasons in test output
platform_skips=$(grep -c "SKIPPED.*\(MPS\|CUDA\|ripgrep\|Docker\|Qdrant\|macOS\|Linux\)" test_output.log 2>/dev/null || echo "0")
other_skips=$((skipped - platform_skips))

if [[ "$other_skips" -gt 0 ]]; then
    echo "FAIL: $other_skips non-platform tests were skipped"
    echo "Platform-related skips ($platform_skips) are acceptable."
    return 1
fi

if [[ "$platform_skips" -gt 0 ]]; then
    echo "NOTE: $platform_skips tests skipped due to platform requirements"
fi
```

## Acceptance Criteria

### Platform Detection Module
- [ ] `src/clams/utils/platform.py` exists with `PlatformInfo` dataclass
- [ ] `get_platform_info()` correctly detects all capabilities
- [ ] Detection is cached (only runs once per process)
- [ ] `check_requirements()` validates multiple requirements at once
- [ ] `format_report()` produces human-readable output
- [ ] Module does NOT import torch at top level (lazy import only when checking backends)

### Pytest Integration
- [ ] Custom markers registered: `requires_mps`, `requires_cuda`, `requires_ripgrep`, `requires_docker`, `requires_qdrant`, `macos_only`, `linux_only`
- [ ] Tests with markers are auto-skipped when requirements not met
- [ ] Skip messages include actionable remediation (e.g., "Install: brew install ripgrep")
- [ ] `platform_info` fixture available at session scope

### Gate Check Integration
- [ ] `.claude/gates/check_platform.sh` runs before test suite
- [ ] Platform warnings displayed but don't fail the gate
- [ ] `check_tests.sh` distinguishes platform skips from code skips
- [ ] Platform skips are allowed; code-related skips fail the gate

### Test Migration
- [ ] `tests/embedding/test_bug_014_mps_workaround.py` uses `@pytest.mark.requires_mps`
- [ ] `tests/server/test_bug_042_regression.py` uses `@pytest.mark.macos_only`
- [ ] `tests/git/test_analyzer.py` uses `@pytest.mark.requires_ripgrep`
- [ ] No more inline `pytest.mark.skipif` with platform detection logic

### Documentation
- [ ] Test markers documented in `pyproject.toml` markers section
- [ ] `GETTING_STARTED.md` updated with platform requirements section
- [ ] Clear mapping: which tests need which platform features

### Regression Tests
- [ ] Test that platform detection works on the current platform
- [ ] Test that markers correctly skip when requirements not met
- [ ] Test that `check_requirements()` returns correct results
- [ ] Test that `format_report()` produces valid output

## Open Questions

1. **Should we support Windows?**
   - **Recommendation**: No. CLAMS targets macOS/Linux only. Windows would require significant additional testing.

2. **Should platform skips count toward coverage?**
   - **Recommendation**: No. Skipped tests don't execute, so coverage is naturally limited. Document expected coverage per platform.

3. **Should we auto-detect Qdrant URL from environment?**
   - **Recommendation**: Yes, use `CLAMS_QDRANT_URL` if set, otherwise default to `localhost:6333`.

4. **Should platform check run as pytest plugin or separate script?**
   - **Recommendation**: Both. The pytest collection hook handles test-level skipping, while the shell script provides a pre-flight summary for humans.

## Migration Plan

1. **Phase 1**: Create `src/clams/utils/platform.py` with detection logic
2. **Phase 2**: Add pytest markers and collection hook to `conftest.py`
3. **Phase 3**: Create `.claude/gates/check_platform.sh`
4. **Phase 4**: Update `check_tests.sh` to allow platform skips
5. **Phase 5**: Migrate existing tests to use new markers
6. **Phase 6**: Update documentation
