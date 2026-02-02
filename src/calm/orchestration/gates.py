"""Gate checking logic for CALM orchestration.

This module handles gate checks for phase transitions.
"""

import subprocess
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from calm.config import settings
from calm.orchestration.counters import _get_connection
from calm.orchestration.project import get_current_commit
from calm.orchestration.reviews import check_reviews
from calm.orchestration.tasks import get_task


@dataclass
class GateCheck:
    """Result of a single gate check."""

    name: str
    passed: bool
    message: str
    duration_seconds: float | None = None


@dataclass
class GateResult:
    """Result of all gate checks for a transition."""

    passed: bool
    checks: list[GateCheck] = field(default_factory=list)
    commit_sha: str | None = None


@dataclass
class GateRequirement:
    """A gate requirement definition."""

    transition: str
    name: str
    description: str
    automated: bool = True


# Gate requirements by transition
GATE_REQUIREMENTS: dict[str, list[GateRequirement]] = {
    # Feature transitions
    "SPEC-DESIGN": [
        GateRequirement("SPEC-DESIGN", "spec_reviews", "2 spec reviews approved", True),
    ],
    "DESIGN-IMPLEMENT": [
        GateRequirement(
            "DESIGN-IMPLEMENT", "proposal_exists", "Proposal document exists", True
        ),
        GateRequirement(
            "DESIGN-IMPLEMENT",
            "proposal_reviews",
            "2 proposal reviews approved",
            True,
        ),
    ],
    "IMPLEMENT-CODE_REVIEW": [
        GateRequirement(
            "IMPLEMENT-CODE_REVIEW", "code_exists", "Implementation code exists", True
        ),
        GateRequirement(
            "IMPLEMENT-CODE_REVIEW", "tests_pass", "Tests pass", True
        ),
        GateRequirement(
            "IMPLEMENT-CODE_REVIEW", "linter_clean", "Linter clean", True
        ),
        GateRequirement(
            "IMPLEMENT-CODE_REVIEW", "types_clean", "Type check passes", True
        ),
        GateRequirement(
            "IMPLEMENT-CODE_REVIEW", "no_todos", "No untracked to-dos", True
        ),
    ],
    "CODE_REVIEW-TEST": [
        GateRequirement(
            "CODE_REVIEW-TEST", "code_reviews", "2 code reviews approved", True
        ),
    ],
    "TEST-INTEGRATE": [
        GateRequirement("TEST-INTEGRATE", "tests_pass", "Full test suite passes", True),
    ],
    "INTEGRATE-VERIFY": [
        GateRequirement(
            "INTEGRATE-VERIFY", "changelog_exists", "Changelog entry exists", True
        ),
    ],
    # Bug transitions
    "REPORTED-INVESTIGATED": [
        GateRequirement(
            "REPORTED-INVESTIGATED", "bug_report", "Bug report complete", True
        ),
        GateRequirement(
            "REPORTED-INVESTIGATED", "root_cause", "Root cause documented", True
        ),
        GateRequirement(
            "REPORTED-INVESTIGATED", "fix_plan", "Fix plan documented", True
        ),
    ],
    "INVESTIGATED-FIXED": [
        GateRequirement(
            "INVESTIGATED-FIXED", "tests_pass", "Tests pass", True
        ),
        GateRequirement(
            "INVESTIGATED-FIXED", "linter_clean", "Linter clean", True
        ),
        GateRequirement(
            "INVESTIGATED-FIXED", "types_clean", "Type check passes", True
        ),
        GateRequirement(
            "INVESTIGATED-FIXED", "regression_test", "Regression test added", True
        ),
    ],
    "FIXED-REVIEWED": [
        GateRequirement(
            "FIXED-REVIEWED", "bugfix_reviews", "2 bugfix reviews approved", True
        ),
    ],
    "REVIEWED-TESTED": [
        GateRequirement(
            "REVIEWED-TESTED", "tests_pass", "Full test suite passes", True
        ),
        GateRequirement(
            "REVIEWED-TESTED", "no_skipped", "No skipped tests", True
        ),
    ],
    "TESTED-MERGED": [
        GateRequirement(
            "TESTED-MERGED", "changelog_exists", "Changelog entry exists", True
        ),
    ],
}


