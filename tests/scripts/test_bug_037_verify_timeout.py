"""Regression test for BUG-037: verify_install.py timeout too short."""

import re
from pathlib import Path


class TestBug037Regression:
    """Tests for BUG-037 fix: sufficient timeout for import verification."""

    def test_verify_install_timeout_is_sufficient(self) -> None:
        """Verify verify_install.py uses a timeout >= 15 seconds.

        The import of clams.server.main pulls in sentence-transformers/PyTorch
        which takes 4-6 seconds. A timeout of 5 seconds caused false failures.
        The timeout should be at least 15 seconds to provide adequate headroom.
        """
        # Find the verify_install.py script
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        verify_install_path = scripts_dir / "verify_install.py"
        source = verify_install_path.read_text()

        # Find the timeout parameter in subprocess.run call
        # Pattern: timeout=<number>
        timeout_match = re.search(r'timeout=(\d+)', source)

        assert timeout_match is not None, (
            "BUG-037 REGRESSION: Could not find timeout parameter in verify_install.py"
        )

        timeout_value = int(timeout_match.group(1))
        assert timeout_value >= 15, (
            f"BUG-037 REGRESSION: verify_install.py timeout is {timeout_value}s, "
            f"but should be >= 15s to handle PyTorch/sentence-transformers import time"
        )

    def test_verify_install_uses_subprocess_timeout(self) -> None:
        """Verify the subprocess.run call includes a timeout parameter."""
        scripts_dir = Path(__file__).parent.parent.parent / "scripts"
        verify_install_path = scripts_dir / "verify_install.py"
        source = verify_install_path.read_text()

        # Should have subprocess.run with timeout in verify_mcp_server function
        assert "subprocess.run" in source, (
            "verify_install.py should use subprocess.run for import verification"
        )
        assert "timeout=" in source, (
            "verify_install.py subprocess.run should have timeout parameter"
        )
        assert "TimeoutExpired" in source, (
            "verify_install.py should handle subprocess.TimeoutExpired"
        )
