# Session Handoff - 2025-12-05 (Night)

## Session Summary

Completed the MCP tool discovery fix. The server now properly exposes all 23 tools to Claude Code.

## Key Changes

### Root Cause (from previous session)
1. Missing `@server.list_tools()` handler - Claude Code asks "what tools?" and got "Method not found"
2. Each `@server.call_tool()` decorator REPLACED the previous handler - only the last tool was active
3. Logs were going to stdout instead of stderr (fixed in previous session)

### Fix Implemented This Session

Refactored all tool modules from the old pattern to a dispatcher pattern:

**Old Pattern** (broken):
```python
def register_foo_tools(server, ...):
    @server.call_tool()  # Each decorator REPLACED the previous!
    async def tool_a(): ...

    @server.call_tool()  # Only last tool was registered
    async def tool_b(): ...
```

**New Pattern** (working):
```python
def get_foo_tools(...) -> dict[str, Any]:
    async def tool_a(): ...
    async def tool_b(): ...
    return {"tool_a": tool_a, "tool_b": tool_b}

# Central dispatcher in __init__.py:
tool_registry.update(get_foo_tools(...))

@server.call_tool()  # Single dispatcher for ALL tools
async def handle_call_tool(name, arguments):
    return await tool_registry[name](**arguments)

@server.list_tools()  # Returns all 23 tool schemas
async def handle_list_tools():
    return _get_all_tool_definitions()
```

### Files Modified
- `src/learning_memory_server/server/tools/__init__.py` - Added `Any` import, central dispatcher
- `src/learning_memory_server/server/tools/ghap.py` - Added return dict and stub
- `src/learning_memory_server/server/tools/code.py` - Refactored to dispatcher pattern
- `src/learning_memory_server/server/tools/git.py` - Refactored to dispatcher pattern
- `src/learning_memory_server/server/tools/learning.py` - Refactored to dispatcher pattern
- `src/learning_memory_server/server/tools/search.py` - Refactored to dispatcher pattern
- `tests/server/tools/test_code.py` - Updated to use get_code_tools
- `tests/server/tools/test_git.py` - Updated to use get_git_tools
- `tests/server/tools/test_memory.py` - Updated to use get_memory_tools

## Test Status

### Passing
- **MCP Protocol Tests**: 10/10 (the critical regression tests)
- `tests/server/tools/test_code.py`: All pass
- `tests/server/tools/test_git.py`: All pass
- `tests/server/tools/test_memory.py`: All pass
- `tests/server/tools/test_enums.py`: All pass
- `tests/server/tools/test_errors.py`: All pass

### Still Need Update
These test files still use the old `register_*_tools` pattern with `server.tools` dict:
- `tests/server/tools/test_ghap.py` - Needs refactor to use `get_ghap_tools`
- `tests/server/tools/test_learning.py` - Needs refactor to use `get_learning_tools`
- `tests/server/tools/test_search.py` - Needs refactor to use `get_search_tools`

The fix pattern is the same as the other tests:
1. Import `get_*_tools` instead of `register_*_tools`
2. Call `get_*_tools(...)` directly to get tools dict
3. Access tools via `tools["tool_name"]` instead of `server.tools["tool_name"]`

## Next Steps

1. **Update remaining test files** - Follow the pattern from test_code.py/test_git.py/test_memory.py
2. **Run full test suite** - After all tests updated
3. **Verify with Claude Code** - Restart Claude Code and confirm tools appear as `mcp__learning-memory-server__*`

## Commands to Resume

```bash
# Check current state
.claude/bin/clams-status

# Run tool tests
TOKENIZERS_PARALLELISM=false uv run pytest tests/server/tools/ -v --tb=short

# Run full test suite after fixes
TOKENIZERS_PARALLELISM=false uv run pytest -vvsx --ignore=tests/e2e

# After all tests pass, verify with Claude Code
claude mcp list
```

## Friction Points

- The MCP SDK's dual pattern (call_tool for execution, list_tools for discovery) is non-obvious
- Each @server.call_tool() decorator REPLACES the previous handler - easy to miss in code review
- Tests that mock `server.call_tool` decorator behavior need manual updates when architecture changes