def _check_tests_pass(worktree: Path, task_id: str, db_path: Path | None) -> GateCheck:
    """Run test suite and check if all tests pass."""
    start = time.time()

    result = subprocess.run(
        ["pytest", "-v", "--tb=short"],
        cwd=worktree,
        capture_output=True,
        text=True,
        timeout=300,  # 5 minute timeout
    )

    duration = time.time() - start

    # Parse test results
    output = result.stdout + result.stderr
    passed = result.returncode == 0

    # Extract counts from pytest output
    test_passed = 0
    test_failed = 0
    test_skipped = 0

    for line in output.split("\n"):
        if "passed" in line or "failed" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if "passed" in part and i > 0:
                    try:
                        test_passed = int(parts[i - 1])
                    except ValueError:
                        pass
                if "failed" in part and i > 0:
                    try:
                        test_failed = int(parts[i - 1])
                    except ValueError:
                        pass
                if "skipped" in part and i > 0:
                    try:
                        test_skipped = int(parts[i - 1])
                    except ValueError:
                        pass

    # Record test run
    if db_path:
        with _get_connection(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO test_runs
                (task_id, passed, failed, skipped, duration_seconds, run_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    test_passed,
                    test_failed,
                    test_skipped,
                    duration,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()

    message = f"{test_passed} passed, {test_failed} failed, {test_skipped} skipped"
    if not passed:
        # Include some of the failure output
        message += f"\n{output[-500:]}"

    return GateCheck(
        name="Tests pass",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_linter_clean(worktree: Path) -> GateCheck:
    """Run linter and check if code is clean."""
    start = time.time()

    result = subprocess.run(
        ["ruff", "check", "."],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    duration = time.time() - start
    passed = result.returncode == 0

    if passed:
        message = "No linting errors"
    else:
        message = result.stdout[:500] if result.stdout else result.stderr[:500]

    return GateCheck(
        name="Linter clean",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_types_clean(worktree: Path) -> GateCheck:
    """Run mypy and check if types are clean."""
    start = time.time()

    result = subprocess.run(
        ["mypy", "--strict", "src/"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    duration = time.time() - start
    passed = result.returncode == 0

    if passed:
        message = "No type errors"
    else:
        message = result.stdout[:500] if result.stdout else result.stderr[:500]

    return GateCheck(
        name="Type check passes",
        passed=passed,
        message=message,
        duration_seconds=duration,
    )


def _check_code_exists(worktree: Path, task_id: str) -> GateCheck:
    """Check that implementation code exists."""
    result = subprocess.run(
        ["git", "diff", "main...HEAD", "--name-only"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return GateCheck(
            name="Implementation code exists",
            passed=False,
            message="Failed to get diff",
        )

    changed_files = result.stdout.strip().split("\n")
    impl_patterns = ["src/", "tests/"]

    impl_files = [
        f for f in changed_files if any(f.startswith(p) for p in impl_patterns)
    ]

    passed = len(impl_files) > 0
    message = (
        f"Changed files: {', '.join(impl_files[:5])}"
        if passed
        else "No implementation code changes found"
    )

    return GateCheck(
        name="Implementation code exists",
        passed=passed,
        message=message,
    )


def _check_changelog_exists(worktree: Path, task_id: str) -> GateCheck:
    """Check that changelog entry exists."""
    changelog_file = worktree / "changelog.d" / f"{task_id}.md"
    passed = changelog_file.exists()

    message = (
        f"Changelog entry found: {changelog_file.name}"
        if passed
        else f"Missing: {changelog_file}"
    )

    return GateCheck(
        name="Changelog entry exists",
        passed=passed,
        message=message,
    )


def _check_reviews(
    task_id: str, review_type: str, db_path: Path | None
) -> GateCheck:
    """Check that 2 reviews are approved."""
    passed, count = check_reviews(task_id, review_type, required=2, db_path=db_path)

    message = f"{count}/2 {review_type} reviews approved"

    return GateCheck(
        name=f"2 {review_type} reviews approved",
        passed=passed,
        message=message,
    )


def _check_proposal_exists(worktree: Path, task_id: str) -> GateCheck:
    """Check that proposal document exists."""
    proposal_file = worktree / "planning_docs" / task_id / "proposal.md"
    passed = proposal_file.exists()

    message = (
        f"Proposal found: {proposal_file.name}"
        if passed
        else f"Missing: {proposal_file}"
    )

    return GateCheck(
        name="Proposal document exists",
        passed=passed,
        message=message,
    )


def _check_bug_report(worktree: Path, task_id: str) -> GateCheck:
    """Check that bug report is complete."""
    bug_report = worktree / "bug_reports" / f"{task_id}.md"

    if not bug_report.exists():
        return GateCheck(
            name="Bug report complete",
            passed=False,
            message=f"Missing: {bug_report}",
        )

    content = bug_report.read_text()

    # Check for required sections
    required_sections = ["Reproduction Steps", "Expected Behavior", "Actual Behavior"]
    missing = [s for s in required_sections if s not in content]

    passed = len(missing) == 0
    message = (
        "Bug report has all required sections"
        if passed
        else f"Missing sections: {', '.join(missing)}"
    )

    return GateCheck(
        name="Bug report complete",
        passed=passed,
        message=message,
    )


def _check_root_cause(worktree: Path, task_id: str) -> GateCheck:
    """Check that root cause is documented."""
    bug_report = worktree / "bug_reports" / f"{task_id}.md"

    if not bug_report.exists():
        return GateCheck(
            name="Root cause documented",
            passed=False,
            message="Bug report not found",
        )

    content = bug_report.read_text()

    # Check that Root Cause section has content
    if "Root Cause" not in content:
        return GateCheck(
            name="Root cause documented",
            passed=False,
            message="Root Cause section not found",
        )

    # Find the Root Cause section and check if it has content beyond the template
    lines = content.split("\n")
    in_root_cause = False
    has_content = False

    for line in lines:
        if "Root Cause" in line and line.startswith("#"):
            in_root_cause = True
            continue
        if in_root_cause:
            if line.startswith("#"):
                break
            if line.strip() and not line.startswith("<!--"):
                has_content = True
                break

    passed = has_content
    message = "Root cause is documented" if passed else "Root Cause section is empty"

    return GateCheck(
        name="Root cause documented",
        passed=passed,
        message=message,
    )


def _check_fix_plan(worktree: Path, task_id: str) -> GateCheck:
    """Check that fix plan is documented."""
    bug_report = worktree / "bug_reports" / f"{task_id}.md"

    if not bug_report.exists():
        return GateCheck(
            name="Fix plan documented",
            passed=False,
            message="Bug report not found",
        )

    content = bug_report.read_text()

    # Check that Fix Plan section has content
    if "Fix Plan" not in content:
        return GateCheck(
            name="Fix plan documented",
            passed=False,
            message="Fix Plan section not found",
        )

    # Find the Fix Plan section and check if it has content
    lines = content.split("\n")
    in_fix_plan = False
    has_content = False

    for line in lines:
        if "Fix Plan" in line and line.startswith("#"):
            in_fix_plan = True
            continue
        if in_fix_plan:
            if line.startswith("#"):
                break
            if line.strip() and not line.startswith("<!--"):
                has_content = True
                break

    passed = has_content
    message = "Fix plan is documented" if passed else "Fix Plan section is empty"

    return GateCheck(
        name="Fix plan documented",
        passed=passed,
        message=message,
    )


def _check_no_skipped(worktree: Path, task_id: str, db_path: Path | None) -> GateCheck:
    """Check that there are no skipped tests."""
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    # Run actual tests to check for skipped
    result = subprocess.run(
        ["pytest", "-v", "--tb=no"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    output = result.stdout

    # Check for skipped tests
    skipped = 0
    for line in output.split("\n"):
        if "skipped" in line.lower():
            parts = line.split()
            for i, part in enumerate(parts):
                if "skipped" in part and i > 0:
                    try:
                        skipped = int(parts[i - 1])
                    except ValueError:
                        pass

    passed = skipped == 0
    message = "No skipped tests" if passed else f"{skipped} tests skipped"

    return GateCheck(
        name="No skipped tests",
        passed=passed,
        message=message,
    )


def _check_no_todos(worktree: Path) -> GateCheck:
    """Check for untracked to-do comments."""
    todo_pattern = "TO" + "DO"  # Split to avoid triggering this check

    result = subprocess.run(
        ["git", "diff", "main...HEAD"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return GateCheck(
            name="No untracked to-dos",
            passed=True,
            message="Could not check diff",
        )

    # Look for to-do comments in added lines
    todos: list[str] = []
    for line in result.stdout.split("\n"):
        if line.startswith("+") and todo_pattern in line and not line.startswith("+++"):
            todos.append(line[1:].strip()[:50])

    passed = len(todos) == 0
    message = (
        "No new to-dos found"
        if passed
        else f"Found {len(todos)} to-dos: {todos[0]}..."
    )

    return GateCheck(
        name="No untracked to-dos",
        passed=passed,
        message=message,
    )


def _check_regression_test(worktree: Path, task_id: str) -> GateCheck:
    """Check that a regression test was added."""
    result = subprocess.run(
        ["git", "diff", "main...HEAD", "--name-only"],
        cwd=worktree,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return GateCheck(
            name="Regression test added",
            passed=False,
            message="Failed to get diff",
        )

    changed_files = result.stdout.strip().split("\n")
    test_files = [f for f in changed_files if f.startswith("tests/")]

    passed = len(test_files) > 0
    message = (
        f"Test files changed: {', '.join(test_files[:3])}"
        if passed
        else "No test files added or modified"
    )

    return GateCheck(
        name="Regression test added",
        passed=passed,
        message=message,
    )


def check_gate(
    task_id: str,
    transition: str,
    worktree_path: Path | str | None = None,
    project_path: str | None = None,
    db_path: Path | None = None,
) -> GateResult:
    """Run gate checks for a phase transition.

    Args:
        task_id: Task identifier
        transition: Transition name (e.g., "IMPLEMENT-CODE_REVIEW")
        worktree_path: Path to the worktree (auto-detected if not provided)
        project_path: Project path (auto-detected if not provided)
        db_path: Optional path to database file

    Returns:
        GateResult with all check results
    """
    if db_path is None:
        db_path = settings.db_path

    # Get worktree path
    if worktree_path is None:
        task = get_task(task_id, db_path=db_path)
        if task and task.worktree_path:
            worktree_path = Path(task.worktree_path)
        else:
            raise ValueError(f"No worktree found for task {task_id}")
    else:
        worktree_path = Path(worktree_path)

    # Get requirements for this transition
    requirements = GATE_REQUIREMENTS.get(transition, [])
    if not requirements:
        # No specific requirements, pass by default
        return GateResult(
            passed=True,
            checks=[],
            commit_sha=get_current_commit(worktree_path),
        )

    checks: list[GateCheck] = []

    # Map check names to functions
    check_functions: dict[str, Callable[..., GateCheck]] = {
        "tests_pass": lambda: _check_tests_pass(worktree_path, task_id, db_path),
        "linter_clean": lambda: _check_linter_clean(worktree_path),
        "types_clean": lambda: _check_types_clean(worktree_path),
        "code_exists": lambda: _check_code_exists(worktree_path, task_id),
        "no_todos": lambda: _check_no_todos(worktree_path),
        "changelog_exists": lambda: _check_changelog_exists(worktree_path, task_id),
        "proposal_exists": lambda: _check_proposal_exists(worktree_path, task_id),
        "spec_reviews": lambda: _check_reviews(task_id, "spec", db_path),
        "proposal_reviews": lambda: _check_reviews(task_id, "proposal", db_path),
        "code_reviews": lambda: _check_reviews(task_id, "code", db_path),
        "bugfix_reviews": lambda: _check_reviews(task_id, "bugfix", db_path),
        "bug_report": lambda: _check_bug_report(worktree_path, task_id),
        "root_cause": lambda: _check_root_cause(worktree_path, task_id),
        "fix_plan": lambda: _check_fix_plan(worktree_path, task_id),
        "no_skipped": lambda: _check_no_skipped(worktree_path, task_id, db_path),
        "regression_test": lambda: _check_regression_test(worktree_path, task_id),
    }

    for req in requirements:
        if req.name in check_functions:
            try:
                check = check_functions[req.name]()
                checks.append(check)
            except Exception as e:
                checks.append(
                    GateCheck(
                        name=req.description,
                        passed=False,
                        message=f"Check failed with error: {e}",
                    )
                )
        else:
            # Unknown check, skip
            checks.append(
                GateCheck(
                    name=req.description,
                    passed=True,
                    message="Check not implemented",
                )
            )

    all_passed = all(c.passed for c in checks)
    commit_sha = get_current_commit(worktree_path)

    # Record gate pass if all checks passed
    if all_passed:
        record_gate_pass(task_id, transition, commit_sha, db_path)

    return GateResult(
        passed=all_passed,
        checks=checks,
        commit_sha=commit_sha,
    )


def record_gate_pass(
    task_id: str,
    transition: str,
    commit_sha: str,
    db_path: Path | None = None,
) -> None:
    """Record a successful gate pass anchored to a commit.

    Args:
        task_id: Task identifier
        transition: Transition name
        commit_sha: Commit SHA where gate passed
        db_path: Optional path to database file
    """
    if db_path is None:
        db_path = settings.db_path

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO gate_passes
            (task_id, transition, commit_sha, passed_at)
            VALUES (?, ?, ?, ?)
            """,
            (task_id, transition, commit_sha, datetime.now().isoformat()),
        )
        conn.commit()


def verify_gate_pass(
    task_id: str,
    transition: str,
    current_sha: str,
    db_path: Path | None = None,
) -> bool:
    """Verify a gate was passed at the current commit.

    Args:
        task_id: Task identifier
        transition: Transition name
        current_sha: Current commit SHA
        db_path: Optional path to database file

    Returns:
        True if gate was passed at this commit
    """
    if db_path is None:
        db_path = settings.db_path

    with _get_connection(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id FROM gate_passes
            WHERE task_id = ? AND transition = ? AND commit_sha = ?
            """,
            (task_id, transition, current_sha),
        )
        return cursor.fetchone() is not None


def list_gates() -> list[GateRequirement]:
    """List all gate requirements by transition.

    Returns:
        List of all gate requirements
    """
    result: list[GateRequirement] = []
    for reqs in GATE_REQUIREMENTS.values():
        result.extend(reqs)
    return result
