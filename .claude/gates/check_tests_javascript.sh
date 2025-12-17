#!/usr/bin/env bash
#
# check_tests_javascript.sh: Run JavaScript/TypeScript test suite
#
# Usage: check_tests_javascript.sh <worktree_path> [task_id]
#
# Supports: npm test, jest, vitest, mocha
#
# Exit codes:
#   0 - All tests passed
#   1 - Tests failed
#   2 - Tool not available (skipped)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/claws-common.sh" ]]; then
    source "$BIN_DIR/claws-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Running JavaScript/TypeScript Tests ==="
echo "Directory: $WORKTREE"
echo ""

# Verify this is a JavaScript/TypeScript project
if [[ ! -f "package.json" ]]; then
    echo "Error: Not a JavaScript project (no package.json)" >&2
    exit 2
fi

# Install dependencies if node_modules doesn't exist
if [[ ! -d "node_modules" ]]; then
    echo "Installing dependencies..."
    if command -v npm &> /dev/null; then
        npm install --quiet 2>/dev/null || npm install
    else
        echo "Error: npm not found" >&2
        exit 2
    fi
    echo ""
fi

# Detect test runner
if grep -q '"vitest"' package.json 2>/dev/null || [[ -f "vitest.config.ts" ]] || [[ -f "vitest.config.js" ]]; then
    echo "Detected: Vitest"
    if npx vitest run 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
elif grep -q '"jest"' package.json 2>/dev/null || [[ -f "jest.config.js" ]] || [[ -f "jest.config.ts" ]]; then
    echo "Detected: Jest"
    if npx jest 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
elif grep -q '"test"' package.json 2>/dev/null; then
    echo "Detected: npm test script"
    if npm test 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
else
    echo "WARNING: No test runner detected in package.json"
    echo "Supported: jest, vitest, npm test"
    echo ""
    echo "SKIP: No tests to run"
    exit 0
fi
