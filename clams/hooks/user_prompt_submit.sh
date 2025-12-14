#!/bin/bash
# clams/hooks/user_prompt_submit.sh
# Hook: UserPromptSubmit
# Purpose: Analyze prompt and inject rich context
#
# SPEC-008: Uses HTTP transport to singleton MCP server
# - Blocking: waits for server to be ready (up to 30s)
# - HTTP: calls assemble_context via POST to /mcp

set -uo pipefail  # No -e: we handle errors explicitly

# Configuration
CLAMS_DIR="${HOME}/.clams"
PID_FILE="${CLAMS_DIR}/server.pid"
SERVER_PORT="${CLAMS_PORT:-6334}"
SERVER_HOST="${CLAMS_HOST:-127.0.0.1}"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"

# Check if server is running
is_server_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE" 2>/dev/null)
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Wait for server to be ready (blocking with timeout)
wait_for_ready() {
    local timeout="${1:-30}"
    local elapsed=0

    while [ "$elapsed" -lt "$timeout" ]; do
        # Check health endpoint
        if curl -s --max-time 1 "${SERVER_URL}/health" >/dev/null 2>&1; then
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    return 1
}

# Call MCP tool via HTTP
call_mcp_http() {
    local tool_name="$1"
    local args="$2"
    local timeout="${3:-10}"

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
    # Read user prompt from stdin
    local user_prompt
    user_prompt=$(cat)

    # Wait for server to be ready (blocking, up to 30s)
    if ! wait_for_ready 30; then
        # Server not available - graceful degradation (empty context)
        cat <<EOF
{
  "hookSpecificOutput": {
    "additionalContext": ""
  }
}
EOF
        exit 0
    fi

    # Call assemble_context via HTTP
    local prompt_escaped
    prompt_escaped=$(echo "$user_prompt" | jq -Rs .)

    local context_result
    context_result=$(call_mcp_http "assemble_context" \
        "{\"query\": $prompt_escaped, \"context_types\": [\"experiences\", \"values\"], \"limit\": 10, \"max_tokens\": 1500}" \
        10)

    # Handle failure - graceful degradation (empty context)
    if [ -z "$context_result" ] || [ "$context_result" = "{}" ]; then
        cat <<EOF
{
  "hookSpecificOutput": {
    "additionalContext": ""
  }
}
EOF
        exit 0
    fi

    # Build output using Claude Code's UserPromptSubmit schema
    # See: https://docs.anthropic.com/en/docs/claude-code/hooks
    local context_md
    context_md=$(echo "$context_result" | jq -r '.markdown // ""' 2>/dev/null || echo "")

    cat <<EOF
{
  "hookSpecificOutput": {
    "additionalContext": $(echo "$context_md" | jq -Rs .)
  }
}
EOF
}

main
exit 0
