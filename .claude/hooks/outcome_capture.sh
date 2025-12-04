#!/bin/bash
# .claude/hooks/outcome_capture.sh
# Hook: PostToolCall
# Purpose: Capture test/build outcomes

set -uo pipefail  # No -e: we handle errors explicitly

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/mcp_client.py"

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

# Read tool result from stdin
TOOL_RESULT=$(cat)

# Parse tool details (with validation)
if ! echo "$TOOL_RESULT" | jq empty 2>/dev/null; then
  # Invalid JSON, exit silently
  exit 0
fi

TOOL_NAME=$(echo "$TOOL_RESULT" | jq -r '.tool // ""')
COMMAND=$(echo "$TOOL_RESULT" | jq -r '.command // ""')
EXIT_CODE=$(echo "$TOOL_RESULT" | jq -r '.exit_code // 999')
STDOUT=$(echo "$TOOL_RESULT" | jq -r '.stdout // ""')

# Check if this is an outcome-triggering tool
IS_TEST=false
IS_BUILD=false

case "$COMMAND" in
  pytest*|*"npm test"*|*"cargo test"*|*"make test"*)
    IS_TEST=true
    ;;
  *"make build"*|*"npm build"*|*"cargo build"*)
    IS_BUILD=true
    ;;
esac

# If not outcome-triggering, exit silently
if [ "$IS_TEST" = "false" ] && [ "$IS_BUILD" = "false" ]; then
  exit 0
fi

# Determine outcome
OUTCOME_STATUS="unknown"
if [ "$EXIT_CODE" -eq 0 ]; then
  OUTCOME_STATUS="success"
else
  OUTCOME_STATUS="failure"
fi

# Get current GHAP state
GHAP_RESULT=$(call_mcp "get_active_ghap" '{}')
HAS_ACTIVE=$(echo "$GHAP_RESULT" | jq -r '.has_active // false')
PREDICTION=$(echo "$GHAP_RESULT" | jq -r '.prediction // ""')

# If failure and NO active GHAP, suggest starting GHAP
if [ "$OUTCOME_STATUS" = "failure" ] && [ "$HAS_ACTIVE" = "false" ]; then
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
if [ "$HAS_ACTIVE" = "true" ]; then
  if [ "$IS_TEST" = "true" ]; then
    OUTCOME_TYPE="Test"
  else
    OUTCOME_TYPE="Build"
  fi

  if [ "$OUTCOME_STATUS" = "success" ]; then
    cat <<EOF
{
  "type": "outcome",
  "content": "## $OUTCOME_TYPE PASSED\n\nYour prediction was: \"$PREDICTION\"\n\nDoes this confirm your hypothesis? If yes, resolve GHAP as CONFIRMED.",
  "suggested_action": "resolve_confirmed",
  "auto_captured": true
}
EOF
  else
    cat <<EOF
{
  "type": "outcome",
  "content": "## $OUTCOME_TYPE FAILED\n\nYour prediction was: \"$PREDICTION\"\n\nActual: Test still fails.\n\nThis falsifies your hypothesis. Please:\n1. What surprised you?\n2. What was the root cause?\n3. What did you learn?",
  "suggested_action": "resolve_falsified",
  "auto_captured": true
}
EOF
  fi
fi

exit 0
