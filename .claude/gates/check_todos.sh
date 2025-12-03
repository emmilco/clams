#!/usr/bin/env bash
#
# check_todos.sh: Find untracked TODOs
#
# Usage: check_todos.sh [worktree_path] [task_id]
#
# Finds TODO comments that aren't linked to tracked tasks.
# TODOs should reference a task ID like: TODO(TASK-123): description
#
# Returns 0 if all TODOs are tracked, 1 if untracked TODOs found.

set -euo pipefail

WORKTREE="${1:-.}"
TASK_ID="${2:-}"
cd "$WORKTREE"

echo "=== Checking for Untracked TODOs ==="
echo "Directory: $WORKTREE"
echo ""

# Find all TODO comments
all_todos=$(grep -rn "TODO" . \
    --include="*.py" \
    --include="*.js" \
    --include="*.ts" \
    --include="*.tsx" \
    --include="*.jsx" \
    --include="*.go" \
    --include="*.rs" \
    --include="*.java" \
    --include="*.rb" \
    --include="*.sh" \
    2>/dev/null | grep -v ".git" | grep -v "node_modules" | grep -v "__pycache__" || true)

if [[ -z "$all_todos" ]]; then
    echo "No TODO comments found"
    echo ""
    echo "PASS: No untracked TODOs"
    exit 0
fi

echo "Found TODO comments:"
echo "$all_todos"
echo ""

# Check for TODOs that reference task IDs
# Pattern: TODO(TASK-XXX) or TODO: TASK-XXX or TODO [TASK-XXX]
tracked=$(echo "$all_todos" | grep -E "TODO.*[A-Z]+-[0-9]+" || true)
untracked=$(echo "$all_todos" | grep -vE "TODO.*[A-Z]+-[0-9]+" || true)

if [[ -n "$tracked" ]]; then
    echo "Tracked TODOs (have task reference):"
    echo "$tracked"
    echo ""
fi

if [[ -n "$untracked" ]]; then
    echo "UNTRACKED TODOs (need task reference):"
    echo "$untracked"
    echo ""
    untracked_count=$(echo "$untracked" | wc -l | tr -d ' ')
    echo "FAIL: $untracked_count untracked TODO(s) found"
    echo ""
    echo "Each TODO should reference a task ID, e.g.:"
    echo "  # TODO(TASK-123): Implement error handling"
    echo "  // TODO: TASK-456 - Add caching"
    exit 1
else
    echo "PASS: All TODOs are tracked"
    exit 0
fi
