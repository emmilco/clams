"""Regression test for BUG-082: Pre-commit hooks deleted during CALM migration.

Verifies that the pre-commit hook scripts exist and function correctly:
- check_heavy_imports.py catches top-level heavy package imports
- check_subprocess.py catches subprocess calls without stdin handling
- Both scripts allow valid code to pass
"""

import ast
import subprocess
import sys
from pathlib import Path

import pytest

# Project root (where .claude/hooks/ and .pre-commit-config.yaml live)
PROJECT_ROOT = Path(__file__).parent.parent


class TestPreCommitConfigExists:
    """Verify pre-commit configuration and hook scripts are present."""

    def test_pre_commit_config_exists(self) -> None:
        """Pre-commit config must exist at project root."""
        config = PROJECT_ROOT / ".pre-commit-config.yaml"
        assert config.exists(), (
            ".pre-commit-config.yaml missing from project root. "
            "See BUG-082: SPEC-058-08 accidentally deleted it."
        )

    def test_heavy_imports_hook_exists(self) -> None:
        """Heavy imports check hook must exist."""
        hook = PROJECT_ROOT / ".claude" / "hooks" / "check_heavy_imports.py"
        assert hook.exists(), (
            ".claude/hooks/check_heavy_imports.py missing. "
            "See BUG-082: SPEC-058-08 accidentally deleted it."
        )

    def test_subprocess_hook_exists(self) -> None:
        """Subprocess check hook must exist."""
        hook = PROJECT_ROOT / ".claude" / "hooks" / "check_subprocess.py"
        assert hook.exists(), (
            ".claude/hooks/check_subprocess.py missing. "
            "See BUG-082: SPEC-058-08 accidentally deleted it."
        )

    def test_hooks_are_valid_python(self) -> None:
        """Both hook scripts must parse without syntax errors."""
        for name in ["check_heavy_imports.py", "check_subprocess.py"]:
            hook = PROJECT_ROOT / ".claude" / "hooks" / name
            if hook.exists():
                source = hook.read_text()
                ast.parse(source, filename=name)


class TestHeavyImportsHook:
    """Verify the heavy imports hook catches violations."""

    @pytest.fixture
    def hook_path(self) -> Path:
        return PROJECT_ROOT / ".claude" / "hooks" / "check_heavy_imports.py"

    def test_catches_top_level_torch_import(
        self, hook_path: Path, tmp_path: Path
    ) -> None:
        """Hook must flag top-level 'import torch'."""
        test_file = tmp_path / "bad_module.py"
        test_file.write_text("import torch\n")
        result = subprocess.run(
            [sys.executable, str(hook_path), str(test_file)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 1
        assert "heavy packages" in result.stderr.lower()

    def test_allows_lazy_import_in_function(
        self, hook_path: Path, tmp_path: Path
    ) -> None:
        """Hook must allow imports inside functions (lazy import pattern)."""
        test_file = tmp_path / "good_module.py"
        test_file.write_text(
            "def get_model():\n    import torch\n    return torch.tensor(1)\n"
        )
        result = subprocess.run(
            [sys.executable, str(hook_path), str(test_file)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0

    def test_allows_test_files(
        self, hook_path: Path, tmp_path: Path
    ) -> None:
        """Hook must skip test files (they don't run in production)."""
        test_file = tmp_path / "test_something.py"
        test_file.write_text("import torch\n")
        result = subprocess.run(
            [sys.executable, str(hook_path), str(test_file)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0

    def test_references_calm_not_clams(self, hook_path: Path) -> None:
        """Hook ALLOWED_MODULES must reference calm paths, not clams paths."""
        source = hook_path.read_text()
        assert "src/calm/" in source, "ALLOWED_MODULES should reference src/calm/"
        assert "src/clams/" not in source, (
            "ALLOWED_MODULES still references src/clams/ — "
            "should have been updated during CALM migration"
        )


class TestSubprocessHook:
    """Verify the subprocess hook catches violations."""

    @pytest.fixture
    def hook_path(self) -> Path:
        return PROJECT_ROOT / ".claude" / "hooks" / "check_subprocess.py"

    def test_catches_subprocess_run_without_stdin(
        self, hook_path: Path, tmp_path: Path
    ) -> None:
        """Hook must flag subprocess.run() without stdin handling."""
        test_file = tmp_path / "bad_subprocess.py"
        test_file.write_text(
            'import subprocess\nsubprocess.run(["ls"])\n'
        )
        result = subprocess.run(
            [sys.executable, str(hook_path), str(test_file)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 1
        assert "stdin" in result.stderr.lower()

    def test_allows_subprocess_with_stdin(
        self, hook_path: Path, tmp_path: Path
    ) -> None:
        """Hook must allow subprocess.run() with stdin=subprocess.DEVNULL."""
        test_file = tmp_path / "good_subprocess.py"
        test_file.write_text(
            "import subprocess\n"
            'subprocess.run(["ls"], stdin=subprocess.DEVNULL)\n'
        )
        result = subprocess.run(
            [sys.executable, str(hook_path), str(test_file)],
            capture_output=True,
            text=True,
            stdin=subprocess.DEVNULL,
        )
        assert result.returncode == 0
