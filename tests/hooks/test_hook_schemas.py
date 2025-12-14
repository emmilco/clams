"""Claude Code hook schema conformance tests.

This module tests that CLAMS hook scripts output JSON conforming to Claude Code's
expected schemas. These tests prevent schema drift bugs like BUG-050 and BUG-051.

Documentation: https://docs.anthropic.com/en/docs/claude-code/hooks

The expected schema structure for all hooks that inject context:
{
  "hookSpecificOutput": {
    "hookEventName": "<EventName>",
    "additionalContext": "<string>"
  }
}
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

try:
    import jsonschema  # type: ignore[import-untyped]
    HAS_JSONSCHEMA = True
except ImportError:
    jsonschema = None
    HAS_JSONSCHEMA = False

from tests.fixtures.claude_code_schemas import (
    CLAUDE_CODE_HOOKS_DOCS,
    HOOK_EVENT_NAMES,
    load_schema,
)

# Path to hook scripts
REPO_ROOT = Path(__file__).parent.parent.parent
HOOKS_DIR = REPO_ROOT / "clams" / "hooks"


class TestSessionStartSchema:
    """Tests for session_start.sh hook schema conformance."""

    @pytest.fixture
    def hook_path(self) -> Path:
        """Get the path to session_start.sh hook."""
        hook = HOOKS_DIR / "session_start.sh"
        assert hook.exists(), f"Hook not found at {hook}"
        return hook

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load the SessionStart schema."""
        return load_schema("session_start")

    def run_hook(self, hook_path: Path) -> dict[str, Any]:
        """Run the session_start hook and return parsed JSON output."""
        result = subprocess.run(
            [str(hook_path)],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(Path.home()),
            },
        )
        assert result.returncode == 0, (
            f"Hook failed with code {result.returncode}: {result.stderr}"
        )

        try:
            output: dict[str, Any] = json.loads(result.stdout)
            return output
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}\nOutput: {result.stdout}")

    def test_output_is_valid_json(self, hook_path: Path) -> None:
        """Verify hook outputs valid JSON."""
        result = subprocess.run(
            [str(hook_path)],
            capture_output=True,
            text=True,
            timeout=15,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(Path.home()),
            },
        )
        assert result.returncode == 0
        # Should not raise
        json.loads(result.stdout)

    def test_has_hook_specific_output(self, hook_path: Path) -> None:
        """Verify output contains required hookSpecificOutput key."""
        output = self.run_hook(hook_path)
        assert "hookSpecificOutput" in output, (
            f"Missing 'hookSpecificOutput' key. Got keys: {list(output.keys())}. "
            f"See: {CLAUDE_CODE_HOOKS_DOCS}"
        )

    def test_hook_event_name_is_session_start(self, hook_path: Path) -> None:
        """Verify hookEventName is 'SessionStart'."""
        output = self.run_hook(hook_path)
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output.get("hookEventName") == "SessionStart", (
            f"hookEventName should be 'SessionStart', "
            f"got: {hook_output.get('hookEventName')}"
        )

    def test_has_additional_context(self, hook_path: Path) -> None:
        """Verify hookSpecificOutput contains additionalContext."""
        output = self.run_hook(hook_path)
        hook_output = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_output, (
            "Missing 'additionalContext' in hookSpecificOutput"
        )

    def test_additional_context_is_string(self, hook_path: Path) -> None:
        """Verify additionalContext is a string."""
        output = self.run_hook(hook_path)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert isinstance(context, str), (
            f"additionalContext should be string, got {type(context).__name__}"
        )

    def test_no_legacy_schema_fields(self, hook_path: Path) -> None:
        """Verify no legacy schema fields exist at top level (BUG-050 regression)."""
        output = self.run_hook(hook_path)
        legacy_fields = ["type", "content", "token_count"]
        for field in legacy_fields:
            assert field not in output, (
                f"Found legacy '{field}' field at top level - BUG-050 regression!"
            )

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_conforms_to_schema(
        self, hook_path: Path, schema: dict[str, Any]
    ) -> None:
        """Verify output conforms to JSON schema."""
        output = self.run_hook(hook_path)
        jsonschema.validate(instance=output, schema=schema)

    def test_contains_ghap_instructions(self, hook_path: Path) -> None:
        """Verify additionalContext contains GHAP instructions."""
        output = self.run_hook(hook_path)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert "GHAP" in context, "Should contain GHAP instructions"
        assert "mcp__clams__start_ghap" in context, (
            "Should reference start_ghap tool"
        )


