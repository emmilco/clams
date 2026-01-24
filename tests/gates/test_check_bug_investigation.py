"""Tests for check_bug_investigation.sh gate script.

This test verifies SPEC-011 implementation: enhanced bug investigation quality gates.
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest


def run_gate(worktree: str, task_id: str) -> tuple[int, str]:
    """Run the gate check and return (exit_code, output)."""
    script_path = Path(__file__).parent.parent.parent / ".claude" / "gates" / "check_bug_investigation.sh"

    # Ensure we have an environment that won't interfere
    env = os.environ.copy()

    result = subprocess.run(
        [str(script_path), worktree, task_id],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )
    return result.returncode, result.stdout + result.stderr


@pytest.fixture
def worktree_dir() -> str:
    """Create a temporary worktree-like directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bug_reports = Path(tmpdir) / "bug_reports"
        bug_reports.mkdir()
        # Initialize a minimal git repo for scaffold remnant checks
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"],
            cwd=tmpdir,
            check=True,
            capture_output=True,
        )
        yield tmpdir


class TestHypothesisCount:
    """Test hypothesis counting logic."""

    def test_rejects_zero_hypotheses(self, worktree_dir: str) -> None:
        """Gate rejects bug report with no hypotheses."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
(no table)
### Root Cause
Something broke
## Fix Plan
Fix it
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "hypotheses" in output.lower()

    def test_rejects_two_hypotheses_without_justification(self, worktree_dir: str) -> None:
        """Gate rejects 2 hypotheses without justification section."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race condition | See A | See B | Saw B | Eliminated |
| 2 | Null pointer | See C | See D | Saw C | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
debug
```
### Root Cause
Null pointer issue
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "2" in output and "hypotheses" in output.lower()

    def test_accepts_two_hypotheses_with_justification(self, worktree_dir: str) -> None:
        """Gate accepts 2 hypotheses when justification is provided."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Typo in config | See A | See B | Saw B | Eliminated |
| 2 | Wrong default | See C | See D | Saw C | CONFIRMED |
### Reduced Hypothesis Justification
This is a trivially simple configuration typo. The only two possibilities are
a typo in the config file or a wrong default value. No other causes are plausible.
### Evidentiary Scaffold
```python
print(config)
```
**Captured output**:
```
{'key': 'wrong_value'}
```
### Root Cause
Wrong default value in config
## Fix Plan
Fix src/config.py default
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 0

    def test_accepts_three_hypotheses(self, worktree_dir: str) -> None:
        """Gate accepts 3+ hypotheses."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race condition | See A | See B | Saw B | Eliminated |
| 2 | Cache miss | See C | See D | Saw D | Eliminated |
| 3 | Null pointer | See E | See F | Saw E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
State: null
```
### Root Cause
Null pointer when profile is missing
## Fix Plan
Fix src/user.py:handle_profile()
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 0


class TestConfirmedHypothesis:
    """Test CONFIRMED hypothesis validation."""

    def test_rejects_no_confirmed(self, worktree_dir: str) -> None:
        """Gate rejects when no hypothesis is CONFIRMED."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race condition | See A | See B | Saw B | Eliminated |
| 2 | Cache miss | See C | See D | Saw D | Eliminated |
| 3 | Null pointer | See E | See F | Saw E | Pending |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
output
```
### Root Cause
Not sure yet
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "CONFIRMED" in output

    def test_rejects_multiple_confirmed(self, worktree_dir: str) -> None:
        """Gate rejects when multiple hypotheses are CONFIRMED."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race condition | See A | See B | Saw A | CONFIRMED |
| 2 | Cache miss | See C | See D | Saw D | Eliminated |
| 3 | Null pointer | See E | See F | Saw E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
output
```
### Root Cause
Two things
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "Multiple" in output or "2" in output


class TestEvidentiaryScaffold:
    """Test evidentiary scaffold validation."""

    def test_rejects_missing_scaffold_code(self, worktree_dir: str) -> None:
        """Gate rejects when scaffold has no code block."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race | A | B | B | Eliminated |
| 2 | Cache | C | D | D | Eliminated |
| 3 | Null | E | F | E | CONFIRMED |
### Evidentiary Scaffold
I looked at the code and found the bug.
### Root Cause
Null pointer
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "scaffold" in output.lower()

    def test_rejects_empty_captured_output(self, worktree_dir: str) -> None:
        """Gate rejects when captured output is empty."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race | A | B | B | Eliminated |
| 2 | Cache | C | D | D | Eliminated |
| 3 | Null | E | F | E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
```
### Root Cause
Null pointer
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "empty" in output.lower() or "output" in output.lower()


class TestFixPlan:
    """Test fix plan validation."""

    def test_rejects_missing_file_references(self, worktree_dir: str) -> None:
        """Gate rejects when fix plan has no file references."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race | A | B | B | Eliminated |
| 2 | Cache | C | D | D | Eliminated |
| 3 | Null | E | F | E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
debug output
```
### Root Cause
Null pointer
## Fix Plan
Fix the bug in the pagination code.
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "file" in output.lower()

    def test_accepts_specific_file_reference(self, worktree_dir: str) -> None:
        """Gate accepts when fix plan references specific files."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race | A | B | B | Eliminated |
