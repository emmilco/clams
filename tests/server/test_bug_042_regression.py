"""Regression tests for BUG-042: Daemon crashes on macOS due to MPS fork safety.

Tests verify that the daemon can start without crashing from MPS fork issues
by ensuring PyTorch is not imported until after daemonization.
"""

import subprocess
import sys
import time
from pathlib import Path

import pytest


def test_bug_042_main_module_no_torch_at_import():
    """Verify main.py doesn't import torch at module level.

    BUG-042 root cause: PyTorch MPS initializes on import, and os.fork()
    crashes if MPS was initialized in the parent process.

    Fix: main.py defers all PyTorch-dependent imports until after fork().
    This test verifies that importing main.py doesn't trigger torch import.
    """
    # Run a subprocess that imports main and checks if torch is loaded
    check_script = """
import sys

# Import main module (should NOT trigger torch import)
from clams.server import main

# Check if torch was imported as a side effect
if 'torch' in sys.modules:
    print("FAIL: torch was imported when importing main")
    sys.exit(1)
else:
    print("PASS: torch not imported at module level")
    sys.exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0, (
        f"torch was imported when importing main.py - this will cause MPS fork crash.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_bug_042_parse_args_no_heavy_imports():
    """Verify parse_args() can be called without heavy imports.

    This ensures command-line parsing (--daemon, --stop) can happen
    before any PyTorch imports.
    """
    check_script = """
import sys

from clams.server.main import parse_args

# Simulate --daemon flag parsing
sys.argv = ['clams-server', '--daemon']
args = parse_args()

assert args.daemon is True, "Failed to parse --daemon"

# Check no torch import occurred
if 'torch' in sys.modules:
    print("FAIL: torch imported during parse_args")
    sys.exit(1)

print("PASS: parse_args works without torch")
sys.exit(0)
"""
    result = subprocess.run(
        [sys.executable, "-c", check_script],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    assert result.returncode == 0, (
        f"parse_args caused heavy imports.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


@pytest.mark.skipif(
    sys.platform != "darwin",
    reason="MPS fork safety only affects macOS"
)
def test_bug_042_daemon_start_does_not_crash():
    """Verify daemon mode starts without MPS fork crash.

    This is the actual regression test - start the daemon and verify
    it doesn't crash with the MPS fork safety error.
    """
    # First ensure no daemon is running
    subprocess.run(
        [sys.executable, "-m", "clams.server.main", "--stop"],
        capture_output=True,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Try to start daemon
    result = subprocess.run(
        [sys.executable, "-m", "clams.server.main", "--daemon"],
        capture_output=True,
        text=True,
        timeout=10,
        cwd=Path(__file__).parent.parent.parent,
    )

    # Give daemon time to either crash or start
    time.sleep(2)

    # Check the log file for crash message
    log_file = Path.home() / ".clams" / "server.log"
    if log_file.exists():
        log_content = log_file.read_text()
        assert "MPSGraphObject" not in log_content, (
            f"Daemon crashed with MPS fork safety error:\n{log_content[-500:]}"
        )

    # Try to stop the daemon (cleanup)
    subprocess.run(
        [sys.executable, "-m", "clams.server.main", "--stop"],
        capture_output=True,
        cwd=Path(__file__).parent.parent.parent,
    )
