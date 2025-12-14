"""Regression test for BUG-056: Pre-commit hook for subprocess.run stdin.

This test ensures the check_subprocess.py pre-commit hook correctly detects
subprocess calls that are missing stdin handling, which can cause test hangs.

The bug: subprocess.run() calls without stdin=subprocess.DEVNULL could wait
for input, causing tests to hang indefinitely.
"""

import subprocess
import tempfile
from pathlib import Path

import pytest


class TestBug056Regression:
    """Tests for BUG-056 fix: pre-commit hook for subprocess.run stdin handling."""

    @pytest.fixture
    def checker_path(self) -> Path:
        """Get the path to check_subprocess.py hook."""
        repo_root = Path(__file__).parent.parent.parent
        checker = repo_root / ".claude" / "hooks" / "check_subprocess.py"
        assert checker.exists(), f"Checker not found at {checker}"
        return checker

    def test_bug_056_detects_missing_stdin(self, checker_path: Path) -> None:
        """Verify the checker detects subprocess.run without stdin handling.

        This would have passed before the fix because no check existed.
        """
        # Create a temp file with unsafe subprocess call
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.run(["ls"])\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should fail (exit code 1)
            assert result.returncode == 1, (
                "Checker should reject subprocess.run without stdin handling"
            )
            assert "subprocess.run()" in result.stderr
            assert "missing stdin=" in result.stderr
        finally:
            Path(temp_path).unlink()

    def test_bug_056_accepts_stdin_devnull(self, checker_path: Path) -> None:
        """Verify the checker accepts subprocess.run with stdin=subprocess.DEVNULL."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.run(["ls"], stdin=subprocess.DEVNULL)\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should pass (exit code 0)
            assert result.returncode == 0, (
                f"Checker should accept subprocess.run with stdin=DEVNULL.\n"
                f"stderr: {result.stderr}"
            )
        finally:
            Path(temp_path).unlink()

    def test_bug_056_accepts_stdin_pipe(self, checker_path: Path) -> None:
        """Verify the checker accepts subprocess.run with stdin=subprocess.PIPE."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.run(["cat"], stdin=subprocess.PIPE)\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should pass
            assert result.returncode == 0, (
                f"Checker should accept subprocess.run with stdin=PIPE.\n"
                f"stderr: {result.stderr}"
            )
        finally:
            Path(temp_path).unlink()

    def test_bug_056_accepts_input_parameter(self, checker_path: Path) -> None:
        """Verify the checker accepts subprocess.run with input= parameter."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.run(["cat"], input=b"hello")\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should pass
            assert result.returncode == 0, (
                f"Checker should accept subprocess.run with input=.\n"
                f"stderr: {result.stderr}"
            )
        finally:
            Path(temp_path).unlink()

    def test_bug_056_detects_popen_without_stdin(self, checker_path: Path) -> None:
        """Verify the checker detects subprocess.Popen without stdin handling."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.Popen(["ls"])\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should fail
            assert result.returncode == 1, (
                "Checker should reject subprocess.Popen without stdin handling"
            )
            assert "subprocess.Popen()" in result.stderr
        finally:
            Path(temp_path).unlink()

    def test_bug_056_detects_call_without_stdin(self, checker_path: Path) -> None:
        """Verify the checker detects subprocess.call without stdin handling."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.call(["ls"])\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should fail
            assert result.returncode == 1, (
                "Checker should reject subprocess.call without stdin handling"
            )
            assert "subprocess.call()" in result.stderr
        finally:
            Path(temp_path).unlink()

    def test_bug_056_multiple_issues_reported(self, checker_path: Path) -> None:
        """Verify the checker reports all issues in a file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(
                'import subprocess\n'
                'subprocess.run(["ls"])  # line 2\n'
                'subprocess.call(["echo", "hi"])  # line 3\n'
                'subprocess.check_call(["pwd"])  # line 4\n'
            )
            temp_path = f.name

        try:
            result = subprocess.run(
                ["python", str(checker_path), temp_path],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
            )

            # Checker should fail and report all issues
            assert result.returncode == 1
            # Should mention line numbers for each issue
            assert ":2:" in result.stderr
            assert ":3:" in result.stderr
            assert ":4:" in result.stderr
        finally:
            Path(temp_path).unlink()

    def test_bug_056_pre_commit_config_exists(self) -> None:
        """Verify .pre-commit-config.yaml exists and includes subprocess check."""
        repo_root = Path(__file__).parent.parent.parent
        config_path = repo_root / ".pre-commit-config.yaml"

        assert config_path.exists(), (
            "BUG-056 REGRESSION: .pre-commit-config.yaml missing"
        )

        config = config_path.read_text()
        assert "subprocess-stdin-check" in config, (
            "BUG-056 REGRESSION: subprocess-stdin-check hook missing from config"
        )
        assert "check_subprocess.py" in config, (
            "BUG-056 REGRESSION: check_subprocess.py not referenced in config"
        )
