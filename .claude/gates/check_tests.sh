#!/usr/bin/env bash
#
# check_tests.sh: Verify tests pass and log results
#
# Usage: check_tests.sh [worktree_path] [task_id]
#
# Runs the test suite, verifies all tests pass, and logs results to test_runs table.
# Returns 0 if all pass, 1 otherwise.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

# Use clams-common.sh to resolve to main repo database
if [[ -f "$BIN_DIR/clams-common.sh" ]]; then
    source "$BIN_DIR/clams-common.sh"
else
    # Fallback for standalone execution
    CLAUDE_DIR="$(dirname "$SCRIPT_DIR")"
    _LOCAL_REPO="$(dirname "$CLAUDE_DIR")"
    MAIN_REPO=$(cd "$_LOCAL_REPO" && git worktree list --porcelain 2>/dev/null | head -1 | sed 's/worktree //')
    MAIN_REPO="${MAIN_REPO:-$_LOCAL_REPO}"
    CLAUDE_DIR="$MAIN_REPO/.claude"
    DB_PATH="$CLAUDE_DIR/clams.db"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-}"

cd "$WORKTREE"

# Try to infer task_id from worktree path if not provided
if [[ -z "$TASK_ID" ]]; then
    TASK_ID=$(basename "$WORKTREE")
fi

echo "=== Running Tests ==="
echo "Directory: $WORKTREE"
echo "Task ID: $TASK_ID"
echo ""

# Get commit SHA
COMMIT_SHA=$(git rev-parse HEAD 2>/dev/null || echo "unknown")

# Function to log test results to database
log_test_results() {
    local total="$1"
    local passed="$2"
    local failed="$3"
    local errors="$4"
    local skipped="$5"
    local duration="$6"
    local failed_tests_json="$7"

    if [[ -f "$DB_PATH" ]]; then
        # Escape single quotes in JSON for SQLite
        local escaped_json
        escaped_json=$(echo "$failed_tests_json" | sed "s/'/''/g")

        sqlite3 "$DB_PATH" <<EOF
INSERT INTO test_runs (
    task_id, worktree, commit_sha, total_tests, passed, failed, errors, skipped,
    execution_time_seconds, failed_tests
) VALUES (
    '$TASK_ID',
    '$WORKTREE',
    '$COMMIT_SHA',
    $total,
    $passed,
    $failed,
    $errors,
    $skipped,
    $duration,
    '$escaped_json'
);
EOF
        echo "Test results logged to database"
    fi
}

# Function to extract failed tests from pytest output
extract_failed_tests() {
    local log_file="$1"

    # Find FAILED lines: "FAILED tests/test_foo.py::test_bar - AssertionError: ..."
    # Extract test name and short error
    local failed_json="["
    local first=true

    while IFS= read -r line; do
        # Extract test path and error message
        local test_name error_msg

        # Pattern: FAILED path::test_name - ErrorType: message
        if [[ "$line" =~ ^FAILED[[:space:]]+(.+)[[:space:]]+-[[:space:]]+(.+)$ ]]; then
            test_name="${BASH_REMATCH[1]}"
            error_msg="${BASH_REMATCH[2]}"
        elif [[ "$line" =~ ^FAILED[[:space:]]+(.+)$ ]]; then
            test_name="${BASH_REMATCH[1]}"
            error_msg=""
        else
            continue
        fi

        # Escape for JSON
        test_name=$(echo "$test_name" | sed 's/\\/\\\\/g; s/"/\\"/g')
        error_msg=$(echo "$error_msg" | sed 's/\\/\\\\/g; s/"/\\"/g' | head -c 500)

        if $first; then
            first=false
        else
            failed_json+=","
        fi

        failed_json+="{\"test\":\"$test_name\",\"error\":\"$error_msg\"}"

    done < <(grep "^FAILED " "$log_file" 2>/dev/null || true)

    failed_json+="]"
    echo "$failed_json"
}

