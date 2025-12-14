"""Regression tests for BUG-055: Mark and exclude slow tests.

This test verifies that:
1. The slow marker is properly configured in pytest
2. Slow tests are excluded from default runs
3. Slow tests can be explicitly included with -m slow
"""

import subprocess
from pathlib import Path

import pytest


def test_slow_marker_is_recognized() -> None:
    """Verify that pytest recognizes the slow marker without warnings."""
    project_root = Path(__file__).parent.parent

    result = subprocess.run(
        ["python", "-m", "pytest", "--markers"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    assert result.returncode == 0
    assert "slow" in result.stdout
    assert ">15s" in result.stdout or "excluded by default" in result.stdout


def test_slow_tests_excluded_by_default() -> None:
    """Verify that slow tests are excluded from default pytest runs."""
    project_root = Path(__file__).parent.parent

    # Collect tests in dry-run mode (no execution)
    result = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # The output should NOT include tests marked as slow
    # These specific tests are known to be marked slow:
    # Use full path to avoid matching similarly named tests
    assert "test_analyzer.py::test_integration_with_real_repo" not in result.stdout
    assert "test_check_types.py::test_check_types_completes_standalone" not in result.stdout


def test_slow_tests_can_be_explicitly_run() -> None:
    """Verify that slow tests can be included with -m slow."""
    project_root = Path(__file__).parent.parent

    # Collect slow tests in dry-run mode
    result = subprocess.run(
        ["python", "-m", "pytest", "-m", "slow", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Should find slow tests when explicitly requested
    assert result.returncode == 0
    # Should have collected at least some tests
    lines = [
        line for line in result.stdout.split("\n")
        if line.strip() and not line.startswith("=")
    ]
    assert len(lines) > 0, "No slow tests found when running with -m slow"


def test_all_tests_can_be_run_with_empty_marker() -> None:
    """Verify that all tests (including slow) can be run with -m ''."""
    project_root = Path(__file__).parent.parent

    # Count tests with default exclusion
    default_result = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Count all tests (no marker filter)
    all_result = subprocess.run(
        ["python", "-m", "pytest", "-m", "", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd=project_root,
    )

    # Extract test counts from output
    # Format: "X tests collected" or similar
    def count_tests(output: str) -> int:
        # Count lines that look like test items (end with .py::test_*)
        return len([
            line for line in output.split("\n")
            if "::test_" in line or "::Test" in line
        ])

    default_count = count_tests(default_result.stdout)
    all_count = count_tests(all_result.stdout)

    # All tests should be >= default tests (default excludes slow)
    assert all_count >= default_count, (
        f"Expected all tests ({all_count}) >= default tests ({default_count})"
    )


@pytest.mark.slow
def test_this_test_is_marked_slow() -> None:
    """A test marked as slow to verify the marker works.

    This test should NOT run in the default test suite.
    It should only run when explicitly requested with -m slow or -m ''.
    """
    pass


def test_this_test_runs_by_default() -> None:
    """A test that should run in the default test suite."""
    pass
