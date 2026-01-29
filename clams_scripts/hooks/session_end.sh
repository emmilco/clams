#!/bin/bash
# clams/hooks/session_end.sh
# Hook: SessionEnd (NOT YET SUPPORTED BY CLAUDE CODE)
# Purpose: Session cleanup
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

# Get script directory
# This file is at clams/hooks/session_end.sh
# mcp_client.py is at clams/mcp_client.py (one level up)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_CLIENT="$SCRIPT_DIR/../mcp_client.py"

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

# End session (abandons unresolved GHAP)
SESSION_RESULT=$(call_mcp "end_session" '{}')

# No output needed
exit 0
