"""Test that check_types.sh runs without hanging.

This test verifies BUG-007 fix: gate check hangs due to tokenizer parallelism.
"""

import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.slow
def test_check_types_completes_standalone() -> None:
    """Verify that check_types.sh completes without hanging when run standalone.

    This test explicitly clears TOKENIZERS_PARALLELISM from the environment
    to verify the script handles it correctly on its own (either via inline
    setting or by sourcing clams-common.sh).
    """
    gate_script = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_types.sh"
    worktree = Path(__file__).parent.parent.parent

    # Create an environment WITHOUT TOKENIZERS_PARALLELISM to verify
    # the script handles it correctly on its own
    env = os.environ.copy()
    env.pop("TOKENIZERS_PARALLELISM", None)

    # Run the gate script with a timeout - it should complete in reasonable time
    # If it hangs, this will fail with TimeoutExpired
    result = subprocess.run(
        [str(gate_script), str(worktree)],
        capture_output=True,
        text=True,
        timeout=180,  # 180 seconds - mypy can be slow on large codebases
        env=env,
    )

    # We don't care if mypy finds type errors (it will), we just care that it completes
    # The script returns 1 if type errors are found, but that's OK for this test
    assert result.returncode in (0, 1), f"Unexpected return code: {result.returncode}"

    # Verify the script actually ran mypy
    assert "mypy" in result.stdout.lower() or "mypy" in result.stderr.lower()
