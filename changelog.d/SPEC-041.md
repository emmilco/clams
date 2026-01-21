## SPEC-041: Shell/Hooks Gate Check Script Enhancements

### Summary
Enhanced the shell linter gate script with bash -n syntax checking, severity filtering, and changed-only mode.

### Changes
- Added `bash -n` syntax checking before shellcheck
- Added `-S warning` severity threshold to shellcheck
- Added `CHECK_CHANGED_ONLY=1` environment variable for checking only changed files
- Added `clams/hooks/` to default script directories
- Improved exit code handling and error messages
