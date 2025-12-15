"""Regression test for BUG-062: Auto-detect project type in gate checks.

This test verifies that:
1. Python projects are correctly detected via pyproject.toml
2. Explicit project_type in .claude/project.json overrides auto-detection
3. The detect_project_type function is available and works correctly
"""

import json
import subprocess
import tempfile
from pathlib import Path


class TestBug062Regression:
    """Tests for BUG-062 fix: project type auto-detection in gate checks."""

    def test_detect_project_type_function_exists(self) -> None:
        """Verify detect_project_type function is defined in claws-common.sh."""
        common_script = (
            Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-common.sh"
        )
        source = common_script.read_text()

        assert "detect_project_type()" in source, (
            "BUG-062 REGRESSION: detect_project_type function not found in claws-common.sh"
        )
        assert "echo \"python\"" in source, (
            "BUG-062 REGRESSION: Python detection not found in detect_project_type"
        )
        assert "echo \"javascript\"" in source, (
            "BUG-062 REGRESSION: JavaScript detection not found in detect_project_type"
        )
        assert "echo \"rust\"" in source, (
            "BUG-062 REGRESSION: Rust detection not found in detect_project_type"
        )
        assert "echo \"go\"" in source, (
            "BUG-062 REGRESSION: Go detection not found in detect_project_type"
        )

    def test_claws_gate_uses_project_type(self) -> None:
        """Verify claws-gate displays and uses project type."""
        gate_script = (
            Path(__file__).parent.parent.parent / ".claude" / "bin" / "claws-gate"
        )
        source = gate_script.read_text()

        assert "detect_project_type" in source, (
            "BUG-062 REGRESSION: claws-gate does not call detect_project_type"
        )
        assert "Project type:" in source, (
            "BUG-062 REGRESSION: claws-gate does not display project type"
        )
        assert "case \"$project_type\"" in source, (
            "BUG-062 REGRESSION: claws-gate does not dispatch based on project type"
        )

    def test_python_project_detection(self) -> None:
        """Verify Python project is detected from pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Python project marker
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = \"test\"\n")

            # Source claws-common.sh and call detect_project_type
            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            assert result.stdout.strip() == "python", (
                f"BUG-062 REGRESSION: Expected 'python', got '{result.stdout.strip()}'"
            )

    def test_javascript_project_detection(self) -> None:
        """Verify JavaScript project is detected from package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a JS project marker
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}\n')

            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            assert result.stdout.strip() == "javascript", (
                f"BUG-062 REGRESSION: Expected 'javascript', got '{result.stdout.strip()}'"
            )

    def test_rust_project_detection(self) -> None:
        """Verify Rust project is detected from Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").write_text('[package]\nname = "test"\n')

            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            assert result.stdout.strip() == "rust", (
                f"BUG-062 REGRESSION: Expected 'rust', got '{result.stdout.strip()}'"
            )

    def test_go_project_detection(self) -> None:
        """Verify Go project is detected from go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "go.mod").write_text("module test\n")

            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            assert result.stdout.strip() == "go", (
                f"BUG-062 REGRESSION: Expected 'go', got '{result.stdout.strip()}'"
            )

    def test_explicit_project_type_override(self) -> None:
        """Verify .claude/project.json overrides auto-detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create both Python markers AND explicit override to JavaScript
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = \"test\"\n")

            # Create .claude/project.json with explicit override
            claude_dir = Path(tmpdir) / ".claude"
            claude_dir.mkdir()
            (claude_dir / "project.json").write_text(
                json.dumps({"project_type": "javascript"})
            )

            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            # Should be javascript (override) not python (auto-detected)
            assert result.stdout.strip() == "javascript", (
                f"BUG-062 REGRESSION: Explicit project_type not overriding auto-detect. "
                f"Expected 'javascript', got '{result.stdout.strip()}'"
            )

    def test_unknown_project_type(self) -> None:
        """Verify unknown project type when no markers present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Empty directory - no project markers
            common_script = (
                Path(__file__).parent.parent.parent
                / ".claude"
                / "bin"
                / "claws-common.sh"
            )

            result = subprocess.run(
                [
                    "bash",
                    "-c",
                    f'source "{common_script}" && detect_project_type "{tmpdir}"',
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            assert result.returncode == 0, f"Failed: {result.stderr}"
            assert result.stdout.strip() == "unknown", (
                f"BUG-062 REGRESSION: Expected 'unknown', got '{result.stdout.strip()}'"
            )

    def test_current_project_detected_as_python(self) -> None:
        """Verify the current CLAMS project is detected as Python."""
        project_root = Path(__file__).parent.parent.parent
        common_script = project_root / ".claude" / "bin" / "claws-common.sh"

        result = subprocess.run(
            [
                "bash",
                "-c",
                f'source "{common_script}" && detect_project_type "{project_root}"',
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0, f"Failed: {result.stderr}"
        assert result.stdout.strip() == "python", (
            f"BUG-062 REGRESSION: CLAMS project should be detected as Python, "
            f"got '{result.stdout.strip()}'"
        )