| 2 | Cache | C | D | D | Eliminated |
| 3 | Null | E | F | E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
debug output here
```
### Root Cause
Null pointer when profile is None
## Fix Plan
1. In `src/clams/api/users.py:get_profile()`, add null check
2. Add test in `tests/test_users.py`
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 0


class TestRootCauseSection:
    """Test root cause section validation."""

    def test_rejects_missing_root_cause_section(self, worktree_dir: str) -> None:
        """Gate rejects when root cause section is missing."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001
## Reproduction Steps
1. Do X
### Differential Diagnosis
| # | Hypothesis | If True | If False | Evidence | Status |
|---|------------|---------|----------|----------|--------|
| 1 | Race | A | B | B | Eliminated |
| 2 | Cache | C | D | D | Eliminated |
| 3 | Null | E | F | E | CONFIRMED |
### Evidentiary Scaffold
```python
print("debug")
```
**Captured output**:
```
output
```
## Fix Plan
Fix src/foo.py
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 1
        assert "Root Cause" in output


class TestMissingBugReport:
    """Test handling of missing bug report file."""

    def test_rejects_missing_bug_report(self, worktree_dir: str) -> None:
        """Gate rejects when bug report file does not exist."""
        code, output = run_gate(worktree_dir, "BUG-NONEXISTENT")
        assert code == 1
        assert "not found" in output.lower()


class TestWellFormedReport:
    """Test acceptance of well-formed bug reports."""

    def test_accepts_well_formed_report(self, worktree_dir: str) -> None:
        """Gate accepts a complete, well-formed bug report."""
        report = Path(worktree_dir) / "bug_reports" / "BUG-001.md"
        report.write_text("""# BUG-001: Test Bug

## Reported

- **First noticed on commit**: abc123
- **Reported by**: orchestrator
- **Reported at**: 2024-01-15
- **Severity**: high

## Reproduction Steps

1. Start the server
2. Make a request
3. Observe the crash

**Expected**: Server responds with 200
**Actual**: Server crashes with null pointer

---

## Investigation (filled by Bug Investigator)

### Reproduction Confirmed

- [x] Steps reproduced bug

**Observations during reproduction**:
Server crashes when user.profile is None

### Initial Hypothesis

The bug is likely in src/clams/api/users.py:get_profile() where we don't check for None.

### Differential Diagnosis

| # | Hypothesis | If True, Would See | If False, Would See | Evidence | Status |
|---|------------|-------------------|---------------------|----------|--------|
| 1 | Race condition in cache invalidation | Intermittent failures | Consistent failure | Tested 100 times, always fails | Eliminated |
| 2 | Null pointer when user has no profile | Crash only without profile | Crash for all users | Logged: crash only when profile=None | CONFIRMED |
| 3 | Database connection timeout | Timeout error in logs | No timeout error | No timeout in logs | Eliminated |

### Evidentiary Scaffold

```python
# Location: src/clams/api/users.py:45
# Purpose: Log profile state before access
logger.debug(f"SCAFFOLD: profile={user.profile}")

# Location: src/clams/api/users.py:48
# Purpose: Check which branch is taken
logger.debug(f"SCAFFOLD: entering get_profile, has_profile={user.profile is not None}")
```

**Test command**:
```bash
DEBUG=1 pytest tests/test_users.py::test_get_profile -xvs 2>&1 | grep SCAFFOLD
```

**Captured output**:
```
SCAFFOLD: profile=None
SCAFFOLD: entering get_profile, has_profile=False
Traceback: NullPointerException at users.py:50
```

### Root Cause (Proven)

**The bug is caused by**: Missing null check in get_profile() when user.profile is None

**Evidence**: The scaffold logs show profile=None immediately before the crash

**Why alternatives were eliminated**:
- Hypothesis 1 eliminated because: 100/100 runs crashed consistently, not intermittent
- Hypothesis 3 eliminated because: No timeout errors in logs, crash is immediate

---

## Fix Plan

### Code Changes

1. **File**: `src/clams/api/users.py`
   **Function**: `get_profile`
   **Change**: Add null check before accessing profile attributes
   **Rationale**: Prevents the NullPointerException when profile is None

### Regression Test

**Test file**: `tests/test_bug_001_regression.py`

**Test should**:
1. Create a user without a profile
2. Call get_profile()
3. Verify no exception is raised and proper fallback is returned

**Test outline**:
```python
def test_bug_001_regression():
    user = User(profile=None)
    result = get_profile(user)
    assert result is not None  # Should return fallback, not crash
```
""")
        code, output = run_gate(worktree_dir, "BUG-001")
        assert code == 0
        assert "PASS" in output
