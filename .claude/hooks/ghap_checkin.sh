#!/bin/bash
# .claude/hooks/ghap_checkin.sh
# Hook: PreToolCall
# Purpose: GHAP check-in reminder
#
# SPEC-008: Uses HTTP transport to singleton MCP server
# - Quick: 1s timeout on HTTP calls
# - Silent failure: if server not ready, skip silently

set -uo pipefail  # No -e: we handle errors explicitly

# Configuration
SERVER_PORT="${CLAMS_PORT:-6334}"
SERVER_HOST="${CLAMS_HOST:-127.0.0.1}"
SERVER_URL="http://${SERVER_HOST}:${SERVER_PORT}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

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

# Load configuration (with fallback if missing or invalid)
load_frequency() {
    local frequency=10
    if [ -f "$CONFIG_FILE" ]; then
        # Try to parse with Python fallback (more portable than yq)
        frequency=$(python3 -c "
import yaml, sys
try:
    with open('$CONFIG_FILE') as f:
        cfg = yaml.safe_load(f)
    print(cfg.get('hooks', {}).get('ghap_checkin', {}).get('frequency', 10))
except:
    print(10)
" 2>/dev/null || echo "10")
    fi
    echo "$frequency"
}

# Main execution
main() {
    local frequency
    frequency=$(load_frequency)

    # Check if check-in is due (quick HTTP call with 1s timeout)
    local checkin_result
    checkin_result=$(call_mcp_http "should_check_in" "{\"frequency\": $frequency}" 1)

    local should_checkin
    should_checkin=$(echo "$checkin_result" | jq -r '.should_check_in // false' 2>/dev/null || echo "false")

    # If not time for check-in, exit silently (no output)
    if [ "$should_checkin" != "true" ]; then
        exit 0
    fi

    # Get current GHAP state
    local ghap_result
    ghap_result=$(call_mcp_http "get_active_ghap" '{}' 1)

    local goal hypothesis prediction
    goal=$(echo "$ghap_result" | jq -r '.goal // "Unknown"' 2>/dev/null || echo "Unknown")
    hypothesis=$(echo "$ghap_result" | jq -r '.hypothesis // "Unknown"' 2>/dev/null || echo "Unknown")
    prediction=$(echo "$ghap_result" | jq -r '.prediction // "Unknown"' 2>/dev/null || echo "Unknown")

    # Reset tool counter (fire and forget, 1s timeout)
    call_mcp_http "reset_tool_count" '{}' 1 >/dev/null 2>&1 || true

    # Output reminder
    cat <<EOF
{
  "type": "reminder",
  "content": "## GHAP Check-in ($frequency tools since last update)\n\n**Current Goal**: $goal\n**Current Hypothesis**: $hypothesis\n**Current Prediction**: $prediction\n\nIs your hypothesis still valid? If it changed, update your GHAP entry."
}
EOF
}

main
exit 0
