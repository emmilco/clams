# SPEC-029: Create Canonical Configuration Module

## Overview

Refactor configuration to use a single, top-level `src/clams/config.py` module that re-exports and extends the existing `ServerSettings` from `src/clams/server/config.py`, consolidating scattered constants throughout the codebase.

## Background

### Existing Configuration

The codebase already has `src/clams/server/config.py` which provides:
- `ServerSettings` class using pydantic-settings with `CLAMS_` environment variable prefix
- Organized sections: paths, server, timeouts, Qdrant, embedding, clustering, GHAP, git, logging
- Typed fields with descriptions and environment variable support
- `export_for_shell()` method for shell script integration

### Problem

Additional constants are scattered across the codebase and not centralized:
- `src/clams/context/tokens.py`: `MAX_ITEM_FRACTION`, `SOURCE_WEIGHTS`
- `src/clams/context/deduplication.py`: `SIMILARITY_THRESHOLD`, `MAX_FUZZY_CONTENT_LENGTH`
- `src/clams/server/tools/validation.py`: `PROJECT_ID_MAX_LENGTH`
- `src/clams/indexers/indexer.py`: `EMBEDDING_BATCH_SIZE`
- `src/clams/server/tools/session.py`: `CLAMS_DIR`, `JOURNAL_DIR`
- `src/clams/server/http.py`: `DEFAULT_PID_FILE`, `DEFAULT_LOG_FILE`
- `src/clams/server/tools/code.py`: `max_length` parameter
- `src/clams/server/tools/memory.py`: `max_length` parameter

## Requirements

### Functional Requirements

1. Create `src/clams/config.py` that:
   - Re-exports `ServerSettings` from `src/clams/server/config.py`
   - Adds new settings classes for non-server constants (context, indexer, tools, paths)
   - Provides a root `Settings` class composing all sections
   - Exports a module-level `settings` singleton for convenience
   - Maintains pydantic-settings pattern for consistency
2. Migrate the scattered constants listed above to the new module
3. Update imports throughout codebase to use `clams.config`
4. Deprecate direct imports from `clams.server.config` (re-export for backwards compat)

### Non-Functional Requirements

1. Continue using pydantic-settings for consistency
2. No import-time side effects (lazy loading where needed)
3. Type annotations for all configuration values
4. Documentation for each configuration section

## Acceptance Criteria

- [ ] `src/clams/config.py` exists and re-exports `ServerSettings`
- [ ] New settings classes for: `ContextSettings`, `IndexerSettings`, `ToolSettings`, `PathSettings`
- [ ] Root `Settings` class composing all sections with `settings` singleton
- [ ] All constants listed in Background migrated to appropriate settings class
- [ ] Environment variable support for all settings (with `CLAMS_` prefix)
- [ ] Type annotations on all configuration values
- [ ] Tests verify configuration values are accessible
- [ ] No circular import issues introduced
- [ ] Existing functionality unchanged (config values match current behavior)
- [ ] Imports updated throughout codebase to use `clams.config`

## Out of Scope

- Dynamic configuration reloading
- External configuration files (YAML, TOML)
- Configuration validation framework
