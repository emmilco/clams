## SPEC-025: Production Command Verification in Tests

### Summary
Ensures integration tests use the same commands as production hooks to prevent "works in test, fails in production" scenarios.

### Changes
- Added `get_server_command()` utility in tests/conftest.py that returns canonical server commands
- Supports both module invocation and binary entry point styles
- Updated integration tests to use this utility for consistency with production hooks
- Added comments documenting command parity requirements
