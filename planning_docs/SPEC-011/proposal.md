# Technical Proposal: SPEC-011 - Strengthen Bug Investigation Protocol

## Overview

This proposal details the implementation of enhanced quality gates for bug investigations, ensuring rigorous differential diagnosis before bugs progress to implementation.

## Technical Approach

### Part 1: Enhanced Differential Diagnosis Requirements

#### Changes to Bug Report Template

**File**: `.claude/templates/bug-report.md`

Add a "Minimum Requirements" section at the top of the Investigation section and enhance the differential diagnosis table with clearer requirements.

**Before** (existing Investigation section):
```markdown
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
```

**After** (enhanced Investigation section):
```markdown
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
| 1 | [Hypothesis A] | [Observable X] | [Observable Y] | [What you saw] | [Eliminated/Confirmed/Pending] |
| 2 | [Hypothesis B] | [Observable Z] | [Observable W] | [What you saw] | [Eliminated/Confirmed/Pending] |
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
```

### Part 2: Mandatory Evidentiary Scaffold

#### Changes to Bug Report Template (continued)

**Before** (existing Evidentiary Scaffold section):
```markdown
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
```

**After** (enhanced Evidentiary Scaffold section):
```markdown
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
# Location: src/clams/api/pagination.py:45
# Purpose: Capture pagination state at boundary condition
logger.debug(f"SCAFFOLD: offset={offset}, limit={limit}, total={total}")
logger.debug(f"SCAFFOLD: calculated_end={offset + limit}, is_last_page={offset + limit >= total}")

# Location: src/clams/api/pagination.py:52
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
```

### Part 3: Gate Check Enhancements

#### New Gate Script

**File**: `.claude/gates/check_bug_investigation.sh`

Create a new gate script that validates bug investigation quality:

```bash
#!/usr/bin/env bash
#
# check_bug_investigation.sh: Verify bug investigation quality
#
# Usage: check_bug_investigation.sh <worktree_path> <task_id>
#
# Validates:
# - At least 3 hypotheses (or 2 with justification)
# - Exactly 1 CONFIRMED hypothesis
# - Evidentiary scaffold contains code
# - Captured output exists and is non-empty
# - Fix plan references specific files
#
# Returns 0 if all checks pass, 1 otherwise.

set -euo pipefail

WORKTREE="${1:-.}"
TASK_ID="${2:-}"

# Try to infer task_id from worktree path if not provided
if [[ -z "$TASK_ID" ]]; then
    TASK_ID=$(basename "$WORKTREE")
fi

BUG_REPORT="$WORKTREE/bug_reports/$TASK_ID.md"

echo "=== Bug Investigation Quality Check ==="
echo "Task: $TASK_ID"
echo "Report: $BUG_REPORT"
echo ""

if [[ ! -f "$BUG_REPORT" ]]; then
    echo "FAIL: Bug report not found at $BUG_REPORT"
    exit 1
fi

failed=0

# 1. Count hypotheses in differential diagnosis table
# Look for table rows: | 1 | ... | ... | ... | ... | Status |
# Match lines starting with | followed by a number
echo "--- Check: Hypothesis count ---"
hypothesis_count=$(grep -E "^\| [0-9]+ \|" "$BUG_REPORT" | wc -l | tr -d ' ')

# Check for reduced hypothesis justification section
has_reduced_justification=0
if grep -q "### Reduced Hypothesis Justification" "$BUG_REPORT"; then
    # Check if the section has actual content (not just the template text)
    justification_content=$(sed -n '/### Reduced Hypothesis Justification/,/^### /p' "$BUG_REPORT" | grep -v "^#" | grep -v "^\[" | grep -v "^>" | grep -v "^$" | head -1)
    if [[ -n "$justification_content" ]]; then
        has_reduced_justification=1
    fi
fi

if [[ "$hypothesis_count" -lt 3 ]]; then
    if [[ "$hypothesis_count" -ge 2 && "$has_reduced_justification" -eq 1 ]]; then
        echo "OK: $hypothesis_count hypotheses (justified trivially simple bug)"
    else
        echo "FAIL: Found $hypothesis_count hypotheses (minimum 3 required, or 2 with justification)"
        failed=1
    fi
else
    echo "OK: $hypothesis_count hypotheses found"
fi

# 2. Check for exactly one CONFIRMED hypothesis
echo ""
echo "--- Check: Confirmed hypothesis ---"
# Look for CONFIRMED (case-insensitive) in the Status column
confirmed_count=$(grep -iE "^\| [0-9]+ \|.*\| *CONFIRMED *\|" "$BUG_REPORT" | wc -l | tr -d ' ')

if [[ "$confirmed_count" -eq 0 ]]; then
    echo "FAIL: No hypothesis marked CONFIRMED"
    failed=1
elif [[ "$confirmed_count" -gt 1 ]]; then
    echo "FAIL: Multiple hypotheses ($confirmed_count) marked CONFIRMED (expected exactly 1)"
    failed=1
else
    echo "OK: Exactly 1 hypothesis marked CONFIRMED"
fi

# 3. Check that eliminated hypotheses have evidence
echo ""
echo "--- Check: Evidence for eliminated hypotheses ---"
# Find rows with "Eliminated" status and check they have non-empty Evidence column
eliminated_without_evidence=0
while IFS= read -r line; do
    # Extract the Evidence column (5th column in 6-column table)
    evidence=$(echo "$line" | awk -F'|' '{print $6}' | xargs)
    if [[ -z "$evidence" || "$evidence" == "[What you saw]" || "$evidence" == "..." ]]; then
        eliminated_without_evidence=$((eliminated_without_evidence + 1))
        echo "  WARNING: Eliminated hypothesis missing evidence"
    fi
done < <(grep -iE "^\| [0-9]+ \|.*\| *Eliminated *\|" "$BUG_REPORT")

if [[ "$eliminated_without_evidence" -gt 0 ]]; then
    echo "FAIL: $eliminated_without_evidence eliminated hypotheses lack evidence"
    failed=1
else
    echo "OK: All eliminated hypotheses have evidence"
fi

# 4. Check evidentiary scaffold has code block
echo ""
echo "--- Check: Evidentiary scaffold code ---"
# Extract the scaffold section and check for code blocks
scaffold_section=$(sed -n '/### Evidentiary Scaffold/,/### Root Cause/p' "$BUG_REPORT" 2>/dev/null || echo "")

if [[ -z "$scaffold_section" ]]; then
    echo "FAIL: Evidentiary Scaffold section not found"
    failed=1
elif ! echo "$scaffold_section" | grep -q '```'; then
    echo "FAIL: Evidentiary scaffold missing code block"
    echo "  The scaffold must contain actual logging/assertion code."
    failed=1
