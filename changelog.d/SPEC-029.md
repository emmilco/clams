## SPEC-029: Canonical Configuration Module

### Summary
Centralizes all configuration in ServerSettings as the single source of truth, with shell export capability for hooks and scripts.

### Changes
- Extended `src/clams/server/config.py` ServerSettings with pid_file, log_file, and all timeout values
- Added `export_for_shell()` method to generate sourceable config.env files
- Server writes config to `~/.clams/config.env` on startup for shell scripts to source
- Collection names remain in CollectionName class (imported for shell export)
- Removed duplicate StorageSettings class and inline configuration values
- Updated hook scripts to source configuration from config.env
- Added tests verifying shell export round-trips correctly

### References
- Related bugs: BUG-033, BUG-037, BUG-023, BUG-026, BUG-061
