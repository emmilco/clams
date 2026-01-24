#!/usr/bin/env bash
#
# check_tests_python.sh: Run Python test suite (pytest)
#
# Usage: check_tests_python.sh <worktree_path> [task_id]
#
# Exit codes:
#   0 - All tests passed
#   1 - Tests failed or other error
#   2 - Tool not available (skipped)
#
# Features:
#   - Runs pytest with cleanup timeout monitoring
#   - Logs results to test_runs table in CLAWS database
#   - Enforces no skipped tests policy
#   - Detects collection errors (import/syntax failures)

set -euo pipefail

# Cleanup timeout in seconds (configurable via environment)
CLEANUP_TIMEOUT="${CLAWS_CLEANUP_TIMEOUT:-30}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$(dirname "$SCRIPT_DIR")/bin"

# Use claws-common.sh to resolve to main repo database
if [[ -f "$BIN_DIR/claws-common.sh" ]]; then
    source "$BIN_DIR/claws-common.sh"
else
    # Fallback for standalone execution
    CLAUDE_DIR="$(dirname "$SCRIPT_DIR")"
    _LOCAL_REPO="$(dirname "$CLAUDE_DIR")"
    MAIN_REPO=$(cd "$_LOCAL_REPO" && git worktree list --porcelain 2>/dev/null | head -1 | sed 's/worktree //')
    MAIN_REPO="${MAIN_REPO:-$_LOCAL_REPO}"
    CLAUDE_DIR="$MAIN_REPO/.claude"
    DB_PATH="$CLAUDE_DIR/claws.db"
fi

WORKTREE="${1:-.}"
TASK_ID="${2:-}"

cd "$WORKTREE"

# Try to infer task_id from worktree path if not provided
if [[ -z "$TASK_ID" ]]; then
    TASK_ID=$(basename "$WORKTREE")
fi

echo "=== Running Python Tests (pytest) ==="
echo "Directory: $WORKTREE"
echo "Task ID: $TASK_ID"
echo ""

# Verify this looks like a Python project
if [[ ! -f "pyproject.toml" ]] && [[ ! -f "setup.py" ]] && [[ ! -f "pytest.ini" ]]; then
    if [[ ! -d "tests" ]] || [[ -z "$(find tests -name '*.py' -print -quit 2>/dev/null)" ]]; then
        echo "Error: Not a Python project (no pyproject.toml, setup.py, pytest.ini, or tests/*.py)" >&2
        exit 2
    fi
fi

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

    local failed_json="["
    local first=true

    while IFS= read -r line; do
        local test_name error_msg

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

# Function to parse pytest text output
parse_pytest_text() {
    local log_file="$1"

    local summary_line
    summary_line=$(grep -E "^=+ .* in [0-9.]+(s|ms) =+$" "$log_file" | tail -1 || echo "")

    if [[ -z "$summary_line" ]]; then
        summary_line=$(grep -E "[0-9]+ passed" "$log_file" | tail -1 || echo "")
    fi

    local passed=0 failed=0 errors=0 skipped=0 duration=0

    passed=$(echo "$summary_line" | grep -oE "[0-9]+ passed" | grep -oE "[0-9]+" || echo "0")
    failed=$(echo "$summary_line" | grep -oE "[0-9]+ failed" | grep -oE "[0-9]+" || echo "0")
    errors=$(echo "$summary_line" | grep -oE "[0-9]+ error" | grep -oE "[0-9]+" || echo "0")
    skipped=$(echo "$summary_line" | grep -oE "[0-9]+ skipped" | grep -oE "[0-9]+" || echo "0")
    duration=$(echo "$summary_line" | grep -oE "[0-9]+\.[0-9]+" | tail -1 || echo "0")

    local total=$((passed + failed + errors + skipped))

    echo "$total $passed $failed $errors $skipped $duration"
}