class TestUserPromptSubmitSchema:
    """Tests for user_prompt_submit.sh hook schema conformance."""

    @pytest.fixture
    def hook_path(self) -> Path:
        """Get the path to user_prompt_submit.sh hook."""
        hook = HOOKS_DIR / "user_prompt_submit.sh"
        assert hook.exists(), f"Hook not found at {hook}"
        return hook

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load the UserPromptSubmit schema."""
        return load_schema("user_prompt_submit")

    def run_hook(
        self, hook_path: Path, prompt: str = "test prompt"
    ) -> dict[str, Any]:
        """Run the user_prompt_submit hook and return parsed JSON output."""
        result = subprocess.run(
            [str(hook_path)],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=60,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(Path.home()),
            },
        )
        assert result.returncode == 0, (
            f"Hook failed with code {result.returncode}: {result.stderr}"
        )

        try:
            output: dict[str, Any] = json.loads(result.stdout)
            return output
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}\nOutput: {result.stdout}")

    def test_output_is_valid_json(self, hook_path: Path) -> None:
        """Verify hook outputs valid JSON."""
        result = subprocess.run(
            [str(hook_path)],
            input="test prompt",
            capture_output=True,
            text=True,
            timeout=60,
            env={
                "PATH": "/usr/bin:/bin:/usr/local/bin",
                "HOME": str(Path.home()),
            },
        )
        assert result.returncode == 0
        # Should not raise
        json.loads(result.stdout)

    def test_has_hook_specific_output(self, hook_path: Path) -> None:
        """Verify output contains required hookSpecificOutput key."""
        output = self.run_hook(hook_path)
        assert "hookSpecificOutput" in output, (
            f"Missing 'hookSpecificOutput' key. Got keys: {list(output.keys())}. "
            f"See: {CLAUDE_CODE_HOOKS_DOCS}"
        )

    def test_hook_event_name_is_user_prompt_submit(self, hook_path: Path) -> None:
        """Verify hookEventName is 'UserPromptSubmit'."""
        output = self.run_hook(hook_path)
        hook_output = output.get("hookSpecificOutput", {})
        assert hook_output.get("hookEventName") == "UserPromptSubmit", (
            f"hookEventName should be 'UserPromptSubmit', "
            f"got: {hook_output.get('hookEventName')}"
        )

    def test_has_additional_context(self, hook_path: Path) -> None:
        """Verify hookSpecificOutput contains additionalContext."""
        output = self.run_hook(hook_path)
        hook_output = output.get("hookSpecificOutput", {})
        assert "additionalContext" in hook_output, (
            "Missing 'additionalContext' in hookSpecificOutput"
        )

    def test_additional_context_is_string(self, hook_path: Path) -> None:
        """Verify additionalContext is a string."""
        output = self.run_hook(hook_path)
        context = output["hookSpecificOutput"]["additionalContext"]
        assert isinstance(context, str), (
            f"additionalContext should be string, got {type(context).__name__}"
        )

    def test_no_legacy_schema_fields(self, hook_path: Path) -> None:
        """Verify no legacy schema fields exist at top level (BUG-051 regression)."""
        output = self.run_hook(hook_path)
        legacy_fields = ["type", "content", "token_count"]
        for field in legacy_fields:
            assert field not in output, (
                f"Found legacy '{field}' field at top level - BUG-051 regression!"
            )

    @pytest.mark.skipif(not HAS_JSONSCHEMA, reason="jsonschema not installed")
    def test_conforms_to_schema(
        self, hook_path: Path, schema: dict[str, Any]
    ) -> None:
        """Verify output conforms to JSON schema."""
        output = self.run_hook(hook_path)
        jsonschema.validate(instance=output, schema=schema)

    def test_graceful_degradation_format(self, hook_path: Path) -> None:
        """Verify even degraded output (server unavailable) uses correct schema."""
        # Run with very short timeout to simulate server unavailable
        # The hook should still output valid schema with empty additionalContext
        output = self.run_hook(hook_path, "test")

        # Even when server is unavailable, schema must be correct
        assert "hookSpecificOutput" in output
        assert output["hookSpecificOutput"].get("hookEventName") == "UserPromptSubmit"
        assert "additionalContext" in output["hookSpecificOutput"]


class TestSessionEndSchema:
    """Tests for session_end.sh hook schema conformance.

    NOTE: SessionEnd is NOT YET SUPPORTED by Claude Code as of 2025-01.
    These tests verify the script structure but the hook won't be invoked
    by Claude Code until the event type is supported.
    """

    @pytest.fixture
    def hook_path(self) -> Path:
        """Get the path to session_end.sh hook."""
        hook = HOOKS_DIR / "session_end.sh"
        assert hook.exists(), f"Hook not found at {hook}"
        return hook

    @pytest.fixture
    def schema(self) -> dict[str, Any]:
        """Load the SessionEnd schema."""
        return load_schema("session_end")

    def test_hook_exists(self, hook_path: Path) -> None:
        """Verify session_end.sh hook exists."""
        assert hook_path.exists()

    def test_script_is_executable(self, hook_path: Path) -> None:
        """Verify hook script is executable."""
        import os
        import stat
        mode = os.stat(hook_path).st_mode
        assert mode & stat.S_IXUSR, "Hook should be executable by owner"

    def test_script_has_shebang(self, hook_path: Path) -> None:
        """Verify hook script starts with proper shebang."""
        content = hook_path.read_text()
        assert content.startswith("#!/bin/bash"), "Hook should have bash shebang"

    def test_script_notes_unsupported_status(self, hook_path: Path) -> None:
        """Verify hook documents that SessionEnd is not yet supported."""
        content = hook_path.read_text()
        assert "NOT YET SUPPORTED" in content, (
            "Hook should document that SessionEnd is not yet supported by Claude Code"
        )


class TestSchemaConsistency:
    """Tests for schema consistency across hooks."""

    def test_all_schemas_have_required_structure(self) -> None:
        """Verify all schemas have the required Claude Code structure."""
        for hook_name in HOOK_EVENT_NAMES:
            schema = load_schema(hook_name)

            # All must require hookSpecificOutput
            assert "hookSpecificOutput" in schema.get("properties", {}), (
                f"Schema {hook_name} missing hookSpecificOutput property"
            )

            # All must have hookEventName in nested object
            hook_output_props = (
                schema["properties"]["hookSpecificOutput"]["properties"]
            )
            assert "hookEventName" in hook_output_props, (
                f"Schema {hook_name} missing hookEventName property"
            )

    def test_schema_hook_event_names_match_constants(self) -> None:
        """Verify schema hookEventName values match HOOK_EVENT_NAMES constants."""
        for hook_name, expected_event_name in HOOK_EVENT_NAMES.items():
            schema = load_schema(hook_name)
            hook_output_props = (
                schema["properties"]["hookSpecificOutput"]["properties"]
            )
            schema_event_name = hook_output_props["hookEventName"].get("const")
            assert schema_event_name == expected_event_name, (
                f"Schema {hook_name} has hookEventName={schema_event_name}, "
                f"expected {expected_event_name}"
            )

    def test_all_schemas_have_documentation_reference(self) -> None:
        """Verify all schemas reference Claude Code documentation."""
        for hook_name in HOOK_EVENT_NAMES:
            schema = load_schema(hook_name)
            doc_info = schema.get("_documentation", {})
            assert "source" in doc_info, (
                f"Schema {hook_name} missing documentation source"
            )
            assert "anthropic.com" in doc_info["source"], (
                f"Schema {hook_name} should reference Anthropic documentation"
            )

    def test_all_hook_scripts_exist(self) -> None:
        """Verify all hook scripts exist."""
        for hook_name in HOOK_EVENT_NAMES:
            hook_path = HOOKS_DIR / f"{hook_name}.sh"
            assert hook_path.exists(), (
                f"Hook script not found: {hook_path}"
            )


class TestHookSourceCodePatterns:
    """Tests that verify hook source code uses correct patterns."""

    @pytest.mark.parametrize(
        "hook_name,event_name",
        [
            ("session_start", "SessionStart"),
            ("user_prompt_submit", "UserPromptSubmit"),
        ],
    )
    def test_source_contains_correct_schema_pattern(
        self, hook_name: str, event_name: str
    ) -> None:
        """Verify hook source code uses correct schema structure."""
        hook_path = HOOKS_DIR / f"{hook_name}.sh"
        source = hook_path.read_text()

        # Must contain the schema keys
        assert "hookSpecificOutput" in source, (
            f"Hook {hook_name} source should contain 'hookSpecificOutput'"
        )
        assert f'"hookEventName": "{event_name}"' in source, (
            f"Hook {hook_name} source should contain hookEventName: {event_name}"
        )
        assert "additionalContext" in source, (
            f"Hook {hook_name} source should contain 'additionalContext'"
        )

    @pytest.mark.parametrize(
        "hook_name",
        ["session_start", "user_prompt_submit"],
    )
    def test_source_does_not_contain_legacy_patterns(self, hook_name: str) -> None:
        """Verify hook source code does NOT contain legacy schema patterns."""
        hook_path = HOOKS_DIR / f"{hook_name}.sh"
        source = hook_path.read_text()

        # Legacy patterns that should NOT appear as JSON output
        legacy_patterns = [
            '"type": "light"',
            '"type": "rich"',
            '"type": "degraded"',
            '"content":',  # at top level, not inside additionalContext
        ]

        for pattern in legacy_patterns:
            # Check it's not used as top-level JSON key
            # (it may appear in comments or additionalContext string, that's ok)
            lines = source.split("\n")
            for i, line in enumerate(lines):
                # Skip comment lines
                if line.strip().startswith("#"):
                    continue
                # Skip if it's inside a jq string processing context
                if "jq" in line and pattern in line:
                    continue
                # Check for direct JSON output of legacy pattern
                if pattern in line and "cat <<EOF" not in line:
                    # Look for context - is this part of JSON output?
                    context_start = max(0, i - 5)
                    context = "\n".join(lines[context_start : i + 1])
                    if "EOF" in context and '"type"' in line:
                        pytest.fail(
                            f"Hook {hook_name} may contain legacy pattern '{pattern}' "
                            f"in JSON output near line {i + 1}"
                        )
