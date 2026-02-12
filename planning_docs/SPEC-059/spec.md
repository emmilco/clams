# SPEC-059: Backup Rotation with Configurable Max Count

## Problem

Backups accumulate indefinitely with no automatic cleanup, consuming disk space over time.

## Requirements

1. Add a `max_backups` config setting (default: 10) to `CalmSettings` in `src/calm/config.py`
2. After each backup creation in `create_backup()`, check total backup count and delete oldest backups (by creation timestamp) until count equals `max_backups`
3. The `calm backup list` CLI should show the backup count and configured limit
4. A `calm backup delete <name>` CLI subcommand for manual deletion (already existed)

## Acceptance Criteria

- [ ] `CalmSettings.max_backups` field exists with default value 10
- [ ] `max_backups` is configurable via `CALM_MAX_BACKUPS` environment variable
- [ ] `rotate_backups(max_backups)` function exists and deletes oldest backups when count exceeds limit
- [ ] `rotate_backups()` removes both SQLite backup files and Qdrant snapshot directories
- [ ] `create_backup()` calls `rotate_backups()` after each backup creation
- [ ] Creating 12 backups with max=10 results in exactly 10 remaining (the newest 10)
- [ ] `calm backup list` output shows "N of M backups (max: M)" header
- [ ] Empty backup list shows "(max: M)" in the output
- [ ] `rotate_backups()` raises `ValueError` when max_backups < 1
- [ ] All existing backup tests continue to pass
- [ ] New tests cover rotation, config, and CLI output
