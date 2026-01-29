"""Tests for hook configuration validation (SPEC-056).

This module tests the hook validation script and verifies that:
1. validate_config.sh passes on current configuration
2. validate_config.sh fails when hook script is missing
3. validate_config.sh fails when hook script not executable
4. validate_config.sh fails when hook has syntax error
5. README documents all hooks
6. README env vars match actual usage in hook scripts
7. Validation detects missing dependencies (mocked)
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest


@pytest.fixture
def hooks_dir() -> Path:
    """Return the path to the hooks directory."""
    # Navigate from tests/hooks/ to clams/hooks/
    return Path(__file__).parent.parent.parent / "clams_scripts" / "hooks"


@pytest.fixture
def validation_script(hooks_dir: Path) -> Path:
    """Return the path to the validation script."""
    return hooks_dir / "validate_config.sh"


@pytest.fixture
def readme_path(hooks_dir: Path) -> Path:
    """Return the path to the README."""
    return hooks_dir / "README.md"


class TestValidationScriptExists:
    """Verify the validation script exists and is runnable."""

    def test_validation_script_exists(self, validation_script: Path) -> None:
        """Test that validate_config.sh exists."""
        assert validation_script.exists(), f"validate_config.sh not found at {validation_script}"

    def test_validation_script_executable(self, validation_script: Path) -> None:
        """Test that validate_config.sh is executable."""
        assert os.access(validation_script, os.X_OK), "validate_config.sh is not executable"

    def test_validation_script_has_valid_bash_syntax(self, validation_script: Path) -> None:
        """Test that validate_config.sh has valid bash syntax."""
        result = subprocess.run(
            ["bash", "-n", str(validation_script)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Syntax error: {result.stderr}"


class TestValidationPasses:
    """Verify validation passes on current configuration."""

    def test_validation_passes_current_config(
        self, hooks_dir: Path, validation_script: Path
    ) -> None:
        """Test that validation passes on the current hook configuration."""
        result = subprocess.run(
            [str(validation_script)],
            capture_output=True,
            text=True,
            cwd=str(hooks_dir),
        )
        assert result.returncode == 0, f"Validation failed:\n{result.stdout}\n{result.stderr}"
        assert "All checks passed" in result.stdout


class TestValidationFailures:
    """Verify validation fails appropriately for invalid configurations."""

    @pytest.fixture
    def temp_hooks_dir(self, hooks_dir: Path) -> Generator[Path, None, None]:
        """Create a temporary hooks directory for testing failure cases."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir)
            # Copy all files from hooks_dir
            for f in hooks_dir.iterdir():
                if f.is_file():
                    dest = temp_path / f.name
                    dest.write_bytes(f.read_bytes())
                    # Preserve executable permissions
                    if os.access(f, os.X_OK):
                        dest.chmod(dest.stat().st_mode | stat.S_IXUSR)
            yield temp_path

    def test_validation_fails_missing_hook(self, temp_hooks_dir: Path) -> None:
        """Test that validation fails when a hook script is missing."""
        # Remove one of the hooks
        hook_to_remove = temp_hooks_dir / "session_start.sh"
        hook_to_remove.unlink()

        validation_script = temp_hooks_dir / "validate_config.sh"
        result = subprocess.run(
            [str(validation_script)],
            capture_output=True,
            text=True,
            cwd=str(temp_hooks_dir),
        )
        assert result.returncode == 1, "Validation should fail when hook is missing"
        assert "session_start.sh not found" in result.stdout

    def test_validation_fails_non_executable_hook(self, temp_hooks_dir: Path) -> None:
        """Test that validation fails when a hook script is not executable."""
        # Remove execute permission
        hook_path = temp_hooks_dir / "session_start.sh"
        hook_path.chmod(stat.S_IRUSR | stat.S_IWUSR)  # Remove execute bit

        validation_script = temp_hooks_dir / "validate_config.sh"
        result = subprocess.run(
            [str(validation_script)],
            capture_output=True,
            text=True,
            cwd=str(temp_hooks_dir),
        )
        assert result.returncode == 1, "Validation should fail when hook is not executable"
        assert "not executable" in result.stdout

    def test_validation_fails_syntax_error(self, temp_hooks_dir: Path) -> None:
        """Test that validation fails when a hook has syntax errors."""
        # Introduce a syntax error
        hook_path = temp_hooks_dir / "session_start.sh"
        content = hook_path.read_text()
        # Add invalid bash syntax
        hook_path.write_text(content + "\n\nif [[ ; then\n")  # Missing condition

        validation_script = temp_hooks_dir / "validate_config.sh"
        result = subprocess.run(
            [str(validation_script)],
            capture_output=True,
            text=True,
            cwd=str(temp_hooks_dir),
        )
        assert result.returncode == 1, "Validation should fail when hook has syntax error"
        assert "syntax error" in result.stdout.lower()

    def test_validation_fails_missing_readme(self, temp_hooks_dir: Path) -> None:
        """Test that validation fails when README.md is missing."""
        readme_path = temp_hooks_dir / "README.md"
        readme_path.unlink()

        validation_script = temp_hooks_dir / "validate_config.sh"
        result = subprocess.run(
            [str(validation_script)],
            capture_output=True,
            text=True,
            cwd=str(temp_hooks_dir),
        )
        assert result.returncode == 1, "Validation should fail when README is missing"
        assert "README.md not found" in result.stdout


