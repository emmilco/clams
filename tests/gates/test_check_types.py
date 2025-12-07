"""Test that check_types.sh runs without hanging.

This test verifies BUG-007 fix: gate check hangs due to tokenizer parallelism.
"""

import subprocess
import sys
from pathlib import Path


def test_check_types_completes() -> None:
    """Verify that check_types.sh completes without hanging."""
    gate_script = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_types.sh"
    worktree = Path(__file__).parent.parent.parent

    # Run the gate script with a timeout - it should complete in reasonable time
    # If it hangs, this will fail with TimeoutExpired
    result = subprocess.run(
        [str(gate_script), str(worktree)],
        capture_output=True,
        text=True,
        timeout=60,  # 60 seconds should be more than enough
    )

    # We don't care if mypy finds type errors (it will), we just care that it completes
    # The script returns 1 if type errors are found, but that's OK for this test
    assert result.returncode in (0, 1), f"Unexpected return code: {result.returncode}"

    # Verify the script actually ran mypy
    assert "mypy" in result.stdout.lower() or "mypy" in result.stderr.lower()
