"""PostToolUse hook for CALM.

Parses test results and suggests GHAP resolution based on outcome.

Input (stdin): {"tool_name": "Bash", "tool_input": {...}, "tool_output": "..."}
Output (stdout): GHAP feedback (max 800 chars), or empty for non-test commands
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any

from calm.hooks.common import (
    get_db_path,
    log_hook_error,
    read_json_input,
    truncate_output,
    write_output,
)

MAX_OUTPUT_CHARS = 800
MAX_TOOL_OUTPUT_CHARS = 100_000  # 100KB

# Test command patterns
TEST_PATTERNS = [
    r"\bpytest\b",
    r"\bnpm\s+test\b",
    r"\bcargo\s+test\b",
    r"\bgo\s+test\b",
    r"\bjest\b",
    r"\bmocha\b",
    r"\brspec\b",
    r"\bunittest\b",
]


def is_test_command(tool_input: dict[str, Any]) -> bool:
    """Check if the tool input represents a test command.

    Args:
        tool_input: Tool input dict (e.g., {"command": "pytest ..."})

    Returns:
        True if this is a test command
    """
    command = tool_input.get("command", "")
    if not command:
        return False

    for pattern in TEST_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return True
    return False


def parse_test_results(output: str) -> tuple[int, int] | None:
    """Parse test results from output.

    Args:
        output: Test command output

    Returns:
        Tuple of (passed, failed) or None if not parseable
    """
    # cargo test pattern: "test result: ok. X passed; Y failed"
    # Check this first since it has a specific prefix that won't match pytest
    cargo_match = re.search(
        r"test result:.*?(\d+)\s+passed[;,]\s*(\d+)\s+failed",
        output,
    )
    if cargo_match:
        passed = int(cargo_match.group(1))
        failed = int(cargo_match.group(2))
        return (passed, failed)

    # npm/jest pattern: "Tests: X passed, Y failed" or "X passed"
    # Check before pytest since it has a specific "Tests:" prefix
    jest_match = re.search(
        r"Tests?:\s*(\d+)\s+passed(?:,\s*(\d+)\s+failed)?",
        output,
    )
    if jest_match:
        passed = int(jest_match.group(1))
        failed = int(jest_match.group(2) or 0)
        return (passed, failed)

    # pytest pattern: "42 passed, 3 failed" or just "42 passed"
    # This is the most generic pattern, so check last
    pytest_match = re.search(
        r"(\d+)\s+passed(?:,\s*(\d+)\s+failed)?",
        output,
    )
    if pytest_match:
        passed = int(pytest_match.group(1))
        failed = int(pytest_match.group(2) or 0)
        return (passed, failed)

    # go test pattern: "ok" or "FAIL"
    # This is simpler - just check for overall pass/fail
    if re.search(r"^ok\s+\S+", output, re.MULTILINE):
        # Go test passed - we don't have exact counts easily
        return (1, 0)
    if re.search(r"^FAIL\s+\S+", output, re.MULTILINE):
        return (0, 1)

    return None


def get_active_ghap(db_path: Path) -> dict[str, Any] | None:
    """Get the current active GHAP entry.

    Args:
        db_path: Path to database

    Returns:
        Dict with GHAP details or None
    """
    try:
        conn = sqlite3.connect(db_path, timeout=1.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, prediction
            FROM ghap_entries
            WHERE status = 'active'
            ORDER BY created_at DESC
            LIMIT 1
            """
        )
        row = cursor.fetchone()
        conn.close()

        if row:
            return {"id": row["id"], "prediction": row["prediction"]}
        return None
    except (sqlite3.Error, OSError) as exc:
        log_hook_error("PostToolUse.get_active_ghap", exc)
        return None


def format_feedback(
    passed: int,
    failed: int,
    ghap: dict[str, Any],
) -> str:
    """Format the test result feedback.

    Args:
        passed: Number of tests passed
        failed: Number of tests failed
        ghap: Active GHAP dict

    Returns:
        Formatted feedback string
    """
    lines = ["## Test Results vs. GHAP Prediction", ""]
    lines.append(f"Tests: {passed} passed, {failed} failed")
    lines.append("")

    prediction = ghap["prediction"][:80]
    lines.append(f'Your prediction was: "{prediction}"')
    lines.append("")

    # Determine if results align with typical success/failure predictions
    tests_passed = failed == 0

    # Common success prediction keywords
    success_keywords = ["pass", "succeed", "work", "fix", "correct"]
    predicts_success = any(kw in ghap["prediction"].lower() for kw in success_keywords)

    if tests_passed and predicts_success:
        lines.append("This appears to CONFIRM your hypothesis. Consider:")
        lines.append("- `resolve_ghap --status confirmed` to record this success")
    elif not tests_passed and not predicts_success:
        lines.append("This appears to CONFIRM your hypothesis. Consider:")
        lines.append("- `resolve_ghap --status confirmed` to record this result")
    else:
        lines.append("This appears to CONTRADICT your prediction. Consider:")
        lines.append("- `update_ghap` with a revised hypothesis")
        lines.append("- `resolve_ghap --status falsified` if you've learned something")

    return "\n".join(lines)


def main() -> None:
    """Main entry point for PostToolUse hook."""
    # Read input
    input_data = read_json_input()

    # Only process Bash tool (test commands)
    if input_data.get("tool_name") != "Bash":
        write_output("")
        return

    tool_input = input_data.get("tool_input", {})
    if not isinstance(tool_input, dict):
        write_output("")
        return

    if not is_test_command(tool_input):
        write_output("")
        return

    # Get and truncate output
    tool_output = input_data.get("tool_output", "")
    if not tool_output:
        write_output("")
        return
    tool_output = tool_output[:MAX_TOOL_OUTPUT_CHARS]

    # Parse test results
    results = parse_test_results(tool_output)
    if not results:
        write_output("")
        return

    passed, failed = results

    # Check for active GHAP
    db_path = get_db_path()
    if not db_path.exists():
        write_output("")
        return

    ghap = get_active_ghap(db_path)
    if not ghap:
        write_output("")
        return

    # Format and write output
    output = format_feedback(passed, failed, ghap)
    output = truncate_output(output, MAX_OUTPUT_CHARS)
    write_output(output)


if __name__ == "__main__":
    main()
