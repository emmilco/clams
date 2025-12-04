#!/bin/bash
# .claude/hooks/ghap_checkin.sh
# Hook: PreToolCall
# Purpose: GHAP check-in reminder

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"
CONFIG_FILE="$SCRIPT_DIR/config.yaml"

# Helper: Call MCP with error handling
call_mcp() {
  local tool_name="$1"
  local args="$2"
  local result

  if ! result=$(python3 "$MCP_CLIENT" "$tool_name" "$args" 2>/dev/null); then
    echo '{}'
    return 1
  fi

  if ! echo "$result" | jq empty 2>/dev/null; then
    echo '{}'
    return 1
  fi

  echo "$result"
  return 0
}

# Load configuration (with fallback if missing or invalid)
FREQUENCY=10
if [ -f "$CONFIG_FILE" ]; then
  # Try to parse with Python fallback (more portable than yq)
  FREQUENCY=$(python3 -c "
import yaml, sys
try:
    with open('$CONFIG_FILE') as f:
        cfg = yaml.safe_load(f)
    print(cfg.get('hooks', {}).get('ghap_checkin', {}).get('frequency', 10))
except:
    print(10)
" 2>/dev/null || echo "10")
fi

# Check if check-in is due
CHECKIN_RESULT=$(call_mcp "should_check_in" "{\"frequency\": $FREQUENCY}")
SHOULD_CHECKIN=$(echo "$CHECKIN_RESULT" | jq -r '.should_check_in // false')

# If not time for check-in, exit silently (no output)
if [ "$SHOULD_CHECKIN" != "true" ]; then
  exit 0
fi

# Get current GHAP state
GHAP_RESULT=$(call_mcp "get_active_ghap" '{}')
GOAL=$(echo "$GHAP_RESULT" | jq -r '.goal // "Unknown"')
HYPOTHESIS=$(echo "$GHAP_RESULT" | jq -r '.hypothesis // "Unknown"')
PREDICTION=$(echo "$GHAP_RESULT" | jq -r '.prediction // "Unknown"')

# Reset tool counter (fire and forget)
call_mcp "reset_tool_count" '{}' >/dev/null 2>&1 || true

# Output reminder
cat <<EOF
{
  "type": "reminder",
  "content": "## GHAP Check-in ($FREQUENCY tools since last update)\n\n**Current Goal**: $GOAL\n**Current Hypothesis**: $HYPOTHESIS\n**Current Prediction**: $PREDICTION\n\nIs your hypothesis still valid? If it changed, update your GHAP entry."
}
EOF

exit 0
