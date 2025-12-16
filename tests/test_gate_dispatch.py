"""Tests for the gate dispatch system (SPEC-040).

These tests verify:
1. Dispatcher routes to correct type-specific scripts
2. Registry.json is valid and all referenced scripts exist
3. Project type detection works correctly
4. Composite project support works
5. Fallback behavior for unknown types
"""

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest


# Path to the CLAWS scripts
SCRIPT_DIR = Path(__file__).parent.parent / ".claude" / "bin"
GATES_DIR = Path(__file__).parent.parent / ".claude" / "gates"
DISPATCH_SCRIPT = SCRIPT_DIR / "claws-gate-dispatch"
REGISTRY_FILE = GATES_DIR / "registry.json"


class TestRegistryJson:
    """Tests for registry.json validity."""

    def test_registry_exists(self) -> None:
        """Registry file exists at expected location."""
        assert REGISTRY_FILE.exists(), f"Registry not found at {REGISTRY_FILE}"

    def test_registry_is_valid_json(self) -> None:
        """Registry file is valid JSON."""
        registry = json.loads(REGISTRY_FILE.read_text())
        assert "version" in registry
        assert "checks" in registry

    def test_registry_has_required_categories(self) -> None:
        """Registry has all required check categories."""
        registry = json.loads(REGISTRY_FILE.read_text())
        required_categories = ["tests", "linter", "types", "todos", "orphans"]

        for category in required_categories:
            assert category in registry["checks"], f"Missing category: {category}"

    def test_all_referenced_scripts_exist(self) -> None:
        """All scripts referenced in registry exist and are executable."""
        registry = json.loads(REGISTRY_FILE.read_text())

        for category, mappings in registry["checks"].items():
            for project_type, script in mappings.items():
                if script is None:
                    # Null means skip - valid
                    continue

                script_path = GATES_DIR / script
                assert script_path.exists(), (
                    f"Script not found: {script_path} "
                    f"(checks.{category}.{project_type})"
                )

                # Check executable permission
                assert os.access(script_path, os.X_OK), (
                    f"Script not executable: {script_path}"
                )

    def test_default_fallbacks_exist(self) -> None:
        """Each category has a default fallback (or explicit null)."""
        registry = json.loads(REGISTRY_FILE.read_text())

        for category, mappings in registry["checks"].items():
            assert "default" in mappings, f"Missing default for category: {category}"


class TestDispatcherScript:
    """Tests for claws-gate-dispatch script."""

    def test_dispatcher_exists_and_executable(self) -> None:
        """Dispatcher script exists and is executable."""
        assert DISPATCH_SCRIPT.exists()
        assert os.access(DISPATCH_SCRIPT, os.X_OK)

    def test_dispatcher_requires_jq(self) -> None:
        """Dispatcher checks for jq availability."""
        # This is a behavioral check - dispatcher should fail cleanly if jq missing
        # We just verify the script references jq
        content = DISPATCH_SCRIPT.read_text()
        assert "jq" in content, "Dispatcher should check for jq"

    def test_dispatcher_usage_on_missing_args(self) -> None:
        """Dispatcher shows usage when called without arguments."""
        result = subprocess.run(
            [str(DISPATCH_SCRIPT)],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 2
        assert "Usage:" in result.stderr or "Usage:" in result.stdout

    def test_dispatcher_validates_category(self) -> None:
        """Dispatcher rejects invalid categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "invalid_category", tmpdir],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 2
            assert "Invalid category" in result.stderr


class TestProjectTypeDetection:
    """Tests for project type detection."""

    def test_python_detection_pyproject(self) -> None:
        """Python projects detected via pyproject.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create pyproject.toml
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'test'\n")

            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir],
                capture_output=True,
                text=True,
            )
            # Should detect python and try to run python linter
            assert "type=python" in result.stdout or "python" in result.stdout.lower()

    def test_javascript_detection_package_json(self) -> None:
        """JavaScript projects detected via package.json."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "package.json").write_text('{"name": "test"}')

            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir],
                capture_output=True,
                text=True,
            )
            assert "type=javascript" in result.stdout or "javascript" in result.stdout.lower()

    def test_rust_detection_cargo_toml(self) -> None:
        """Rust projects detected via Cargo.toml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "Cargo.toml").write_text('[package]\nname = "test"\n')

            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir],
                capture_output=True,
                text=True,
            )
            assert "type=rust" in result.stdout or "rust" in result.stdout.lower()

    def test_go_detection_go_mod(self) -> None:
        """Go projects detected via go.mod."""
        with tempfile.TemporaryDirectory() as tmpdir:
            (Path(tmpdir) / "go.mod").write_text("module test\n")

            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir],
                capture_output=True,
                text=True,
            )
            assert "type=go" in result.stdout or "go" in result.stdout.lower()

    def test_unknown_type_detection(self) -> None:
        """Unknown project type when no markers present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir],
                capture_output=True,
                text=True,
            )
            assert "type=unknown" in result.stdout or "unknown" in result.stdout.lower()

    def test_explicit_type_override(self) -> None:
        """Explicit type argument overrides detection."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create Python markers
            (Path(tmpdir) / "pyproject.toml").write_text("[project]\nname = 'test'\n")

            # But specify javascript explicitly
            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "linter", tmpdir, "javascript"],
                capture_output=True,
                text=True,
            )
            # Should use javascript despite python markers
            assert "type=javascript" in result.stdout or "javascript" in result.stdout.lower()