else
    # Check it's not just template placeholder
    if echo "$scaffold_section" | grep -q '\[Command to run\]'; then
        echo "FAIL: Evidentiary scaffold contains only template placeholder"
        failed=1
    else
        echo "OK: Evidentiary scaffold contains code"
    fi
fi

# 5. Check for captured output
echo ""
echo "--- Check: Captured output ---"
# Look for the captured output section with actual content
if ! grep -q "Captured output" "$BUG_REPORT" && ! grep -q "\*\*Captured output\*\*" "$BUG_REPORT"; then
    echo "FAIL: Missing 'Captured output' section"
    failed=1
else
    # Check that there's a code block after "Captured output"
    output_section=$(sed -n '/[Cc]aptured output/,/^###\|^##\|^\*\*[A-Z]/p' "$BUG_REPORT" | head -20)
    if ! echo "$output_section" | grep -q '```'; then
        echo "FAIL: Captured output section missing code block"
        failed=1
    else
        # Check it's not just template placeholder or empty
        output_content=$(echo "$output_section" | sed -n '/```/,/```/p' | grep -v '```' | grep -v '^\[' | head -5)
        if [[ -z "$output_content" ]]; then
            echo "FAIL: Captured output is empty (must contain actual scaffold output)"
            failed=1
        else
            echo "OK: Captured output present"
            echo "  First line: $(echo "$output_content" | head -1 | cut -c1-60)"
        fi
    fi
fi

# 6. Check fix plan has file references
echo ""
echo "--- Check: Fix plan specificity ---"
# Extract fix plan section
fix_section=$(sed -n '/## Fix Plan/,/## Implementation\|## Review\|## Resolution/p' "$BUG_REPORT" 2>/dev/null || echo "")

if [[ -z "$fix_section" ]]; then
    echo "FAIL: Fix Plan section not found"
    failed=1
else
    # Check for file path references (common extensions)
    if echo "$fix_section" | grep -qE '\.(py|ts|js|tsx|jsx|sh|rs|go|java|cpp|c|h)'; then
        echo "OK: Fix plan references specific files"
        # Show the file references
        echo "  Files mentioned:"
        echo "$fix_section" | grep -oE '[a-zA-Z0-9_/.-]+\.(py|ts|js|tsx|jsx|sh|rs|go|java|cpp|c|h)' | sort -u | head -5 | sed 's/^/    /'
    else
        echo "FAIL: Fix plan missing specific file references"
        echo "  The fix plan must reference specific files to change."
        failed=1
    fi