# Function to parse pytest JSON report
parse_pytest_json() {
    local json_file="$1"

    if [[ ! -f "$json_file" ]]; then
        return 1
    fi

    # Extract values using grep/sed (portable, no jq dependency)
    local summary
    summary=$(cat "$json_file")

    local total passed failed errors skipped duration
    total=$(echo "$summary" | grep -o '"total":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
    passed=$(echo "$summary" | grep -o '"passed":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
    failed=$(echo "$summary" | grep -o '"failed":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
    errors=$(echo "$summary" | grep -o '"error":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
    skipped=$(echo "$summary" | grep -o '"skipped":[0-9]*' | head -1 | cut -d: -f2 || echo "0")
    duration=$(echo "$summary" | grep -o '"duration":[0-9.]*' | head -1 | cut -d: -f2 || echo "0")

    # Get failed test names (simplified extraction)
    local failed_tests="[]"

    echo "$total $passed $failed $errors $skipped $duration"
}

# Function to parse pytest text output
parse_pytest_text() {
    local log_file="$1"

    # Look for summary line like: "5 passed, 2 failed, 1 error in 1.23s"
    # or "5 passed in 1.23s"
    local summary_line
    summary_line=$(grep -E "^=+ .* in [0-9.]+(s|ms) =+$" "$log_file" | tail -1 || echo "")

    if [[ -z "$summary_line" ]]; then
        # Try alternate format
        summary_line=$(grep -E "[0-9]+ passed" "$log_file" | tail -1 || echo "")
    fi

    local passed=0 failed=0 errors=0 skipped=0 duration=0

    # Extract counts
    passed=$(echo "$summary_line" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    failed=$(echo "$summary_line" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    errors=$(echo "$summary_line" | grep -oE "[0-9]+ error" | grep -oE "[0-9]+" || echo "0")
    skipped=$(echo "$summary_line" | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")

    # Extract duration
    duration=$(echo "$summary_line" | grep -oE "[0-9]+\.[0-9]+" | tail -1 || echo "0")

    local total=$((passed + failed + errors + skipped))

    echo "$total $passed $failed $errors $skipped $duration"
}

# Run pytest
run_pytest() {
    local json_report=".pytest_results.json"
    local exit_code=0
    local start_time end_time duration
    local total=0 passed=0 failed=0 errors=0 skipped=0
    local failed_tests_json="[]"

    start_time=$(date +%s.%N)

    echo "Detected: Python (pytest)"
    echo ""

    # Sync dependencies and install package with uv
    if [[ -f "pyproject.toml" ]] && command -v uv &> /dev/null; then
        echo "Syncing dependencies with uv..."
        uv sync --all-extras --quiet 2>/dev/null || uv sync --quiet 2>/dev/null || true
        echo ""

        # Run pytest via venv python to ensure correct environment
        echo "Running tests..."
        .venv/bin/python -m pytest -xvs --ignore=tests/e2e 2>&1 | tee test_output.log || exit_code=$?
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    elif [[ -f "pyproject.toml" ]]; then
        # Fallback without uv
        echo "Installing package in editable mode..."
        pip install -e ".[dev]" --quiet 2>/dev/null || pip install -e . --quiet 2>/dev/null || true
        echo ""

        pytest -xvs --ignore=tests/e2e 2>&1 | tee test_output.log || exit_code=$?
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    else
        # No pyproject.toml, just run pytest
        pytest -xvs --ignore=tests/e2e 2>&1 | tee test_output.log || exit_code=$?
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    fi

    # Extract failed tests from log output (works for both modes)
    if [[ -f "test_output.log" ]]; then
        failed_tests_json=$(extract_failed_tests test_output.log)
    fi

    end_time=$(date +%s.%N)

    # If duration wasn't parsed, calculate it
    if [[ "$duration" == "0" ]] || [[ -z "$duration" ]]; then
        duration=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "0")
    fi

    # Ensure we have valid numbers
    total=${total:-0}
    passed=${passed:-0}
    failed=${failed:-0}
    errors=${errors:-0}
    skipped=${skipped:-0}
    duration=${duration:-0}

    echo ""
    echo "=== Test Summary ==="
    echo "Total: $total | Passed: $passed | Failed: $failed | Errors: $errors | Skipped: $skipped"
    echo "Duration: ${duration}s"

    # Show failed tests if any
    if [[ "$failed_tests_json" != "[]" ]]; then
        echo ""
        echo "Failed tests recorded in database"
    fi

    # Log to database
    log_test_results "$total" "$passed" "$failed" "$errors" "$skipped" "$duration" "$failed_tests_json"

    if [[ $exit_code -eq 0 ]]; then
        echo ""
        echo "PASS: All tests passed"
        return 0
    else
        echo ""
        echo "FAIL: Tests failed"
        return 1
    fi
}

# Main test detection and execution
if [[ -f "pytest.ini" ]] || [[ -f "pyproject.toml" ]] || [[ -f "setup.py" ]] || [[ -d "tests" && -f "$(find tests -name '*.py' -print -quit 2>/dev/null)" ]]; then
    run_pytest
    exit $?

elif [[ -f "package.json" ]]; then
    echo "Detected: Node.js"
    echo "Note: test_runs logging not implemented for Node.js"
    if npm test 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi

elif [[ -f "Cargo.toml" ]]; then
    echo "Detected: Rust"
    echo "Note: test_runs logging not implemented for Rust"
    if cargo test 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi

elif [[ -f "go.mod" ]]; then
    echo "Detected: Go"
    echo "Note: test_runs logging not implemented for Go"
    if go test ./... 2>&1 | tee test_output.log; then
        echo ""
        echo "PASS: All tests passed"
        exit 0
    else
        echo ""
        echo "FAIL: Tests failed"
        exit 1
    fi

else
    echo "WARNING: No recognized test framework detected"
    echo "Supported: pytest, npm test, cargo test, go test"
    echo ""
    echo "SKIP: No tests to run"
    exit 0
fi
