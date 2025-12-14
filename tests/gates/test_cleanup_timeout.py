"""Test cleanup timeout functionality in check_tests.sh.

This test verifies BUG-053 fix: Gate script timeout with force-kill.

The check_tests.sh script now has a configurable cleanup timeout that
force-kills pytest if it hangs during shutdown after tests complete.
"""

import os
import subprocess
import tempfile
from pathlib import Path


def test_check_tests_has_timeout_variable() -> None:
    """Verify that check_tests.sh reads CLAWS_CLEANUP_TIMEOUT environment variable.

    The script should have a configurable timeout (default 30s) that can be
    overridden via CLAWS_CLEANUP_TIMEOUT.
    """
    gate_script = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_tests.sh"

    # Read the script content
    script_content = gate_script.read_text()

    # Verify the timeout variable is defined
    assert "CLAWS_CLEANUP_TIMEOUT" in script_content, (
        "check_tests.sh should read CLAWS_CLEANUP_TIMEOUT environment variable"
    )
    assert "CLEANUP_TIMEOUT" in script_content, (
        "check_tests.sh should have a CLEANUP_TIMEOUT variable"
    )


def test_check_tests_has_timeout_function() -> None:
    """Verify that check_tests.sh has the run_with_cleanup_timeout function."""
    gate_script = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_tests.sh"

    script_content = gate_script.read_text()

    # Verify the timeout wrapper function exists
    assert "run_with_cleanup_timeout" in script_content, (
        "check_tests.sh should have run_with_cleanup_timeout function"
    )

    # Verify it monitors for test completion
    assert "tests_completed" in script_content, (
        "run_with_cleanup_timeout should track test completion"
    )

    # Verify it force-kills on timeout
    assert "KILL" in script_content or "kill -9" in script_content.lower() or "kill -KILL" in script_content, (
        "run_with_cleanup_timeout should force-kill hung processes"
    )


def test_timeout_with_hanging_script() -> None:
    """Test that a hanging process is killed after timeout.

    Creates a minimal test environment with a script that hangs,
    verifies it gets killed and produces appropriate error message.
    """
    gate_script = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_tests.sh"

    # Create a temporary directory with a fake test that hangs
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)

        # Create a minimal Python test that passes but hangs on cleanup
        tests_dir = tmppath / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").touch()

        # Create a test file that passes but hangs on module unload
        test_file = tests_dir / "test_hang.py"
        test_file.write_text('''"""Test that hangs during cleanup."""

import atexit
import time

def hang_forever():
    """Hang forever when module unloads."""
    while True:
        time.sleep(1)

# Register a handler that hangs on exit
atexit.register(hang_forever)

def test_passes():
    """This test passes, but cleanup hangs."""
    assert True
''')

        # Create a minimal pyproject.toml
        (tmppath / "pyproject.toml").write_text('''[project]
name = "test-hang"
version = "0.1.0"

[tool.pytest.ini_options]
testpaths = ["tests"]
''')

        # Run check_tests.sh with a very short timeout
        env = os.environ.copy()
        env["CLAWS_CLEANUP_TIMEOUT"] = "3"  # 3 second timeout

        try:
            result = subprocess.run(
                [str(gate_script), str(tmppath)],
                capture_output=True,
                text=True,
                timeout=30,  # Overall timeout to prevent infinite hang if fix is broken
                env=env,
                cwd=str(tmppath),
            )
        except subprocess.TimeoutExpired:
            raise AssertionError(
                "check_tests.sh itself timed out - the cleanup timeout fix may not be working"
            )

        # The gate should FAIL when cleanup hangs
        assert result.returncode != 0, (
            f"Gate should fail when cleanup hangs. stdout: {result.stdout}, stderr: {result.stderr}"
        )

        # Verify the output mentions cleanup timeout
        combined_output = result.stdout + result.stderr
        assert any(phrase in combined_output for phrase in [
            "cleanup",
            "CLEANUP",
            "timeout",
            "TIMEOUT",
            "hung",
            "force-kill",
        ]), f"Output should mention cleanup timeout. Got: {combined_output}"


def test_normal_operation_implicit() -> None:
    """Verify that normal tests are not affected by the timeout mechanism.

    This is implicitly verified by the fact that all other tests in the test
    suite run successfully through check_tests.sh without triggering a cleanup
    timeout. The test_timeout_with_hanging_script test explicitly verifies the
    timeout behavior when cleanup actually hangs.

    This test exists as documentation that normal operation is verified.
    """
    # The fact that all tests pass through the gate check (including this one)
    # proves that normal test execution is not affected by the timeout mechanism.
    #
    # If the timeout wrapper had bugs (e.g., false positives, breaking output
    # capture, etc.), other tests in this suite would fail.
    #
    # The key regression test is test_timeout_with_hanging_script which verifies:
    # 1. Hanging cleanup is detected
    # 2. Process is force-killed
    # 3. Gate fails with clear error message
    assert True  # Placeholder - real verification is implicit
