#!/usr/bin/env bash
#
# check_tests_generic.sh: Generic test runner fallback
#
# Usage: check_tests_generic.sh <worktree_path> [task_id]
#
# Tries common test runners in order:
#   1. pytest (Python)
#   2. npm test (Node.js)
#   3. cargo test (Rust)
#   4. go test (Go)
#
# Exit codes:
#   0 - Tests passed (or no tests found)
#   1 - Tests failed
#   2 - No test framework detected

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

if [[ -f "$BIN_DIR/calm-common.sh" ]]; then
    source "$BIN_DIR/calm-common.sh"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-$(basename "$WORKTREE")}"

cd "$WORKTREE"

echo "=== Running Generic Test Detection ==="
echo "Directory: $WORKTREE"
echo ""
echo "Note: Project type was 'unknown' - attempting auto-detection"
echo ""

# Try pytest first
if [[ -f "pytest.ini" ]] || [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -d "tests" && -n "$(find tests -name '*.py' -print -quit 2>/dev/null)" ]]; then
    echo "Detected: Python (pytest)"
    if pytest -vvsx 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
fi

# Try npm test
if [[ -f "package.json" ]]; then
    echo "Detected: Node.js"
    if npm test 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
fi

# Try cargo test
if [[ -f "Cargo.toml" ]]; then
    echo "Detected: Rust"
    if cargo test 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
fi

# Try go test
if [[ -f "go.mod" ]]; then
    echo "Detected: Go"
    if go test ./... 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi
fi

echo "WARNING: No recognized test framework detected"
echo "Supported: pytest, npm test, cargo test, go test"
echo ""
echo "SKIP: No tests to run"
exit 0