class TestReadmeDocumentation:
    """Verify README documents all hooks and environment variables."""

    EXPECTED_HOOKS = [
        "session_start.sh",
        "session_end.sh",
        "user_prompt_submit.sh",
        "ghap_checkin.sh",
        "outcome_capture.sh",
    ]

    EXPECTED_ENV_VARS = [
        "CLAMS_HTTP_HOST",
        "CLAMS_HTTP_PORT",
        "CLAMS_PID_FILE",
        "CLAMS_STORAGE_PATH",
        "CLAMS_GHAP_CHECK_FREQUENCY",
    ]

    def test_readme_exists(self, readme_path: Path) -> None:
        """Test that README.md exists."""
        assert readme_path.exists(), f"README.md not found at {readme_path}"

    def test_readme_documents_all_hooks(self, readme_path: Path) -> None:
        """Test that README documents all hooks."""
        content = readme_path.read_text()
        for hook in self.EXPECTED_HOOKS:
            assert hook in content, f"README missing documentation for {hook}"

    def test_readme_documents_all_env_vars(self, readme_path: Path) -> None:
        """Test that README documents all environment variables."""
        content = readme_path.read_text()
        for var in self.EXPECTED_ENV_VARS:
            assert var in content, f"README missing documentation for {var}"

    def test_readme_has_quick_reference_table(self, readme_path: Path) -> None:
        """Test that README has a quick reference table."""
        content = readme_path.read_text()
        assert "Quick Reference" in content, "README missing Quick Reference section"
        # Check for table markers
        assert "| Hook |" in content, "README missing hook reference table"

    def test_readme_has_json_schema_section(self, readme_path: Path) -> None:
        """Test that README documents the JSON output schema."""
        content = readme_path.read_text()
        assert "JSON Output Schema" in content, "README missing JSON Output Schema section"
        assert "hookSpecificOutput" in content, "README missing hookSpecificOutput documentation"

    def test_readme_has_troubleshooting_section(self, readme_path: Path) -> None:
        """Test that README has a troubleshooting section."""
        content = readme_path.read_text()
        assert "Troubleshooting" in content, "README missing Troubleshooting section"

    def test_readme_documents_session_end_not_supported(self, readme_path: Path) -> None:
        """Test that README notes session_end.sh is not supported."""
        content = readme_path.read_text()
        assert (
            "NOT SUPPORTED" in content.upper() or "not supported" in content.lower()
        ), "README should note session_end.sh is not supported"

    def test_readme_documents_config_precedence(self, readme_path: Path) -> None:
        """Test that README documents configuration precedence."""
        content = readme_path.read_text()
        assert "config.env" in content, "README should mention config.env"
        assert "config.yaml" in content, "README should mention config.yaml"
        # Should mention precedence
        assert (
            "precedence" in content.lower() or "Precedence" in content
        ), "README should document configuration precedence"


