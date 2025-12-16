#!/bin/bash
# clams/hooks/session_start.sh
# Hook: SessionStart
# Purpose: Initialize session and inject light context
#
# SPEC-008: Uses HTTP transport to singleton MCP server
# - Non-blocking: starts daemon if needed, doesn't wait
# - File I/O: reads local files for session state
# - HTTP: calls server for context assembly
#
# SPEC-029: Sources configuration from ~/.clams/config.env

set -uo pipefail  # No -e: we handle errors explicitly

# Source CLAMS configuration (written by server on startup)
# See SPEC-029 for canonical configuration module
CLAMS_CONFIG="${HOME}/.clams/config.env"
if [ -f "$CLAMS_CONFIG" ]; then
    # shellcheck source=/dev/null
    source "$CLAMS_CONFIG"
fi

# Fallback defaults if config not available (must match ServerSettings defaults)
CLAMS_HTTP_HOST="${CLAMS_HTTP_HOST:-127.0.0.1}"
CLAMS_HTTP_PORT="${CLAMS_HTTP_PORT:-6334}"
CLAMS_PID_FILE="${CLAMS_PID_FILE:-${HOME}/.clams/server.pid}"
CLAMS_STORAGE_PATH="${CLAMS_STORAGE_PATH:-${HOME}/.clams}"

# Derived configuration using sourced values
CLAMS_DIR="${CLAMS_STORAGE_PATH}"
JOURNAL_DIR="${CLAMS_DIR}/journal"
PID_FILE="${CLAMS_PID_FILE}"
SERVER_PORT="${CLAMS_HTTP_PORT}"
SERVER_HOST="${CLAMS_HTTP_HOST}"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"

# Get script directory for finding the server binary
# This file is at clams/hooks/session_start.sh
# Navigate: clams/hooks -> clams -> repo_root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Ensure directories exist
mkdir -p "$JOURNAL_DIR"

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

# Start daemon if not running (non-blocking)
start_daemon_if_needed() {
    if is_server_running; then
        return 0
    fi

    # Try to start the server in daemon mode
    # Use the venv from the repo if available
    if [ -f "$REPO_ROOT/.venv/bin/python" ]; then
        nohup "$REPO_ROOT/.venv/bin/python" -m clams.server.main --http --daemon \
            --host "$SERVER_HOST" --port "$SERVER_PORT" \
            > "${CLAMS_DIR}/server.log" 2>&1 &
    elif command -v clams-server &>/dev/null; then
        nohup clams-server --http --daemon \
            --host "$SERVER_HOST" --port "$SERVER_PORT" \
            > "${CLAMS_DIR}/server.log" 2>&1 &
    fi
    # Don't wait - this is non-blocking
}

# Call MCP tool via HTTP (with timeout)
call_mcp_http() {
    local tool_name="$1"
    local args="$2"
    local timeout="${3:-5}"

    # Build JSON-RPC style request
    local request
    request=$(jq -n --arg name "$tool_name" --argjson args "$args" \
        '{method: "tools/call", params: {name: $name, arguments: $args}}')

    curl -s --max-time "$timeout" -X POST "${SERVER_URL}/api/call" \
        -H "Content-Type: application/json" \
        -d "$request" 2>/dev/null || echo '{}'
}

# Generate session ID (UUID)
generate_session_id() {
    if command -v uuidgen &>/dev/null; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    else
        python3 -c "import uuid; print(uuid.uuid4())"
    fi
}

# Check for orphaned GHAP from previous session (local file I/O)
check_orphaned_ghap() {
    local ghap_file="${JOURNAL_DIR}/current_ghap.json"
    local session_file="${JOURNAL_DIR}/.session_id"

    if [ ! -f "$ghap_file" ]; then
        echo '{"has_orphan": false}'
        return
    fi

    local current_session=""
    if [ -f "$session_file" ]; then
        current_session=$(cat "$session_file" 2>/dev/null)
    fi

    local ghap_session
    ghap_session=$(jq -r '.session_id // ""' "$ghap_file" 2>/dev/null)

    if [ -n "$ghap_session" ] && [ "$ghap_session" != "$current_session" ]; then
        # This is an orphan from a different session
        local goal hypothesis
        goal=$(jq -r '.goal // "Unknown"' "$ghap_file" 2>/dev/null)
        hypothesis=$(jq -r '.hypothesis // "Unknown"' "$ghap_file" 2>/dev/null)
        jq -n --arg goal "$goal" --arg hypothesis "$hypothesis" --arg session "$ghap_session" \
            '{has_orphan: true, goal: $goal, hypothesis: $hypothesis, session_id: $session}'
    else
        echo '{"has_orphan": false}'
    fi
}

# Main execution
main() {
    # 1. Start daemon if needed (non-blocking, returns immediately)
    start_daemon_if_needed

    # 2. Generate and save session ID (local file I/O)
    local session_id
    session_id=$(generate_session_id)
    echo "$session_id" > "${JOURNAL_DIR}/.session_id"
    echo "0" > "${JOURNAL_DIR}/.tool_count"

    # 3. Check for orphaned GHAP (local file I/O)
    local orphan_result
    orphan_result=$(check_orphaned_ghap)
    local has_orphan
    has_orphan=$(echo "$orphan_result" | jq -r '.has_orphan // false')

    # 4. Try to get light context via HTTP (optional, graceful degradation)
    local context_md=""
    if is_server_running; then
        # Server might be running, try to get context
        local context_result
        context_result=$(call_mcp_http "assemble_context" \
            '{"query": "", "context_types": ["values"], "limit": 5, "max_tokens": 500}' 2)
        context_md=$(echo "$context_result" | jq -r '.markdown // ""' 2>/dev/null || echo "")
    fi

    # 5. Build GHAP instructions
    local ghap_instructions="## GHAP Learning System

**Start a GHAP before your first investigative action** - not after something breaks.

If you're about to grep/search/read code to understand *why* something happens, you have a hypothesis. Capture it.

### When to Start a GHAP
- \"I think this test fails because X\" → start before investigating
- \"The error is probably in module Y\" → start before reading that module
- \"Let me check if Z is the cause\" → that's a hypothesis, capture it

### When to Skip
- Reading a file the user explicitly pointed you to
- Running a command the user explicitly asked for
- Simple tasks with no uncertainty (fix typo, add import)

### The Tools
1. \`mcp__clams__start_ghap\` - Goal, hypothesis, action, prediction (30 sec)
2. \`mcp__clams__update_ghap\` - Revise if hypothesis changes
3. \`mcp__clams__resolve_ghap\` - Record outcome (confirmed/falsified/abandoned)

Past GHAPs surface as relevant context in future sessions.

---
"

    # 6. Build output with Claude Code's expected SessionStart schema
    # See: https://code.claude.com/docs/en/hooks (hookSpecificOutput.additionalContext)
    if [ "$has_orphan" = "true" ]; then
        local goal hypothesis
        goal=$(echo "$orphan_result" | jq -r '.goal // "Unknown"')
        hypothesis=$(echo "$orphan_result" | jq -r '.hypothesis // "Unknown"')

        local orphan_content="## Orphaned GHAP Detected

From previous session:

**Goal**: $goal
**Hypothesis**: $hypothesis

**Options**:
- Adopt and continue this work
- Abandon with reason

---

${ghap_instructions}${context_md}"

        cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": $(echo "$orphan_content" | jq -Rs .)
  }
}
EOF
    else
        local full_content="${ghap_instructions}${context_md}"
        cat <<EOF
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": $(echo "$full_content" | jq -Rs .)
  }
}
EOF
    fi
}

main
exit 0