fi

# 7. Cross-reference: Root cause matches confirmed hypothesis
echo ""
echo "--- Check: Root cause consistency ---"
root_cause_section=$(sed -n '/### Root Cause/,/^##\|^###/p' "$BUG_REPORT" 2>/dev/null || echo "")

if [[ -z "$root_cause_section" ]]; then
    echo "FAIL: Root Cause section not found"
    failed=1
else
    # Check that root cause section has content beyond template
    root_cause_content=$(echo "$root_cause_section" | grep -v "^#" | grep -v "^\*\*" | grep -v "^-" | grep -v "^$" | grep -v "\[" | head -3)
    if [[ -z "$root_cause_content" ]]; then
        echo "FAIL: Root Cause section appears to be template only"
        failed=1
    else
        echo "OK: Root Cause section has content"
    fi
fi

echo ""
echo "=========================================="
if [[ $failed -eq 0 ]]; then
    echo "BUG INVESTIGATION QUALITY: PASS"
    exit 0
else
    echo "BUG INVESTIGATION QUALITY: FAIL"
    echo ""
    echo "Fix the issues above before transitioning."
    echo "See .claude/roles/bug-investigator.md for guidance."
    exit 1
fi
```

#### Modifications to claws-gate Script

**File**: `.claude/bin/claws-gate`

Update the REPORTED-INVESTIGATED case to call the new quality check script:

**Before** (lines 366-400):
```bash
        REPORTED-INVESTIGATED)
            echo ""
            # Check bug report exists
            if ! check_file_exists "$worktree/bug_reports/$task_id.md" "Bug report exists"; then
                failed=1
            fi
            echo ""
            # Check required sections are filled
            echo "--- Gate: Bug report sections complete ---"
            local bug_report="$worktree/bug_reports/$task_id.md"
            local missing_sections=()

            if ! grep -q "## Reproduction Steps" "$bug_report" 2>/dev/null; then
                missing_sections+=("Reproduction Steps")
            fi
            if ! grep -q "### Root Cause" "$bug_report" 2>/dev/null; then
                missing_sections+=("Root Cause")
            fi
            if ! grep -q "## Fix Plan" "$bug_report" 2>/dev/null; then
                missing_sections+=("Fix Plan")
            fi

            if [[ ${#missing_sections[@]} -gt 0 ]]; then
                echo "x Bug report sections: FAIL"
                echo "  Missing sections:"
                for section in "${missing_sections[@]}"; do
                    echo "    - $section"
                done
                failed=1
            else
                echo "v Bug report sections: PASS"
            fi
            ;;
```

**After**:
```bash
        REPORTED-INVESTIGATED)
            echo ""
            # Check bug report exists
            if ! check_file_exists "$worktree/bug_reports/$task_id.md" "Bug report exists"; then
                failed=1
            fi
            echo ""
            # Check required sections are filled (basic structure)
            echo "--- Gate: Bug report sections complete ---"
            local bug_report="$worktree/bug_reports/$task_id.md"
            local missing_sections=()

            if ! grep -q "## Reproduction Steps" "$bug_report" 2>/dev/null; then
                missing_sections+=("Reproduction Steps")
            fi
            if ! grep -q "### Root Cause" "$bug_report" 2>/dev/null; then
                missing_sections+=("Root Cause")
            fi
            if ! grep -q "## Fix Plan" "$bug_report" 2>/dev/null; then
                missing_sections+=("Fix Plan")
            fi

            if [[ ${#missing_sections[@]} -gt 0 ]]; then
                echo "x Bug report sections: FAIL"
                echo "  Missing sections:"
                for section in "${missing_sections[@]}"; do
                    echo "    - $section"
                done
                failed=1
            else
                echo "v Bug report sections: PASS"
            fi

            # Run investigation quality checks (new in SPEC-011)
            echo ""
            if ! run_gate "Investigation quality" "check_bug_investigation.sh" "$worktree"; then
                failed=1
            fi
            ;;
```

### Part 4: Bug Investigator Role Guidance Updates

**File**: `.claude/roles/bug-investigator.md`

Add sections for minimum requirements, evidence thresholds, and expanded anti-patterns.

**Additions after existing "Differential Diagnosis (CRITICAL)" section:**

```markdown
### Minimum Requirements (MANDATORY)

These are enforced by automated gate checks:

1. **3 hypotheses minimum**: You must list at least 3 plausible hypotheses
   - Exception: For trivially simple bugs (obvious typo, simple misconfiguration), 2 hypotheses
     are acceptable IF you document why additional hypotheses are not plausible in a
     "### Reduced Hypothesis Justification" section

2. **Exactly 1 CONFIRMED**: One and only one hypothesis must be marked CONFIRMED
   - All others must be marked Eliminated with evidence

3. **Evidence for eliminations**: Each eliminated hypothesis must cite specific evidence
   - "Unlikely" or "improbable" is NOT acceptable

4. **Evidentiary scaffold required**: You must add diagnostic code and run it
   - Code inspection alone is insufficient

5. **Captured output required**: Include actual output from running your scaffold
   - The gate checks that this section is not empty

### Evidence Threshold Definitions

**Evidence sufficient to ELIMINATE a hypothesis:**

- **Log output**: Explicit log/debug output showing the hypothesized condition does not occur
  - Example: "Logged user.profile: value is not None, so null profile hypothesis eliminated"

- **Assertion failure**: Code assertion proving the hypothesis path is not taken
  - Example: "Added assert at line 45, never triggered in 100 runs"

- **Code path analysis**: Demonstrable proof via instrumentation that the hypothesized code path
  is never executed
  - Example: "Added counter for each branch, path B never incremented"

- **State inspection**: Debugger/print output showing relevant state contradicts the hypothesis
  - Example: "Dumped cache state: all entries present, cache miss hypothesis eliminated"

**Evidence sufficient to CONFIRM a hypothesis:**

- **Reproduction via artificial injection**: Bug reproduced by artificially creating the
  hypothesized condition
  - Example: "Manually set offset = total - 1, bug reproduced consistently"

- **Fix verification**: Bug disappears when the hypothesized cause is corrected
  - Example: "Changed >= to >, bug no longer reproduces"

- **Elimination proof**: All other hypotheses eliminated AND positive evidence supports this
  hypothesis
  - Example: "3 alternatives eliminated, logs show this exact path triggers crash"

- **Root cause trace**: Complete causal chain from trigger to symptom documented with evidence
  at each step
  - Example: "Input X -> function Y (logged) -> state Z (observed) -> crash (stack trace)"

**NOT acceptable as evidence:**

- "Unlikely" or "improbable" without supporting data
- "Code inspection suggests" without runtime verification
- "Should work" or "looks correct" assertions
- Reasoning without observed behavior
- "I tried X and it seemed to work" without systematic verification
```

**Expanded Anti-Patterns section:**

```markdown
## Anti-Patterns (DO NOT DO)

### Investigation Anti-Patterns

- **Guessing**: "It's probably X" without evidence
- **Single hypothesis**: Only considering one cause (gate requires 3+)
- **Premature fixing**: Changing code before proving root cause
- **Weak evidence**: "It worked after I changed X" (correlation != causation)
- **Scope creep**: Finding other bugs and fixing those too
- **Skipping reproduction**: Investigating without first reproducing
- **Code-reading only**: Drawing conclusions from code inspection without runtime verification

### Evidence Anti-Patterns

- **Vague elimination**: "Hypothesis A is unlikely because the code looks correct"
  - Fix: Run with logging to prove the hypothesized condition does not occur

- **Confirmation bias**: Only looking for evidence that supports your first guess
  - Fix: Actively try to prove your initial hypothesis WRONG

- **Missing scaffold**: "I looked at the code and found the bug"
  - Fix: Add logging/assertions, run them, capture the output

- **Empty output**: Scaffold section exists but captured output is missing
  - Fix: Actually run the scaffold and paste the real output

- **Symptom vs root cause**: "The bug is that function X returns wrong value"
  - Fix: WHY does it return wrong value? That's the root cause.

### Fix Plan Anti-Patterns

- **Vague fix**: "Fix the bug in the pagination code"
  - Fix: "In src/clams/api/pagination.py:52, change `offset >= total` to `offset > total`"

- **Missing regression test**: Fix plan doesn't specify what the test should verify
  - Fix: Include test outline with setup, action, and assertion

- **Over-engineering**: Proposing major refactors when a surgical fix suffices
  - Fix: Minimal change that addresses proven root cause

### Self-Review Checklist

Before running the gate check, verify:

- [ ] I can explain the root cause in one sentence
- [ ] I have evidence (not just reasoning) for each eliminated hypothesis
- [ ] My evidentiary scaffold code is shown in the bug report
- [ ] I ran the scaffold and included the actual output
- [ ] My fix plan names specific files and functions
- [ ] The fix directly addresses the proven root cause (not symptoms)
- [ ] I've documented how to verify the fix works
```

## File Summary

| File | Action | Description |
|------|--------|-------------|
| `.claude/gates/check_bug_investigation.sh` | Create | New quality gate script for bug investigations |
| `.claude/bin/claws-gate` | Modify | Add call to new investigation quality check |
| `.claude/templates/bug-report.md` | Modify | Add requirements callout, examples, checklist |
| `.claude/roles/bug-investigator.md` | Modify | Add minimum requirements, evidence thresholds, anti-patterns |

## Testing Strategy

### Unit Tests for Gate Script

Create `tests/test_bug_investigation_gate.py`:

```python
"""Tests for check_bug_investigation.sh gate script."""

import subprocess
import tempfile
import os
from pathlib import Path

import pytest


@pytest.fixture
def worktree_dir():
    """Create a temporary worktree-like directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bug_reports = Path(tmpdir) / "bug_reports"
        bug_reports.mkdir()
        yield tmpdir


def run_gate(worktree: str, task_id: str) -> tuple[int, str]:
    """Run the gate check and return (exit_code, output)."""
    script_path = Path(__file__).parent.parent / ".claude" / "gates" / "check_bug_investigation.sh"
    result = subprocess.run(
        [str(script_path), worktree, task_id],
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout + result.stderr


class TestHypothesisCount:
    """Test hypothesis counting logic."""

    def test_rejects_zero_hypotheses(self, worktree_dir):
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

    def test_rejects_two_hypotheses_without_justification(self, worktree_dir):
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

    def test_accepts_two_hypotheses_with_justification(self, worktree_dir):
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

    def test_accepts_three_hypotheses(self, worktree_dir):
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

    def test_rejects_no_confirmed(self, worktree_dir):
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

    def test_rejects_multiple_confirmed(self, worktree_dir):
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

    def test_rejects_missing_scaffold_code(self, worktree_dir):
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

    def test_rejects_empty_captured_output(self, worktree_dir):
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

    def test_rejects_missing_file_references(self, worktree_dir):
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

    def test_accepts_specific_file_reference(self, worktree_dir):
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
```

### Integration Test

Add to existing test suite or create `tests/test_bug_workflow.py`:

```python
"""Integration tests for bug workflow with enhanced investigation gates."""

import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def claws_repo(tmp_path):
    """Set up a minimal CLAWS repository for testing."""
    # Initialize git
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    # Create .claude structure
    claude_dir = tmp_path / ".claude"
    claude_dir.mkdir()
    (claude_dir / "bin").mkdir()
    (claude_dir / "gates").mkdir()

    # Copy gate scripts (in real test, would copy from fixtures)
    # ... setup code ...

    yield tmp_path


@pytest.mark.integration
def test_full_bug_investigation_workflow(claws_repo):
    """Test that a well-formed bug report passes all gates."""
    # This would be a full integration test
    # Create bug report, run gate, verify pass
    pass
```

### Manual Testing Checklist

1. **Gate accepts well-formed report**:
   - Create bug report with 3 hypotheses, 1 CONFIRMED, scaffold with code and output
   - Run `.claude/bin/claws-gate check BUG-XXX REPORTED-INVESTIGATED`
   - Verify: PASS

2. **Gate rejects insufficient hypotheses**:
   - Create bug report with only 2 hypotheses, no justification
   - Run gate check
   - Verify: FAIL with clear message about hypothesis count

3. **Gate accepts 2 hypotheses with justification**:
   - Add "### Reduced Hypothesis Justification" section with explanation
   - Run gate check
   - Verify: PASS with informational message

4. **Gate rejects missing scaffold output**:
   - Create report with code but empty captured output
   - Run gate check
   - Verify: FAIL with message about missing output

5. **Gate rejects vague fix plan**:
   - Create report with "fix the bug" fix plan
   - Run gate check
   - Verify: FAIL with message about missing file references

## Implementation Order

1. Create `.claude/gates/check_bug_investigation.sh` (new file)
2. Update `.claude/bin/claws-gate` (add call to new script)
3. Update `.claude/templates/bug-report.md` (add requirements, examples)
4. Update `.claude/roles/bug-investigator.md` (add guidance sections)
5. Create tests and verify
6. Run full gate check on a sample bug report

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Regex parsing fragile with markdown variations | Use flexible patterns, test with various formats |
| Gate too strict for simple bugs | Allow 2-hypothesis exception with justification |
| Investigators game the system with low-quality hypotheses | Reviewers still verify quality; gate checks structure only |
| Performance impact from additional parsing | Script is simple text processing, < 1 second |

## Success Metrics

After implementation:
- Zero investigations should pass gate without meeting minimum hypothesis count
- All investigations should have captured scaffold output (not empty)
- Fix plans should consistently reference specific files
- Reviewer feedback should focus on substantive quality, not missing structure