class TestEnvVarsMatchUsage:
    """Verify documented env vars match actual usage in hook scripts."""

    EXPECTED_ENV_VARS = {
        "CLAMS_HTTP_HOST": ["session_start.sh", "user_prompt_submit.sh", "ghap_checkin.sh", "outcome_capture.sh"],
        "CLAMS_HTTP_PORT": ["session_start.sh", "user_prompt_submit.sh", "ghap_checkin.sh", "outcome_capture.sh"],
        "CLAMS_PID_FILE": ["session_start.sh", "user_prompt_submit.sh"],
        "CLAMS_STORAGE_PATH": ["session_start.sh", "user_prompt_submit.sh"],
        "CLAMS_GHAP_CHECK_FREQUENCY": ["ghap_checkin.sh"],
    }

    def test_env_vars_used_in_expected_hooks(self, hooks_dir: Path) -> None:
        """Test that documented env vars are used in the expected hooks."""
        for var, expected_hooks in self.EXPECTED_ENV_VARS.items():
            for hook_name in expected_hooks:
                hook_path = hooks_dir / hook_name
                content = hook_path.read_text()
                assert var in content, f"{var} should be used in {hook_name}"

    def test_all_hooks_source_config_env(self, hooks_dir: Path) -> None:
        """Test that all hooks source ~/.clams/config.env."""
        hooks = [
            "session_start.sh",
            "session_end.sh",
            "user_prompt_submit.sh",
            "ghap_checkin.sh",
            "outcome_capture.sh",
        ]
        for hook_name in hooks:
            hook_path = hooks_dir / hook_name
            content = hook_path.read_text()
            assert "config.env" in content, f"{hook_name} should reference config.env"


class TestHookScripts:
    """Verify all hook scripts meet basic requirements."""

    HOOKS = [
        "session_start.sh",
        "session_end.sh",
        "user_prompt_submit.sh",
        "ghap_checkin.sh",
        "outcome_capture.sh",
    ]

    def test_all_hooks_exist(self, hooks_dir: Path) -> None:
        """Test that all expected hooks exist."""
        for hook in self.HOOKS:
            hook_path = hooks_dir / hook
            assert hook_path.exists(), f"Hook {hook} not found"

    def test_all_hooks_executable(self, hooks_dir: Path) -> None:
        """Test that all hooks are executable."""
        for hook in self.HOOKS:
            hook_path = hooks_dir / hook
            assert os.access(hook_path, os.X_OK), f"Hook {hook} is not executable"

    def test_all_hooks_have_valid_syntax(self, hooks_dir: Path) -> None:
        """Test that all hooks have valid bash syntax."""
        for hook in self.HOOKS:
            hook_path = hooks_dir / hook
            result = subprocess.run(
                ["bash", "-n", str(hook_path)],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0, f"Hook {hook} has syntax error: {result.stderr}"

    def test_all_hooks_have_shebang(self, hooks_dir: Path) -> None:
        """Test that all hooks have a proper shebang line."""
        for hook in self.HOOKS:
            hook_path = hooks_dir / hook
            content = hook_path.read_text()
            first_line = content.split("\n")[0]
            assert first_line.startswith("#!"), f"Hook {hook} missing shebang"
            assert "bash" in first_line, f"Hook {hook} should use bash"

    def test_all_hooks_reference_spec(self, hooks_dir: Path) -> None:
        """Test that all hooks reference their relevant SPEC in comments."""
        for hook in self.HOOKS:
            hook_path = hooks_dir / hook
            content = hook_path.read_text()
            # Should reference SPEC-029 (config) or SPEC-008 (HTTP transport) or hook event
            assert "SPEC-" in content or "Hook:" in content, (
                f"Hook {hook} should reference relevant SPEC or have Hook: comment"
            )


class TestDependencyDocumentation:
    """Verify dependencies are documented and actually used."""

    def test_curl_used_by_hooks(self, hooks_dir: Path) -> None:
        """Test that curl is used by hooks that make HTTP calls."""
        http_hooks = ["session_start.sh", "user_prompt_submit.sh", "ghap_checkin.sh", "outcome_capture.sh"]
        for hook_name in http_hooks:
            hook_path = hooks_dir / hook_name
            content = hook_path.read_text()
            assert "curl" in content, f"{hook_name} should use curl for HTTP calls"

    def test_jq_used_by_hooks(self, hooks_dir: Path) -> None:
        """Test that jq is used by hooks for JSON processing."""
        json_hooks = ["session_start.sh", "user_prompt_submit.sh", "ghap_checkin.sh", "outcome_capture.sh"]
        for hook_name in json_hooks:
            hook_path = hooks_dir / hook_name
            content = hook_path.read_text()
            assert "jq" in content, f"{hook_name} should use jq for JSON processing"

    def test_readme_documents_dependencies(self, readme_path: Path) -> None:
        """Test that README documents curl and jq as dependencies."""
        content = readme_path.read_text()
        assert "curl" in content, "README should document curl as dependency"
        assert "jq" in content, "README should document jq as dependency"
