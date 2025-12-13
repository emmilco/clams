## SPEC-008: HTTP Transport for Singleton MCP Server

### Summary
Implemented HTTP transport for the MCP server, enabling hooks to connect to a shared daemon instead of spawning new processes. This fixes the fundamental architecture issue where hooks were spawning separate MCP servers (10+ seconds each) and calling non-existent tools.

### Changes
- Added HTTP+SSE transport support using Starlette (`src/clams/server/http.py`)
- Added `/api/call` endpoint for direct tool invocation by hook scripts (bypasses SSE session requirement)
- Added `/health` endpoint for daemon health checks
- Implemented daemon mode with PID file management (`~/.clams/server.pid`)
- Implemented missing session tools:
  - `start_session`: Initialize session, return ID
  - `get_orphaned_ghap`: Detect GHAP from previous session
  - `should_check_in`: Check if GHAP reminder is due
  - `increment_tool_count` / `reset_tool_count`: Track tool usage
- Implemented `assemble_context` tool for context injection
- Updated all 4 hook scripts to use HTTP transport via `/api/call`:
  - `session_start.sh`: Non-blocking, starts daemon in background
  - `user_prompt_submit.sh`: Blocking wait for server, assembles context
  - `ghap_checkin.sh`: Quick 1s timeout for GHAP reminders
  - `outcome_capture.sh`: Captures test/build outcomes
- Updated `install.sh` to start daemon and configure HTTP transport
- Updated `uninstall.sh` to stop daemon and clean up

### Performance
- Session start hook: < 100ms (non-blocking, daemon starts in background)
- User prompt submit: < 200ms (after server warm)
- GHAP checkin/outcome capture: < 200ms with 1s timeout fallback
- Models load once at daemon startup, stay in memory