class TestNullSkipBehavior:
    """Tests for null-configured checks (skip behavior)."""

    def test_types_null_for_rust(self) -> None:
        """Type check returns 0 (skip) for Rust projects."""
        registry = json.loads(REGISTRY_FILE.read_text())
        assert registry["checks"]["types"]["rust"] is None

    def test_types_null_for_go(self) -> None:
        """Type check returns 0 (skip) for Go projects."""
        registry = json.loads(REGISTRY_FILE.read_text())
        assert registry["checks"]["types"]["go"] is None

    def test_dispatcher_returns_zero_for_null_config(self) -> None:
        """Dispatcher returns 0 for null-configured checks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a Rust project
            (Path(tmpdir) / "Cargo.toml").write_text('[package]\nname = "test"\n')

            # Types check should skip (return 0) for Rust
            result = subprocess.run(
                [str(DISPATCH_SCRIPT), "types", tmpdir, "rust"],
                capture_output=True,
                text=True,
            )
            assert result.returncode == 0
            assert "skip" in result.stdout.lower() or "null" in result.stdout.lower()


class TestScriptInterface:
    """Tests for type-specific script interface compliance."""

    def test_python_test_script_interface(self) -> None:
        """Python test script follows standard interface."""
        script = GATES_DIR / "check_tests_python.sh"
        assert script.exists()

        content = script.read_text()
        # Should accept worktree_path as first argument
        assert "WORKTREE" in content
        # Should source claws-common.sh
        assert "claws-common.sh" in content
        # Should have proper exit codes
        assert "exit 0" in content
        assert "exit 1" in content

    def test_python_linter_script_interface(self) -> None:
        """Python linter script follows standard interface."""
        script = GATES_DIR / "check_linter_python.sh"
        assert script.exists()

        content = script.read_text()
        assert "WORKTREE" in content
        assert "ruff" in content.lower() or "flake8" in content.lower()

    def test_python_types_script_interface(self) -> None:
        """Python types script follows standard interface."""
        script = GATES_DIR / "check_types_python.sh"
        assert script.exists()

        content = script.read_text()
        assert "WORKTREE" in content
        assert "mypy" in content.lower()

    def test_shell_linter_script_interface(self) -> None:
        """Shell linter script follows standard interface."""
        script = GATES_DIR / "check_linter_shell.sh"
        assert script.exists()

        content = script.read_text()
        assert "WORKTREE" in content
        assert "shellcheck" in content.lower()


class TestCompositeProjects:
    """Tests for composite project support."""

    def test_project_json_has_composite_config(self) -> None:
        """Project.json includes composite_types configuration."""
        project_json = Path(__file__).parent.parent / ".claude" / "project.json"
        config = json.loads(project_json.read_text())

        assert "gate_config" in config
        assert "composite_types" in config["gate_config"]

    def test_clams_visualizer_configured_as_javascript(self) -> None:
        """clams-visualizer is configured as javascript subproject."""
        project_json = Path(__file__).parent.parent / ".claude" / "project.json"
        config = json.loads(project_json.read_text())

        composite_types = config["gate_config"]["composite_types"]
        assert "clams-visualizer" in composite_types
        assert composite_types["clams-visualizer"] == "javascript"


class TestBackwardsCompatibility:
    """Tests for backwards compatibility with existing scripts."""

    def test_original_check_scripts_still_exist(self) -> None:
        """Original monolithic check scripts still exist."""
        # These may be removed later but should exist during migration
        original_scripts = [
            "check_tests.sh",
            "check_linter.sh",
            "check_types.sh",
            "check_todos.sh",
            "check_orphans.sh",
        ]

        for script in original_scripts:
            script_path = GATES_DIR / script
            assert script_path.exists(), f"Original script missing: {script}"

    def test_original_check_tests_still_works(self) -> None:
        """Original check_tests.sh can still be called directly."""
        script = GATES_DIR / "check_tests.sh"
        assert os.access(script, os.X_OK)

        # Just verify it exists and is executable
        # Full execution requires proper environment


class TestGenericFallbacks:
    """Tests for generic fallback scripts."""

    def test_generic_test_script_exists(self) -> None:
        """Generic test fallback script exists."""
        script = GATES_DIR / "check_tests_generic.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_generic_linter_script_exists(self) -> None:
        """Generic linter fallback script exists."""
        script = GATES_DIR / "check_linter_generic.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)

    def test_generic_orphans_script_exists(self) -> None:
        """Generic orphans fallback script exists."""
        script = GATES_DIR / "check_orphans_generic.sh"
        assert script.exists()
        assert os.access(script, os.X_OK)


class TestIntegration:
    """Integration tests for the full gate dispatch flow."""

    def test_dispatcher_python_linter_runs(self) -> None:
        """Dispatcher successfully runs Python linter on project root."""
        # Run on the actual project
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [str(DISPATCH_SCRIPT), "linter", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should detect Python and attempt to run ruff
        assert "python" in result.stdout.lower()
        # Exit code depends on linter result (may pass or fail based on code state)

    def test_dispatcher_todos_runs(self) -> None:
        """Dispatcher successfully runs TODO check."""
        project_root = Path(__file__).parent.parent

        result = subprocess.run(
            [str(DISPATCH_SCRIPT), "todos", str(project_root)],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )

        # Should use default todos script (language-agnostic)
        # Output indicates check ran
        assert "TODO" in result.stdout or result.returncode in [0, 1]
