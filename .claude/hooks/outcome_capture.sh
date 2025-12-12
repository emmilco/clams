#!/bin/bash
# .claude/hooks/outcome_capture.sh
# Hook: PostToolCall
# Purpose: Capture test/build outcomes
#
# SPEC-008: Uses HTTP transport to singleton MCP server
# - Quick: 1s timeout on HTTP calls
# - Silent failure: if server not ready, skip silently

set -uo pipefail  # No -e: we handle errors explicitly

# Configuration
SERVER_PORT="${CLAMS_PORT:-6334}"
SERVER_HOST="${CLAMS_HOST:-127.0.0.1}"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"

# Call MCP tool via HTTP (with short timeout)
call_mcp_http() {
    local tool_name="$1"
    local args="$2"
    local timeout="${3:-1}"

    # Build JSON-RPC style request
    local request
    request=$(jq -n --arg name "$tool_name" --argjson args "$args" \
        '{method: "tools/call", params: {name: $name, arguments: $args}}')

    curl -s --max-time "$timeout" -X POST "${SERVER_URL}/api/call" \
        -H "Content-Type: application/json" \
        -d "$request" 2>/dev/null || echo '{}'
}

# Main execution
main() {
    # Read tool result from stdin
    local tool_result
    tool_result=$(cat)

    # Parse tool details (with validation)
    if ! echo "$tool_result" | jq empty 2>/dev/null; then
        # Invalid JSON, exit silently
        exit 0
    fi

    local tool_name command exit_code stdout
    tool_name=$(echo "$tool_result" | jq -r '.tool // ""')
    command=$(echo "$tool_result" | jq -r '.command // ""')
    exit_code=$(echo "$tool_result" | jq -r '.exit_code // 999')
    stdout=$(echo "$tool_result" | jq -r '.stdout // ""')

    # Check if this is an outcome-triggering tool
    local is_test=false
    local is_build=false

    case "$command" in
        pytest*|*"npm test"*|*"cargo test"*|*"make test"*)
            is_test=true
            ;;
        *"make build"*|*"npm build"*|*"cargo build"*)
            is_build=true
            ;;
    esac

    # If not outcome-triggering, exit silently
    if [ "$is_test" = "false" ] && [ "$is_build" = "false" ]; then
        exit 0
    fi

    # Determine outcome
    local outcome_status="unknown"
    if [ "$exit_code" -eq 0 ]; then
        outcome_status="success"
    else
        outcome_status="failure"
    fi

    # Get current GHAP state (quick HTTP call with 1s timeout)
    local ghap_result
    ghap_result=$(call_mcp_http "get_active_ghap" '{}' 1)

    local has_active prediction
    has_active=$(echo "$ghap_result" | jq -r '.has_active // false' 2>/dev/null || echo "false")
    prediction=$(echo "$ghap_result" | jq -r '.prediction // ""' 2>/dev/null || echo "")

    # If failure and NO active GHAP, suggest starting GHAP
    if [ "$outcome_status" = "failure" ] && [ "$has_active" = "false" ]; then
        cat <<EOF
{
  "type": "suggestion",
  "content": "## Test FAILED\n\nConsider starting a GHAP to track your debugging approach and learn from the process.",
  "prompt": "Start tracking with GHAP?"
}
EOF
        exit 0
    fi

    # If GHAP active, compare prediction to outcome
    if [ "$has_active" = "true" ]; then
        local outcome_type
        if [ "$is_test" = "true" ]; then
            outcome_type="Test"
        else
            outcome_type="Build"
        fi

        if [ "$outcome_status" = "success" ]; then
            cat <<EOF
{
  "type": "outcome",
  "content": "## $outcome_type PASSED\n\nYour prediction was: \"$prediction\"\n\nDoes this confirm your hypothesis? If yes, resolve GHAP as CONFIRMED.",
  "suggested_action": "resolve_confirmed",
  "auto_captured": true
}
EOF
        else
            cat <<EOF
{
  "type": "outcome",
  "content": "## $outcome_type FAILED\n\nYour prediction was: \"$prediction\"\n\nActual: Test still fails.\n\nThis falsifies your hypothesis. Please:\n1. What surprised you?\n2. What was the root cause?\n3. What did you learn?",
  "suggested_action": "resolve_falsified",
  "auto_captured": true
}
EOF
        fi
    fi
}

main
exit 0
