## SPEC-003: Optimize MCP protocol test performance

### Summary
Reduced MCP protocol test execution time from ~130 seconds to ~8 seconds (17x improvement) by eliminating redundant server startups and embedding model loads.

### Changes
- Changed `mcp_session` test fixture from function-scoped to module-scoped, reducing server startups from 10 to 1 per test run
- Added `create_embedding_service()` function in `main.py` to load the embedding model once at startup
- Refactored initialization chain to pass embedding service through `run_server()`, `create_server()`, `register_all_tools()`, and `initialize_services()`
- Removed duplicate model loading from `validate_configuration()` and `initialize_services()`
- Added unit test for `create_embedding_service()` function