# Run a command with cleanup timeout monitoring
run_with_cleanup_timeout() {
    local log_file="$1"
    shift
    local cmd=("$@")

    # Start the command in background
    "${cmd[@]}" > "$log_file" 2>&1 &
    local pid=$!

    # Also tail the log to show progress
    tail -f "$log_file" 2>/dev/null &
    local tail_pid=$!

    local tests_completed=false
    local completion_time=0
    local check_interval=1

    while kill -0 "$pid" 2>/dev/null; do
        if [[ -f "$log_file" ]] && grep -qE "^=+ .* in [0-9.]+(s|ms) =+$" "$log_file" 2>/dev/null; then
            if [[ "$tests_completed" == "false" ]]; then
                tests_completed=true
                completion_time=$(date +%s)
                echo "" >&2
                echo "=== Tests completed, waiting for cleanup (timeout: ${CLEANUP_TIMEOUT}s) ===" >&2
            fi

            local current_time
            current_time=$(date +%s)
            local elapsed=$((current_time - completion_time))

            if [[ $elapsed -ge $CLEANUP_TIMEOUT ]]; then
                echo "" >&2
                echo "=== CLEANUP TIMEOUT ===" >&2
                echo "ERROR: pytest process hung for ${CLEANUP_TIMEOUT}s after tests completed" >&2
                echo "Force-killing pytest process (PID $pid)..." >&2

                kill -TERM "$pid" 2>/dev/null || true
                sleep 2
                kill -KILL "$pid" 2>/dev/null || true

                kill "$tail_pid" 2>/dev/null || true
                wait "$tail_pid" 2>/dev/null || true

                return 1
            fi
        fi

        sleep "$check_interval"
    done

    kill "$tail_pid" 2>/dev/null || true
    wait "$tail_pid" 2>/dev/null || true

    wait "$pid"
    return $?
}

