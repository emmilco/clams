#!/usr/bin/env bash
#
# check_frontend.sh: Validate frontend (calm-visualizer) changes
#
# Usage: check_frontend.sh <worktree_path> [task_id]
#
# This script handles frontend subdirectories that may or may not have
# npm tooling configured. It:
#   1. Checks if the directory exists
#   2. If package.json exists, runs configured lint/typecheck scripts
#   3. If no package.json, skips gracefully (returns 0)
#
# Exit codes:
#   0 - All checks pass (or no frontend directory / no npm project)
#   1 - Lint or type check failed
#   2 - npm not available

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

# Read frontend_dirs from project.json or use default
PROJECT_CONFIG="$CLAUDE_DIR/project.json"
FRONTEND_DIRS="calm-visualizer/"

if [[ -f "$PROJECT_CONFIG" ]] && command -v jq &>/dev/null; then
    DIRS=$(jq -r '.frontend_dirs[]? // empty' "$PROJECT_CONFIG" 2>/dev/null | tr '\n' ' ')
    if [[ -n "$DIRS" ]]; then
        FRONTEND_DIRS="$DIRS"
    fi
fi

echo "=== Running Frontend Checks ==="
echo "Worktree: $WORKTREE"
echo "Frontend directories: $FRONTEND_DIRS"
echo ""

FAILED=0
CHECKED=0

for dir in $FRONTEND_DIRS; do
    FRONTEND_PATH="$WORKTREE/$dir"

    if [[ ! -d "$FRONTEND_PATH" ]]; then
        echo "Skip: $dir (directory not found)"
        continue
    fi

    echo "--- Checking: $dir ---"
    cd "$FRONTEND_PATH"

    # Check if this is an npm project
    if [[ ! -f "package.json" ]]; then
        echo "Skip: No package.json (not an npm project)"
        echo ""
        continue
    fi

    CHECKED=$((CHECKED + 1))

    # Ensure npm is available
    if ! command -v npm &> /dev/null; then
        echo "Error: npm not found" >&2
        echo "Install Node.js and npm to run frontend checks" >&2
        exit 2
    fi

    # Install dependencies if needed
    if [[ ! -d "node_modules" ]]; then
        echo "Installing dependencies..."
        if ! npm install --quiet 2>/dev/null; then
            npm install || { echo "npm install failed"; exit 1; }
        fi
        echo ""
    fi

    # Run lint if configured
    if grep -q '"lint"' package.json 2>/dev/null; then
        echo "Running: npm run lint"
        if ! npm run lint 2>&1; then
            echo "Lint check FAILED"
            FAILED=1
        else
            echo "Lint check PASSED"
        fi
        echo ""
    else
        echo "Skip lint: no 'lint' script in package.json"
    fi

    # Run typecheck if configured
    if grep -q '"typecheck"' package.json 2>/dev/null; then
        echo "Running: npm run typecheck"
        if ! npm run typecheck 2>&1; then
            echo "Type check FAILED"
            FAILED=1
        else
            echo "Type check PASSED"
        fi
        echo ""
    else
        echo "Skip typecheck: no 'typecheck' script in package.json"
    fi

    cd - > /dev/null
done

echo ""
echo "========================================="
if [[ $CHECKED -eq 0 ]]; then
    echo "SKIP: No frontend npm projects found"
    exit 0
elif [[ $FAILED -eq 0 ]]; then
    echo "PASS: Frontend checks clean ($CHECKED projects checked)"
    exit 0
else
    echo "FAIL: Frontend checks failed"
    exit 1
fi
