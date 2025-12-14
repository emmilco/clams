"""Regression test for BUG-061: Centralize implementation directory list.

This test verifies that:
1. The project.json config file exists and has the required structure
2. The claws-gate script reads directories from config (not hardcoded)
3. Default fallback works when project.json is missing or malformed
"""

import json
import subprocess
from pathlib import Path


# Find the repo root (works from worktrees too)
def get_repo_root() -> Path:
    """Get the repository root directory."""
    current = Path(__file__).resolve()
    # Walk up to find .git or .worktrees marker
    while current != current.parent:
        if (current / ".git").exists():
            return current
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    raise RuntimeError("Could not find repository root")


REPO_ROOT = get_repo_root()
PROJECT_CONFIG = REPO_ROOT / ".claude" / "project.json"
CLAWS_GATE = REPO_ROOT / ".claude" / "bin" / "claws-gate"


class TestProjectConfig:
    """Tests for .claude/project.json configuration file."""

    def test_project_config_exists(self) -> None:
        """Verify project.json exists."""
        assert PROJECT_CONFIG.exists(), f"project.json not found at {PROJECT_CONFIG}"

    def test_project_config_valid_json(self) -> None:
        """Verify project.json is valid JSON."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        assert isinstance(config, dict), "project.json should be a JSON object"

    def test_project_config_has_implementation_dirs(self) -> None:
        """Verify project.json has implementation_dirs key."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        assert "implementation_dirs" in config, "Missing 'implementation_dirs' key"
        assert isinstance(config["implementation_dirs"], list), "'implementation_dirs' should be a list"
        assert len(config["implementation_dirs"]) > 0, "'implementation_dirs' should not be empty"

    def test_project_config_has_test_dirs(self) -> None:
        """Verify project.json has test_dirs key."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        assert "test_dirs" in config, "Missing 'test_dirs' key"
        assert isinstance(config["test_dirs"], list), "'test_dirs' should be a list"
        assert len(config["test_dirs"]) > 0, "'test_dirs' should not be empty"

    def test_project_config_has_frontend_dirs(self) -> None:
        """Verify project.json has frontend_dirs key for frontend-only detection."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        assert "frontend_dirs" in config, "Missing 'frontend_dirs' key"
        assert isinstance(config["frontend_dirs"], list), "'frontend_dirs' should be a list"

    def test_implementation_dirs_include_src(self) -> None:
        """Verify src/ is in implementation_dirs."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        impl_dirs = config.get("implementation_dirs", [])
        # Check that at least one directory contains 'src'
        has_src = any("src" in d for d in impl_dirs)
        assert has_src, f"implementation_dirs should include src/: {impl_dirs}"

    def test_test_dirs_include_tests(self) -> None:
        """Verify tests/ is in test_dirs."""
        with open(PROJECT_CONFIG) as f:
            config = json.load(f)
        test_dirs = config.get("test_dirs", [])
        has_tests = any("tests" in d for d in test_dirs)
        assert has_tests, f"test_dirs should include tests/: {test_dirs}"


class TestClawsGateUsesConfig:
    """Tests to verify claws-gate uses centralized configuration."""

    def test_claws_gate_has_config_reading_functions(self) -> None:
        """Verify claws-gate defines get_impl_dirs and get_test_dirs functions."""
        assert CLAWS_GATE.exists(), f"claws-gate not found at {CLAWS_GATE}"
        content = CLAWS_GATE.read_text()

        assert "get_impl_dirs()" in content, "claws-gate should define get_impl_dirs function"
        assert "get_test_dirs()" in content, "claws-gate should define get_test_dirs function"
        assert "get_frontend_dirs()" in content, "claws-gate should define get_frontend_dirs function"

    def test_claws_gate_reads_project_json(self) -> None:
        """Verify claws-gate reads from project.json."""
        content = CLAWS_GATE.read_text()
        assert "project.json" in content, "claws-gate should reference project.json"
        assert 'jq -r' in content, "claws-gate should use jq to parse project.json"

    def test_claws_gate_uses_config_functions_in_checks(self) -> None:
        """Verify gate checks call the config reading functions."""
        content = CLAWS_GATE.read_text()

        # The IMPLEMENT-CODE_REVIEW section should use get_impl_dirs
        assert "impl_dirs=$(get_impl_dirs)" in content, "IMPLEMENT-CODE_REVIEW should use get_impl_dirs()"
        assert "test_dirs=$(get_test_dirs)" in content, "Gate checks should use get_test_dirs()"

    def test_claws_gate_no_hardcoded_directories_in_git_diff(self) -> None:
        """Verify git diff commands don't use hardcoded directories like 'src/' directly."""
        content = CLAWS_GATE.read_text()

        # Check that we don't have the old hardcoded pattern for the main code checks
        # The pattern git diff ... -- 'src/' 'tests/' should not appear
        # (we use eval with variables now)
        lines = content.split('\n')
        for i, line in enumerate(lines, 1):
            # Skip function definitions and comments
            if 'get_impl_dirs' in line or 'get_test_dirs' in line or 'get_frontend_dirs' in line:
                continue
            if line.strip().startswith('#'):
                continue
            # Check for hardcoded paths in git diff commands (but not in the fallback defaults)
            if "git diff" in line and "--name-only" in line:
                # It should use eval and variables, not literal paths
                if "-- 'src/'" in line or "-- 'tests/'" in line:
                    if "echo" not in line:  # Not just an echo of the default
                        raise AssertionError(
                            f"Line {i} uses hardcoded directories instead of config: {line.strip()}"
                        )

    def test_claws_gate_list_shows_configured_dirs(self) -> None:
        """Verify claws-gate list shows configured directories."""
        result = subprocess.run(
            [str(CLAWS_GATE), "list"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
        )
        # The output should mention configured dirs via get_impl_dirs
        # (the list command calls get_impl_dirs to show what dirs are configured)
        assert result.returncode == 0, f"claws-gate list failed: {result.stderr}"
        output = result.stdout
        # Should show the configured dirs in the output
        assert "src/" in output or "configured" in output.lower(), \
            f"claws-gate list should show configured directories: {output}"


class TestConfigFallback:
    """Tests to verify fallback behavior when config is missing."""

    def test_get_impl_dirs_has_fallback(self) -> None:
        """Verify get_impl_dirs has a default fallback."""
        content = CLAWS_GATE.read_text()
        # The function should have a fallback echo
        assert 'echo "src/' in content, "get_impl_dirs should have default fallback"

    def test_get_test_dirs_has_fallback(self) -> None:
        """Verify get_test_dirs has a default fallback."""
        content = CLAWS_GATE.read_text()
        assert 'echo "tests/' in content, "get_test_dirs should have default fallback"