# Main test execution
run_pytest() {
    local exit_code=0
    local start_time end_time duration
    local total=0 passed=0 failed=0 errors=0 skipped=0
    local failed_tests_json="[]"
    local cleanup_timeout=false

    start_time=$(date +%s.%N)

    # Sync dependencies and run via uv if available
    if [[ -f "pyproject.toml" ]] && command -v uv &> /dev/null; then
        echo "Syncing dependencies with uv..."
        uv sync --all-extras --quiet 2>/dev/null || uv sync --quiet 2>/dev/null || true
        echo ""

        echo "Running tests (cleanup timeout: ${CLEANUP_TIMEOUT}s)..."
        export PYTHONPATH="${WORKTREE}/src:${PYTHONPATH:-}"
        if ! run_with_cleanup_timeout "test_output.log" .venv/bin/python -m pytest -vvsx --ignore=tests/e2e -m "not slow and not integration"; then
            if [[ -f "test_output.log" ]] && grep -qE "^=+ .* in [0-9.]+(s|ms) =+$" test_output.log 2>/dev/null; then
                cleanup_timeout=true
            fi
            exit_code=1
        fi
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    elif [[ -f "pyproject.toml" ]]; then
        echo "Installing package in editable mode..."
        pip install -e ".[dev]" --quiet 2>/dev/null || pip install -e . --quiet 2>/dev/null || true
        echo ""

        echo "Running tests (cleanup timeout: ${CLEANUP_TIMEOUT}s)..."
        if ! run_with_cleanup_timeout "test_output.log" pytest -vvsx --ignore=tests/e2e -m "not slow and not integration"; then
            if [[ -f "test_output.log" ]] && grep -qE "^=+ .* in [0-9.]+(s|ms) =+$" test_output.log 2>/dev/null; then
                cleanup_timeout=true
            fi
            exit_code=1
        fi
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    else
        echo "Running tests (cleanup timeout: ${CLEANUP_TIMEOUT}s)..."
        if ! run_with_cleanup_timeout "test_output.log" pytest -vvsx --ignore=tests/e2e -m "not slow and not integration"; then
            if [[ -f "test_output.log" ]] && grep -qE "^=+ .* in [0-9.]+(s|ms) =+$" test_output.log 2>/dev/null; then
                cleanup_timeout=true
            fi
            exit_code=1
        fi
        read -r total passed failed errors skipped duration <<< "$(parse_pytest_text test_output.log)"
    fi

    # Extract failed tests from log
    if [[ -f "test_output.log" ]]; then
        failed_tests_json=$(extract_failed_tests test_output.log)
    fi

    end_time=$(date +%s.%N)

    if [[ "$duration" == "0" ]] || [[ -z "$duration" ]]; then
        duration=$(echo "$end_time - $start_time" | bc 2>/dev/null || echo "0")
    fi

    # Ensure valid numbers
    total=${total:-0}
    passed=${passed:-0}
    failed=${failed:-0}
    errors=${errors:-0}
    skipped=${skipped:-0}
    duration=${duration:-0}

    # Check for collection errors
    if grep -qE "^ERROR collecting|^E   (ModuleNotFoundError|ImportError|SyntaxError)" test_output.log 2>/dev/null; then
        echo ""
        echo "=== Collection Errors Detected ==="
        grep -E "^ERROR collecting|^E   (ModuleNotFoundError|ImportError|SyntaxError)" test_output.log | head -10
        echo ""
        echo "FAIL: Test collection errors (import/syntax failures)"
        log_test_results "$total" "$passed" "$failed" "1" "$skipped" "$duration" '[{"test":"collection","error":"Import or syntax error during test collection"}]'
        return 1
    fi

    echo ""
    echo "=== Test Summary ==="
    echo "Total: $total | Passed: $passed | Failed: $failed | Errors: $errors | Skipped: $skipped"
    echo "Duration: ${duration}s"

    log_test_results "$total" "$passed" "$failed" "$errors" "$skipped" "$duration" "$failed_tests_json"

    # Handle cleanup timeout
    if [[ "$cleanup_timeout" == "true" ]]; then
        echo ""
        echo "=== CLEANUP TIMEOUT FAILURE ==="
        echo "FAIL: pytest process hung during cleanup for ${CLEANUP_TIMEOUT}s"
        log_test_results "$total" "$passed" "0" "1" "$skipped" "$duration" '[{"test":"cleanup","error":"Process hung during cleanup"}]'
        return 1
    fi

    # Check for skipped tests
    if [[ "$skipped" -gt 0 ]]; then
        echo ""
        echo "=== Analyzing $skipped Skipped Tests ==="

        # Count platform skips (reason starts with "Platform:")
        # Format: SKIPPED [N] path:line: Platform: reason
        local platform_skips
        platform_skips=$(grep -c "^SKIPPED \[.*\] .*: Platform:" test_output.log 2>/dev/null || echo "0")

        # Also check short test summary info format
        # Format: SKIPPED [1] tests/file.py:123: Platform: reason
        local summary_platform_skips
        summary_platform_skips=$(grep -cE "^SKIPPED \[[0-9]+\].*Platform:" test_output.log 2>/dev/null || echo "0")

        # Use the larger of the two counts
        if [[ "$summary_platform_skips" -gt "$platform_skips" ]]; then
            platform_skips="$summary_platform_skips"
        fi

        local non_platform_skips=$((skipped - platform_skips))

        if [[ "$platform_skips" -gt 0 ]]; then
            echo "  Platform-related skips: $platform_skips (allowed)"
            grep -E "^SKIPPED \[[0-9]+\].*Platform:" test_output.log 2>/dev/null | head -5 | sed 's/^/    /'
        fi

        if [[ "$non_platform_skips" -gt 0 ]]; then
            echo ""
            echo "FAIL: $non_platform_skips non-platform tests were skipped"
            echo "Non-platform skips are not allowed - they hide missing dependencies or broken code."
            echo ""
            echo "Skipped tests (non-platform):"
            grep "^SKIPPED " test_output.log 2>/dev/null | grep -v "Platform:" | head -10 | sed 's/^/  /'
            return 1
        fi

        echo ""
        echo "All $skipped skipped tests are platform-specific (acceptable)"
    fi

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

run_pytest
exit $?
