"""Pytest configuration and fixtures."""

import os
import threading
from collections.abc import Generator

import pytest

from calm.utils.platform import PlatformInfo, get_platform_info

# Suppress HuggingFace tokenizers parallelism warnings in forked processes
# These warnings are noisy and don't affect test correctness
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# Enable pytest-asyncio for all tests
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture
def sample_fixture() -> str:
    """Sample fixture for testing."""
    return "test_value"


# Thread names that are expected to be long-running and should be ignored
# by the resource tracker. These are typically from third-party libraries.
_IGNORED_THREAD_PREFIXES = (
    "MainThread",
    "ThreadPoolExecutor",  # Python's ThreadPoolExecutor workers
    "Tokenizer",  # HuggingFace tokenizers background threads
    "torch",  # PyTorch background threads
    "asyncio_",  # asyncio internal threads
    "concurrent.futures",  # concurrent.futures workers
    "QueueFeederThread",  # multiprocessing queue threads
    "Thread-",  # Generic numbered threads (often from third-party libs)
    "pydevd",  # Debugger threads
)


def _is_tracked_thread(t: threading.Thread) -> bool:
    """Check if a thread should be tracked for leak detection.

    We only track non-daemon threads that aren't from known background services.
    Daemon threads are expected to be long-running and will be killed at exit.
    """
    if t.daemon:
        return False
    if t.name is None:
        return True  # Track unnamed threads
    return not any(t.name.startswith(prefix) for prefix in _IGNORED_THREAD_PREFIXES)


def _check_thread_leaks(
    baseline_threads: set[threading.Thread],
) -> list[str]:
    """Check for leaked threads and return error messages."""
    current_threads = {t for t in threading.enumerate() if _is_tracked_thread(t)}
    leaked_threads = current_threads - baseline_threads

    error_parts: list[str] = []
    if leaked_threads:
        thread_names = [t.name for t in leaked_threads]
        error_parts.append(f"{len(leaked_threads)} thread(s): {thread_names}")

    return error_parts


@pytest.fixture(autouse=True)
def thread_leak_tracker(
    request: pytest.FixtureRequest,
) -> Generator[None, None, None]:
    """Track and fail tests that leak threads.

    This fixture captures a baseline of threads before each test and checks
    for new threads after the test completes. If any threads were created
    but not joined, the test fails with an explicit error message.

    This prevents silent hangs during pytest shutdown caused by leaked threads.

    Note: Async task tracking is intentionally not implemented here because
    pytest-asyncio's event loop management makes it complex. Async task leaks
    will typically manifest as test hangs or warnings from pytest-asyncio.

    To skip this check for a specific test, use:
        @pytest.mark.no_resource_tracking
    """
    # Allow tests to opt out of resource tracking
    if request.node.get_closest_marker("no_resource_tracking"):
        yield
        return

    # Capture baseline threads
    baseline_threads = {t for t in threading.enumerate() if _is_tracked_thread(t)}

    yield

    # Check for leaked threads
    error_parts = _check_thread_leaks(baseline_threads)

    if error_parts:
        pytest.fail(
            f"Thread leak detected - {', '.join(error_parts)}. "
            "Tests must join all threads before completion."
        )


# Register the marker for opting out of resource tracking
def pytest_configure(config: pytest.Config) -> None:
    """Register custom markers including platform markers."""
    config.addinivalue_line(
        "markers",
        "no_resource_tracking: skip resource leak checking for this test",
    )

    # Platform markers (SPEC-033)
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
