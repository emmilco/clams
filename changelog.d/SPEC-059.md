## SPEC-059: Backup Rotation with Configurable Max Count

### Summary
Prevent unbounded backup accumulation by enforcing a maximum backup count and automatically deleting the oldest backups when the limit is exceeded.

### Changes
- Added `max_backups` setting to `CalmSettings` (default: 10, configurable via `CALM_MAX_BACKUPS` env var)
- Added `rotate_backups(max_backups)` function that deletes oldest backups (both SQLite and Qdrant snapshots) when count exceeds limit
- `create_backup()` now calls `rotate_backups()` after each backup creation
- Updated `calm backup list` CLI to show "N of M backups (max: M)" header
- Added tests for rotation logic, config setting, and CLI output
