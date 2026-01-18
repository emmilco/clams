## SPEC-030: Cold-Start Testing Protocol

### Summary
Add comprehensive cold-start testing infrastructure to catch bugs that only manifest on first use when no collections or data exist (addressing patterns from BUG-016 and BUG-043).

### Changes
- Added `tests/cold_start/` package with tests for memory, git, GHAP, and values operations
- Added `cold_start` pytest marker for selective test execution
- Added `cold_start_qdrant` and `cold_start_db` fixtures in tests/fixtures/cold_start.py
- Tests verify graceful handling of empty collections (no 404 errors, proper empty results)
- 53 new cold-start tests covering all major MCP tool operations
