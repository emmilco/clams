"""Regression test for BUG-050: SessionStart hook output format.

This test ensures the session_start.sh hook outputs the correct JSON schema
for Claude Code's SessionStart hook content injection.

The bug: Hook used custom {"type": ..., "content": ...} schema instead of
Claude Code's {"hookSpecificOutput": {"additionalContext": ...}} schema.
"""

import json
import subprocess
from pathlib import Path


def test_bug_050_session_start_hook_output_schema():
    """Verify session_start.sh outputs correct Claude Code SessionStart schema.

    This would have failed before the fix because the hook was outputting:
        {"type": "light", "content": "..."}

    Instead of the required:
        {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}
    """
    # Find the hook script
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / "clams" / "hooks" / "session_start.sh"

    assert hook_path.exists(), f"Hook not found at {hook_path}"

    # Run the hook
    result = subprocess.run(
        [str(hook_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    # Hook should exit successfully
    assert result.returncode == 0, f"Hook failed: {result.stderr}"

    # Parse output as JSON
    output = json.loads(result.stdout)

    # Verify Claude Code SessionStart schema
    assert "hookSpecificOutput" in output, (
        "Missing 'hookSpecificOutput' key. "
        f"Got keys: {list(output.keys())}. "
        "This is the BUG-050 regression - wrong schema!"
    )

    hook_output = output["hookSpecificOutput"]
    assert hook_output.get("hookEventName") == "SessionStart", (
        f"hookEventName should be 'SessionStart', got: {hook_output.get('hookEventName')}"
    )

    assert "additionalContext" in hook_output, (
        "Missing 'additionalContext' in hookSpecificOutput"
    )

    context = hook_output["additionalContext"]
    assert isinstance(context, str), f"additionalContext should be string, got {type(context)}"
    assert len(context) > 0, "additionalContext should not be empty"
    assert "GHAP" in context, "additionalContext should contain GHAP instructions"


def test_bug_050_no_legacy_schema_fields():
    """Verify the old incorrect schema fields are NOT present."""
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / "clams" / "hooks" / "session_start.sh"

    result = subprocess.run(
        [str(hook_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    output = json.loads(result.stdout)

    # These were the old (incorrect) field names
    assert "type" not in output, (
        "Found legacy 'type' field - this is the BUG-050 regression!"
    )
    assert "content" not in output, (
        "Found legacy 'content' field - this is the BUG-050 regression!"
    )


def test_bug_050_ghap_instructions_present():
    """Verify GHAP instructions are included in the context."""
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / "clams" / "hooks" / "session_start.sh"

    result = subprocess.run(
        [str(hook_path)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    output = json.loads(result.stdout)
    context = output["hookSpecificOutput"]["additionalContext"]

    # Verify key GHAP instructions are present
    assert "## GHAP Learning System" in context, "Missing GHAP header"
    assert "mcp__clams__start_ghap" in context, "Missing start_ghap tool reference"
    assert "mcp__clams__update_ghap" in context, "Missing update_ghap tool reference"
    assert "mcp__clams__resolve_ghap" in context, "Missing resolve_ghap tool reference"
