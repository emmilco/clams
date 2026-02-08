"""Regression tests for BUG-042: Daemon crashes on macOS due to MPS fork safety.

Tests verify that the daemon can start without crashing from MPS fork issues
by ensuring PyTorch is not imported until after daemonization.
"""

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.no_resource_tracking
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
from calm.server import main

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
        stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 0, (
        f"torch was imported when importing main.py - this will cause MPS fork crash.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )


def test_bug_042_parse_args_no_heavy_imports():
    """Verify parse_args() can be called without heavy imports.

    This ensures command-line parsing can happen before any PyTorch imports.
    """
    check_script = """
import sys

from calm.server.main import parse_args

# Simulate basic flag parsing
sys.argv = ['clams-server', '--host', '127.0.0.1']
args = parse_args()

assert args.host == '127.0.0.1', "Failed to parse --host"

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
        stdin=subprocess.DEVNULL,
    )

    assert result.returncode == 0, (
        f"parse_args caused heavy imports.\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
