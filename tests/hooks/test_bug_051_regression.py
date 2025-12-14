"""Regression test for BUG-051: UserPromptSubmit hook output format.

This test ensures the user_prompt_submit.sh hook outputs the correct JSON schema
for Claude Code's UserPromptSubmit hook content injection.

The bug: Hook used custom {"type": ..., "content": ...} schema instead of
Claude Code's {"hookSpecificOutput": {"additionalContext": ...}} schema.
"""

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest


class TestBug051Regression:
    """Tests for BUG-051 fix: correct UserPromptSubmit hook output schema."""

    @pytest.fixture
    def hook_path(self) -> Path:
        """Get the path to user_prompt_submit.sh hook."""
        repo_root = Path(__file__).parent.parent.parent
        hook = repo_root / "clams" / "hooks" / "user_prompt_submit.sh"
        assert hook.exists(), f"Hook not found at {hook}"
        return hook

    def run_hook(self, hook_path: Path, prompt: str = "test prompt") -> dict[str, Any]:
        """Run the hook and return parsed JSON output."""
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
        # Hook should exit successfully
        assert result.returncode == 0, f"Hook failed with code {result.returncode}: {result.stderr}"

        # Must produce valid JSON
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Hook output is not valid JSON: {e}\nOutput: {result.stdout}")

    def test_bug_051_user_prompt_submit_hook_output_schema(
        self, hook_path: Path
    ) -> None:
        """Verify user_prompt_submit.sh outputs correct Claude Code UserPromptSubmit schema."""
        output = self.run_hook(hook_path, "test prompt for schema validation")

        # Verify Claude Code UserPromptSubmit schema
        assert "hookSpecificOutput" in output, (
            "Missing 'hookSpecificOutput' key. "
            f"Got keys: {list(output.keys())}. "
            "This is the BUG-051 regression - wrong schema!"
        )

        hook_output = output["hookSpecificOutput"]
        assert hook_output.get("hookEventName") == "UserPromptSubmit", (
            f"hookEventName should be 'UserPromptSubmit', got: {hook_output.get('hookEventName')}"
        )

        assert "additionalContext" in hook_output, (
            "Missing 'additionalContext' in hookSpecificOutput"
        )

        context = hook_output["additionalContext"]
        assert isinstance(context, str), (
            f"additionalContext should be string, got {type(context)}"
        )

    def test_bug_051_no_legacy_schema_fields(self, hook_path: Path) -> None:
        """Verify the old incorrect schema fields are NOT present."""
        output = self.run_hook(hook_path, "test prompt")

        # These were the old (incorrect) field names at the top level
        assert "type" not in output, (
            "Found legacy 'type' field - this is the BUG-051 regression!"
        )
        assert "content" not in output, (
            "Found legacy 'content' field - this is the BUG-051 regression!"
        )
        assert "token_count" not in output, (
            "Found legacy 'token_count' field - this is the BUG-051 regression!"
        )

    def test_bug_051_source_contains_correct_schema(self) -> None:
        """Verify the hook source code uses the correct schema pattern."""
        repo_root = Path(__file__).parent.parent.parent
        hook_path = repo_root / "clams" / "hooks" / "user_prompt_submit.sh"
        source = hook_path.read_text()

        # Should contain the correct schema structure
        assert "hookSpecificOutput" in source, (
            "Hook source should contain 'hookSpecificOutput'"
        )
        assert '"hookEventName": "UserPromptSubmit"' in source, (
            "Hook source should contain hookEventName: UserPromptSubmit"
        )
        assert "additionalContext" in source, (
            "Hook source should contain 'additionalContext'"
        )

        # Should NOT contain the old buggy patterns as JSON keys (with quotes)
        # Note: We check for the exact patterns used in the old JSON output
        assert '"type": "rich"' not in source, (
            "BUG-051 REGRESSION: Hook still uses type: rich pattern"
        )
        assert '"type": "degraded"' not in source, (
            "BUG-051 REGRESSION: Hook still uses type: degraded pattern"
        )
