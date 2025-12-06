# BUG-XXX: [Title]

## Reported

- **First noticed on commit**: [SHA]
- **Reported by**: [orchestrator/worker/human]
- **Reported at**: [timestamp]
- **Severity**: [critical/high/medium/low]

## Reproduction Steps

1. [Step one]
2. [Step two]
3. [Step three]

**Expected**: [What should happen]
**Actual**: [What actually happens]

---

## Investigation (filled by Bug Investigator)

### Reproduction Confirmed

- [ ] Steps reproduced bug

**Observations during reproduction**:
[What did you observe when reproducing?]

### Initial Hypothesis

[What do you believe is causing this bug? Be specific: file, function, line.]

### Differential Diagnosis

| # | Hypothesis | If True, Would See | If False, Would See | Evidence | Status |
|---|------------|-------------------|---------------------|----------|--------|
| 1 | [Hypothesis A] | [Observable X] | [Observable Y] | [What you saw] | [Eliminated/Confirmed/Pending] |
| 2 | [Hypothesis B] | [Observable Z] | [Observable W] | [What you saw] | [Eliminated/Confirmed/Pending] |
| 3 | [Hypothesis C] | ... | ... | ... | ... |

### Evidentiary Scaffold

**Logging/assertions added**:
```python
# Location: file.py:123
# Purpose: Distinguish between hypothesis 1 and 2
logger.debug(f"State at critical point: {state}")
```

**Test command**:
```bash
[Command to run with scaffold in place]
```

**Captured output**:
```
[Actual output from scaffold run]
```

### Root Cause (Proven)

**The bug is caused by**: [Specific root cause]

**Evidence**: [What proves this is the cause]

**Why alternatives were eliminated**:
- Hypothesis 1 eliminated because: [reason with evidence]
- Hypothesis 3 eliminated because: [reason with evidence]

---

## Fix Plan

### Code Changes

1. **File**: `src/path/to/file.py`
   **Function**: `function_name`
   **Change**: [Describe the specific change]
   **Rationale**: [Why this fixes the root cause]

2. [Additional changes if needed]

### Regression Test

**Test file**: `tests/test_bug_XXX.py`

**Test should**:
1. Set up the exact conditions that trigger the bug
2. Verify the buggy behavior no longer occurs
3. Fail if the bug regresses

**Test outline**:
```python
def test_bug_XXX_regression():
    # Setup: create conditions that triggered the bug
    # ...

    # Action: perform the operation that was buggy
    # ...

    # Assert: verify correct behavior (would have failed before fix)
    assert result == expected
```

### Verification

After implementing the fix:
```bash
# Run specific test
pytest tests/test_bug_XXX.py -xvs

# Run full test suite
pytest -xvs
```

---

## Implementation (filled by Implementer)

- **Implemented by**: [worker ID]
- **Commit**: [SHA]
- **Regression test file**: [path]

### Changes Made

[Brief summary of actual changes vs plan]

---

## Review (filled by Reviewers)

| Review # | Reviewer | Result | Date |
|----------|----------|--------|------|
| 1 | [worker ID] | [approved/changes_requested] | [date] |
| 2 | [worker ID] | [approved/changes_requested] | [date] |

---

## Resolution

- **Fixed in commit**: [SHA on main]
- **Verified by**: [worker ID]
- **Closed at**: [timestamp]
