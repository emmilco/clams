#!/usr/bin/env bash
#
# check_bug_investigation.sh: Verify bug investigation quality
#
# Usage: check_bug_investigation.sh <worktree_path> [task_id]
#
# Validates:
# - At least 3 hypotheses (or 2 with justification)
# - Exactly 1 CONFIRMED hypothesis
# - Each eliminated hypothesis has specific evidence cited
# - Evidentiary scaffold contains actual code
# - Captured output from scaffold run is included
# - Fix plan references specific files
# - Scaffold remnant warning (non-blocking)
#
# Exit codes:
#   0 - All checks pass
#   1 - One or more checks fail

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
# Use a subshell to prevent set -e from exiting on grep returning 1 (no matches)
hypothesis_count=0
if grep -qE "^\| [0-9]+ \|" "$BUG_REPORT" 2>/dev/null; then
    hypothesis_count=$(grep -cE "^\| [0-9]+ \|" "$BUG_REPORT")
fi

# Check for reduced hypothesis justification section
has_reduced_justification=0
if grep -q "### Reduced Hypothesis Justification" "$BUG_REPORT"; then
    # Check if the section has actual content (not just the template text)
    justification_content=$(sed -n '/### Reduced Hypothesis Justification/,/^### /p' "$BUG_REPORT" | grep -v "^#" | grep -v "^\[" | grep -v "^>" | grep -v "^$" | head -1 || true)
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
confirmed_count=0
if grep -qiE "^\| [0-9]+ \|.*\| *CONFIRMED *\|" "$BUG_REPORT" 2>/dev/null; then
    confirmed_count=$(grep -ciE "^\| [0-9]+ \|.*\| *CONFIRMED *\|" "$BUG_REPORT")
fi

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
done < <(grep -iE "^\| [0-9]+ \|.*\| *Eliminated *\|" "$BUG_REPORT" || true)

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

# 7. Scaffold remnant warning (non-blocking per SPEC-011)
echo ""
echo "--- Check: Scaffold remnants (warning only) ---"
# Check for common scaffold patterns in uncommitted changes
scaffold_patterns='logger\.debug|print\("DEBUG|# SCAFFOLD|# DEBUG|console\.log\("DEBUG'

if cd "$WORKTREE" && git diff HEAD 2>/dev/null | grep -qE "$scaffold_patterns"; then
    echo "WARNING: Possible scaffold remnants detected in uncommitted changes"
    echo "  Review and clean up diagnostic code before proceeding to implementation."
    echo "  Common patterns found:"
    git diff HEAD 2>/dev/null | grep -E "$scaffold_patterns" | head -5 | sed 's/^/    /'
    echo ""
    echo "  (This is a WARNING only - gate will still pass)"
else
    echo "OK: No obvious scaffold remnants in uncommitted changes"
fi

# 8. Cross-reference: Root cause section has content
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
