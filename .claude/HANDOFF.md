# Session Handoff - 2025-12-05 (Evening)

## Session Summary

Investigated why MCP tools weren't appearing in Claude Code despite the server showing as "Connected". Used a differential diagnosis approach to systematically identify the root cause.

## Key Findings

### Root Cause Identified: Two Bugs Found

1. **Missing `@server.list_tools()` handler** (CRITICAL)
   - The MCP SDK requires a `list_tools` handler to respond to tool discovery requests
   - Without it, Claude Code asks "what tools?" and gets "Method not found"
   - Our code only had `@server.call_tool()` decorators (for execution) but no discovery handler

2. **Logs going to stdout instead of stderr** (MEDIUM)
   - `src/learning_memory_server/server/logging.py` line 25 used `stream=sys.stdout`
   - MCP stdio servers MUST log to stderr - stdout is reserved for JSON-RPC
   - **FIXED**: Changed to `stream=sys.stderr`

3. **Dispatcher architecture issue** (discovered during fix)
   - Each `@server.call_tool()` REPLACES the previous handler
   - Only the last registered tool (ping) was active
   - Need single dispatcher that routes to all tool implementations

## Changes Made

### Fixed Files
- `src/learning_memory_server/server/logging.py` - Logs now go to stderr
- `src/learning_memory_server/server/tools/__init__.py` - Added:
  - `_get_all_tool_definitions()` - Returns 23 Tool schemas
  - `@server.list_tools()` handler for tool discovery
  - Started dispatcher pattern (incomplete)
- `src/learning_memory_server/server/tools/memory.py` - Refactored to dispatcher pattern
- `tests/integration/test_mcp_protocol.py` - New MCP protocol-level tests

### Partially Fixed
- `src/learning_memory_server/server/tools/ghap.py` - Partially refactored (needs return dict + register_ghap_tools stub)

### Still Needs Refactoring (not started)
- `src/learning_memory_server/server/tools/code.py`
- `src/learning_memory_server/server/tools/git.py`
- `src/learning_memory_server/server/tools/learning.py`
- `src/learning_memory_server/server/tools/search.py`

## How Bug Was Missed

1. **Spec-level gap** - Specs didn't mention MCP SDK implementation details
2. **Architect misunderstanding** - Thought `server.list_tools()` was a getter, not a decorator
3. **Skeleton bug** - SPEC-002-05 established the wrong pattern, all tools followed it
4. **Test coverage gap** - Unit tests mocked `server.call_tool`, tested implementation not protocol
5. **No E2E protocol test** - Tests called Python services directly, never tested MCP handshake

## New Test Added

`tests/integration/test_mcp_protocol.py` - Protocol-level tests that:
- Connect to server via stdio (like Claude Code)
- Send initialize request
- Send list_tools request (this catches the bug!)
- Verify expected tools are returned
- Call tools to verify execution

This test caught the bug - it fails with "McpError: Method not found" when handler is missing.

## Next Steps

1. **Complete the dispatcher refactor** for remaining modules:
   - Add `get_*_tools()` functions that return dict of tool implementations
   - Remove `@server.call_tool()` decorators from individual tools
   - Make `register_*_tools()` functions no-op for backwards compatibility

2. **Fix ghap.py** - Add the return dict at end of `get_ghap_tools()`

3. **Run the new protocol tests** to verify fix works end-to-end

4. **Restart Claude Code** and verify tools appear as `mcp__learning-memory-server__*`

## Friction Points

- MCP SDK's dual-registration pattern (`call_tool` for execution, `list_tools` for discovery) is not obvious
- The SDK overwrites handlers instead of appending - easy to miss
- Testing the full MCP protocol requires starting a subprocess and doing async communication
- anyio/pytest-asyncio compatibility issues in test teardown (non-blocking but annoying)

## Commands to Resume

```bash
# Check current state
.claude/bin/clams-status

# Run the protocol test to see current status
TOKENIZERS_PARALLELISM=false uv run pytest tests/integration/test_mcp_protocol.py -v --tb=short

# After completing the fix, test with Claude Code
claude mcp list
# Then restart Claude Code to pick up changes
```
