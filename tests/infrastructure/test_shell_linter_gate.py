"""Tests for the shell linter gate script (check_linter_shell.sh).

This module verifies the enhanced shell linter gate script functionality:
- bash -n syntax checking before shellcheck
- Shellcheck -S warning severity threshold
- CHECK_CHANGED_ONLY environment variable support
- clams/hooks/ default directory inclusion
- Graceful git failure fallback

Reference: SPEC-041 (Shell/Hooks Gate Check Script Enhancements)
"""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from .conftest import get_repo_root

# Path to the gate script
GATE_SCRIPT = get_repo_root() / ".claude" / "gates" / "check_linter_shell.sh"

# Check if shellcheck is available
SHELLCHECK_AVAILABLE = shutil.which("shellcheck") is not None


class TestBashSyntaxChecking:
    """Tests for bash -n syntax checking functionality."""

    def test_bash_syntax_error_detected(self, tmp_path: Path) -> None:
        """Verify bash -n catches syntax errors."""
        # Create script with syntax error (missing 'done' for while loop)
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "bad.sh"
        # This is a genuine syntax error - missing 'done' keyword
        script.write_text('#!/bin/bash\nwhile true; do\necho "broken"\n')
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 1, (
            f"Expected exit 1 for syntax error: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "SYNTAX ERROR" in result.stdout, (
            "Output should indicate syntax error. "
            f"Got: {result.stdout}"
        )

    def test_unterminated_string_detected(self, tmp_path: Path) -> None:
        """Verify bash -n catches unterminated strings."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "unclosed.sh"
        script.write_text('#!/bin/bash\necho "unclosed string\n')
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 1, (
            f"Expected exit 1 for unterminated string: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "SYNTAX ERROR" in result.stdout

    def test_valid_syntax_passes(self, tmp_path: Path) -> None:
        """Verify valid scripts pass syntax check."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "good.sh"
        script.write_text('#!/bin/bash\nset -euo pipefail\necho "hello"\n')
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 0, (
            f"Expected exit 0 for valid script: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "PASS" in result.stdout


@pytest.mark.skipif(not SHELLCHECK_AVAILABLE, reason="shellcheck not installed")
class TestShellcheckSeverity:
    """Tests for shellcheck -S warning severity threshold.

    These tests require shellcheck to be installed.
    """

    def test_shellcheck_warning_detected(self, tmp_path: Path) -> None:
        """Verify shellcheck -S warning catches warning-level issues (SC2333)."""
        # Create script with impossible condition (SC2333 - warning level)
        # This is a genuine warning: the condition is always false
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "impossible.sh"
        # SC2333 is a warning about impossible && condition
        script.write_text(
            '#!/bin/bash\n'
            'x=1\n'
            'if [[ $x = 1 ]] && [[ $x = 2 ]]; then\n'
            '    echo both\n'
            'fi\n'
        )
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        # SC2333 is warning level, so it should be caught with -S warning
        assert result.returncode == 1, (
            f"Expected exit 1 for SC2333 warning: {result.stdout}\n"
            "Shellcheck -S warning should catch SC2333 (impossible && condition)"
        )

    def test_clean_script_passes_all_checks(self, tmp_path: Path) -> None:
        """Verify clean scripts pass both bash -n and shellcheck."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "clean.sh"
        # A script that passes both bash -n and shellcheck -S warning
        script.write_text(
            '#!/bin/bash\n'
            'set -euo pipefail\n'
            'DIR="/tmp"\n'
            'rm -rf "$DIR"\n'  # Properly quoted
        )
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 0, f"Expected exit 0 for clean script: {result.stdout}"
        assert "PASS" in result.stdout


class TestChangedOnlyMode:
    """Tests for CHECK_CHANGED_ONLY environment variable support."""

    @pytest.fixture
    def git_repo(self, tmp_path: Path) -> Path:
        """Create a temporary git repo with main branch."""
        subprocess.run(
            ["git", "init"], cwd=tmp_path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        # Create initial commit on main
        (tmp_path / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "initial"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        # Rename current branch to main if needed
        subprocess.run(
            ["git", "branch", "-M", "main"],
            cwd=tmp_path,
            capture_output=True,
        )

        # Create feature branch
        subprocess.run(
            ["git", "checkout", "-b", "feature"],
            cwd=tmp_path,
            capture_output=True,
            check=True,
        )

        # Create .claude directory structure
        (tmp_path / ".claude" / "bin").mkdir(parents=True)

        return tmp_path

    def test_changed_only_with_no_shell_changes(self, git_repo: Path) -> None:
        """Verify CHECK_CHANGED_ONLY=1 exits 0 when no shell changes."""
        env = {
            **os.environ,
            "CHECK_CHANGED_ONLY": "1",
            "CLAUDE_DIR": str(git_repo / ".claude"),
        }

        result = subprocess.run(
            [str(GATE_SCRIPT), str(git_repo)],
            capture_output=True,
            text=True,
            env=env,
        )

        assert result.returncode == 0, (
            f"Expected exit 0 when no shell changes: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "No shell changes to check" in result.stdout

    def test_changed_only_checks_changed_files(self, git_repo: Path) -> None:
        """Verify CHECK_CHANGED_ONLY=1 only checks changed shell files."""
        # Create and commit a clean script on main
        script_dir = git_repo / ".claude" / "bin"
        script = script_dir / "existing.sh"
        script.write_text('#!/bin/bash\necho "existing"\n')
        script.chmod(0o755)

        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add existing"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        # Switch to feature branch and add a new (broken) script
        subprocess.run(
            ["git", "checkout", "-b", "test-feature"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        broken_script = script_dir / "broken.sh"
        # This is a genuine syntax error - missing 'done' keyword
        broken_script.write_text('#!/bin/bash\nwhile true; do\necho "broken"\n')
        broken_script.chmod(0o755)

        subprocess.run(["git", "add", "."], cwd=git_repo, capture_output=True, check=True)
        subprocess.run(
            ["git", "commit", "-m", "add broken"],
            cwd=git_repo,
            capture_output=True,
            check=True,
        )

        env = {
            **os.environ,
            "CHECK_CHANGED_ONLY": "1",
            "CLAUDE_DIR": str(git_repo / ".claude"),
        }

        result = subprocess.run(
            [str(GATE_SCRIPT), str(git_repo)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Should find and check the changed broken script
        assert result.returncode == 1, (
            f"Expected exit 1 for broken changed script: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "broken.sh" in result.stdout

    def test_git_diff_failure_fallback(self, tmp_path: Path) -> None:
        """Verify fallback to all files when git diff fails (not a git repo)."""
        # tmp_path is not a git repo
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "test.sh"
        script.write_text('#!/bin/bash\necho "hello"\n')
        script.chmod(0o755)

        env = {
            **os.environ,
            "CHECK_CHANGED_ONLY": "1",
            "CLAUDE_DIR": str(tmp_path / ".claude"),
        }

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Should fall back to checking all files and pass (script is valid)
        assert result.returncode == 0, (
            f"Expected exit 0 after fallback: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "git diff failed" in result.stdout, (
            "Should warn about git diff failure. "
            f"Got: {result.stdout}"
        )
        assert "fallback" in result.stdout.lower(), (
            "Should mention fallback. "
            f"Got: {result.stdout}"
        )


class TestClamsHooksDirectory:
    """Tests for clams/hooks/ default directory inclusion."""

    def test_clams_hooks_in_default_directories(self, tmp_path: Path) -> None:
        """Verify clams/hooks/ is included in default directories."""
        # Create a script in clams/hooks/
        hooks_dir = tmp_path / "clams" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook = hooks_dir / "test_hook.sh"
        hook.write_text('#!/bin/bash\necho "hook"\n')
        hook.chmod(0o755)

        # Also create .claude dir for CLAUDE_DIR
        (tmp_path / ".claude").mkdir(parents=True)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert "clams/hooks" in result.stdout, (
            "Default directories should include clams/hooks/. "
            f"Got: {result.stdout}"
        )

    def test_clams_hooks_syntax_error_detected(self, tmp_path: Path) -> None:
        """Verify syntax errors in clams/hooks/ are detected."""
        hooks_dir = tmp_path / "clams" / "hooks"
        hooks_dir.mkdir(parents=True)
        hook = hooks_dir / "bad_hook.sh"
        hook.write_text('#!/bin/bash\necho "unclosed\n')
        hook.chmod(0o755)

        (tmp_path / ".claude").mkdir(parents=True)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 1, (
            f"Expected exit 1 for syntax error in clams/hooks/: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "SYNTAX ERROR" in result.stdout


class TestExitCodes:
    """Tests for exit code semantics."""

    def test_exit_code_0_all_pass(self, tmp_path: Path) -> None:
        """Verify exit code 0 when all scripts pass."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "good.sh"
        script.write_text('#!/bin/bash\nset -euo pipefail\necho "hello"\n')
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 0, (
            f"Expected exit 0: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "PASS" in result.stdout

    def test_exit_code_1_syntax_error(self, tmp_path: Path) -> None:
        """Verify exit code 1 when syntax error found."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)
        script = script_dir / "bad.sh"
        # This is a genuine syntax error - missing 'done' keyword
        script.write_text('#!/bin/bash\nwhile true; do\necho "broken"\n')
        script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 1, (
            f"Expected exit 1: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "FAIL" in result.stdout

    def test_exit_code_0_no_scripts_found(self, tmp_path: Path) -> None:
        """Verify exit code 0 when no shell scripts found (with shellcheck available)."""
        (tmp_path / ".claude").mkdir(parents=True)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        # Exit code depends on shellcheck availability
        # When shellcheck unavailable and no scripts: exit 2
        # When shellcheck available and no scripts: exit 0
        if SHELLCHECK_AVAILABLE:
            assert result.returncode == 0
        else:
            assert result.returncode == 2
        assert "SKIP" in result.stdout or "No shell scripts found" in result.stdout

    def test_scripts_checked_count_in_output(self, tmp_path: Path) -> None:
        """Verify scripts checked count appears in output."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)

        # Create two valid scripts
        for name in ["one.sh", "two.sh"]:
            script = script_dir / name
            script.write_text('#!/bin/bash\necho "test"\n')
            script.chmod(0o755)

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_DIR": str(tmp_path / ".claude")},
        )

        assert result.returncode == 0, (
            f"Expected exit 0: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "2 scripts checked" in result.stdout, (
            f"Should report scripts checked count. Got: {result.stdout}"
        )


class TestShellcheckUnavailable:
    """Tests for behavior when shellcheck is unavailable."""

    def test_bash_n_runs_without_shellcheck(self, tmp_path: Path) -> None:
        """Verify bash -n runs even when shellcheck unavailable."""
        script_dir = tmp_path / ".claude" / "bin"
        script_dir.mkdir(parents=True)

        # Create a script with syntax error - missing 'done' keyword
        script = script_dir / "bad.sh"
        script.write_text('#!/bin/bash\nwhile true; do\necho "broken"\n')
        script.chmod(0o755)

        # Use a PATH that doesn't include shellcheck
        env = {
            **os.environ,
            "CLAUDE_DIR": str(tmp_path / ".claude"),
            "PATH": "/usr/bin:/bin",  # Minimal PATH without shellcheck
        }

        result = subprocess.run(
            [str(GATE_SCRIPT), str(tmp_path)],
            capture_output=True,
            text=True,
            env=env,
        )

        # Should still fail due to bash -n catching the syntax error
        assert result.returncode == 1, (
            f"Expected exit 1 from bash -n syntax check: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "SYNTAX ERROR" in result.stdout


class TestScriptHeaderComments:
    """Tests for script documentation."""

    def test_script_has_check_changed_only_documentation(self) -> None:
        """Verify script documents CHECK_CHANGED_ONLY environment variable."""
        content = GATE_SCRIPT.read_text()

        assert "CHECK_CHANGED_ONLY" in content, (
            "Script should document CHECK_CHANGED_ONLY environment variable"
        )
        assert "Environment variables:" in content, (
            "Script should have Environment variables section in header"
        )

    def test_script_has_updated_exit_code_documentation(self) -> None:
        """Verify script documents exit codes."""
        content = GATE_SCRIPT.read_text()

        assert "Exit codes:" in content, (
            "Script should have Exit codes section in header"
        )
        assert "0 -" in content and "1 -" in content and "2 -" in content, (
            "Script should document exit codes 0, 1, and 2"
        )

    def test_script_mentions_bash_n_in_header(self) -> None:
        """Verify script header mentions bash -n."""
        content = GATE_SCRIPT.read_text()
        header = content[:500]  # Check first 500 chars (header area)

        assert "bash -n" in header or "bash -n" in content[:1000], (
            "Script header should mention bash -n syntax checking"
        )
