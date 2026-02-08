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

> **MINIMUM REQUIREMENTS FOR GATE PASSAGE**
>
> Before attempting REPORTED-INVESTIGATED transition, ensure:
> - [ ] At least 3 hypotheses in differential diagnosis (or 2 with justification)
> - [ ] Exactly 1 hypothesis marked CONFIRMED
> - [ ] Each eliminated hypothesis has specific evidence cited
> - [ ] Evidentiary scaffold contains actual code
> - [ ] Captured output from scaffold run is included
> - [ ] Fix plan references specific files and functions

### Reproduction Confirmed

- [ ] Steps reproduced bug

**Observations during reproduction**:
[What did you observe when reproducing?]

### Initial Hypothesis

[What do you believe is causing this bug? Be specific: file, function, line.]

### Differential Diagnosis

> **Requirement**: List at least 3 plausible hypotheses. For trivially simple bugs (e.g., obvious typo),
> 2 hypotheses are acceptable if accompanied by a "### Reduced Hypothesis Justification" section.

| # | Hypothesis | If True, Would See | If False, Would See | Evidence | Status |
|---|------------|-------------------|---------------------|----------|--------|
| 1 | [Hypothesis A] | [Observable X] | [Observable Y] | [What you saw] | [Eliminated/CONFIRMED/Pending] |
| 2 | [Hypothesis B] | [Observable Z] | [Observable W] | [What you saw] | [Eliminated/CONFIRMED/Pending] |
| 3 | [Hypothesis C] | ... | ... | ... | ... |

**Example (well-formed differential diagnosis)**:

| # | Hypothesis | If True, Would See | If False, Would See | Evidence | Status |
|---|------------|-------------------|---------------------|----------|--------|
| 1 | Race condition in cache invalidation | Intermittent failures with concurrent requests | Consistent failure regardless of concurrency | Tested with 100 concurrent requests: failure rate 0% | Eliminated |
| 2 | Null pointer when user has no profile | Crash only for users without profile | Crash for all users | Added logging: crash occurs for users WITH profiles too | Eliminated |
| 3 | Off-by-one in pagination boundary | Fails only on last page | Fails on all pages | Logged page index: fails only when offset = total - 1 | CONFIRMED |

### Reduced Hypothesis Justification

> **Use this section only if you have fewer than 3 hypotheses.**
> Explain why additional hypotheses are not plausible.

[If the bug is trivially simple (e.g., typo, obvious misconfiguration), explain why
additional hypotheses are not genuinely plausible.]

### Evidentiary Scaffold

> **REQUIRED**: You must add diagnostic code, run it, and capture the output.
> Code inspection alone is not sufficient evidence.

**Logging/assertions added**:
```python
# Location: file.py:123
# Purpose: Distinguish between hypothesis 1 and 2
logger.debug(f"State at critical point: {state}")
```

**Test command**:
```bash
[Command to run with scaffold in place - REQUIRED]
```

**Captured output**:
```
[Actual output from scaffold run - REQUIRED, cannot be empty]
```

**Example (well-formed evidentiary scaffold)**:

**Logging/assertions added**:
```python
# Location: src/calm/api/pagination.py:45
# Purpose: Capture pagination state at boundary condition
logger.debug(f"SCAFFOLD: offset={offset}, limit={limit}, total={total}")
logger.debug(f"SCAFFOLD: calculated_end={offset + limit}, is_last_page={offset + limit >= total}")

# Location: src/calm/api/pagination.py:52
# Purpose: Verify which branch is taken
assert offset < total, f"SCAFFOLD: offset ({offset}) >= total ({total})"
logger.debug(f"SCAFFOLD: entering item_slice with indices [{offset}:{offset+limit}]")
```

**Test command**:
```bash
DEBUG=1 pytest tests/test_pagination.py::test_last_page -xvs 2>&1 | grep SCAFFOLD
```

**Captured output**:
```
SCAFFOLD: offset=95, limit=10, total=100
SCAFFOLD: calculated_end=105, is_last_page=True
SCAFFOLD: entering item_slice with indices [95:105]
AssertionError: SCAFFOLD: offset (95) >= total (100) - THIS IS WRONG, should be valid
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
