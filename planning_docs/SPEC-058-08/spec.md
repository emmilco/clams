# SPEC-058-08: CALM Cleanup - Remove Deprecated Code

## Overview

Remove all deprecated CLAMS/CLAWS code from the repository now that CALM is fully implemented (SPEC-058-01 through 058-07 complete). This is a deletion-focused task - no new code is written, only removal and reference updates.

**Precondition**: CALM is fully implemented and the cutover script exists. The old CLAWS bash scripts are still being used for orchestration during this task.

**Postcondition**: All old CLAMS/CLAWS code is removed. Only CALM code remains. The cutover script (`scripts/cutover.py`) and old databases are preserved for post-cleanup migration.

## CRITICAL: Do NOT Delete

The following must be **preserved** - they are needed by the cutover script (`scripts/cutover.py`) which runs AFTER this cleanup:

- **`.claude/claws.db`** - Old orchestration database (migration source)
- **`~/.clams/metadata.db`** - Old CLAMS metadata (migration source)
- **`scripts/cutover.py`** - The migration script itself
- **`tests/test_cutover.py`** - Migration tests
- **`.claude/bin/claws-*` scripts** - Still actively used for orchestration during this task (deleted only AFTER cutover runs)
- **`clams_scripts/hooks/`** - Still referenced by `~/.claude/settings.json` hooks (cleaned by cutover script)

**Rationale**: The cutover script reads from `.claude/claws.db` and `~/.clams/metadata.db` to migrate data into `~/.calm/metadata.db`. If we delete these before running the cutover, we lose all orchestration history (135+ tasks, reviews, test runs, counters).

## Scope

### What to Delete

1. **`src/clams/`** - The entire old Python package (~50 source files, ~170 pycache files across 14 subdirectories)

2. **`.claude/roles/`** - Old role files (16 files). These now live in `~/.calm/roles/` (copied by the install script).

3. **`.claude/hooks/`** - Old hook stubs (3 Python files + pycache):
   - `check_hash_eq.py`
   - `check_heavy_imports.py`
   - `check_subprocess.py`

### What to Update

4. **`pyproject.toml`** - Remove old package references:
   - Remove `clams-server = "clams.server.main:main"` entry point (or keep only if calm entry point exists)
   - Remove `"src/clams"` from `packages` list (keep `"src/calm"`)
   - Remove ruff per-file-ignores for `src/clams/` paths
   - Remove mypy overrides for `clams.*`
   - Update package name if appropriate

5. **`tests/conftest.py`** - Remove imports from `clams` package. Update to import from `calm` if equivalent functionality exists, or remove if no longer needed.

6. **Old test files** - Any test files that ONLY test `src/clams/` code and have no `src/calm/` equivalent should be removed. Test files that test functionality now in `src/calm/` should be updated to import from `calm`.

7. **`.claude/settings.local.json`** - Remove allowlist entries referencing `.claude/bin/claws-*` commands and `mcp__clams__*` tools (these are local permission settings, not hook configuration).

### What NOT to Delete (deferred to post-cutover)

- `.claude/bin/claws-*` scripts - Still used for orchestration
- `clams_scripts/` - Still referenced by active hooks in `~/.claude/settings.json`
- `.claude/claws.db` - Migration source
- Any documentation in `planning_docs/` or `changelog.d/` (historical records)

## Detailed Requirements

### 1. Remove `src/clams/`

Delete the entire directory tree. This includes:
- `src/clams/__init__.py`, `__main__.py`, `config.py`
- `src/clams/server/` (MCP server, tools, main)
- `src/clams/storage/` (Qdrant client)
- `src/clams/embedding/` (embedding models)
- `src/clams/indexers/` (code/git indexing)
- `src/clams/search/` (semantic search)
- `src/clams/context/` (context assembly)
- `src/clams/clustering/` (experience clustering)
- `src/clams/values/` (value management)
- `src/clams/git/` (git operations)
- `src/clams/observation/` (GHAP tracking)
- `src/clams/utils/` (utilities)
- `src/clams/verification/` (verification)
- All `__pycache__/` directories

### 2. Remove `.claude/roles/`

Delete all 16 role files. These are now managed at `~/.calm/roles/` by the CALM install script.

### 3. Remove `.claude/hooks/`

Delete the 3 hook stub files and pycache. These are pre-implementation stubs that are not used by the active hook system.

### 4. Update `pyproject.toml`

- Remove `"src/clams"` from the `packages` list
- Remove the `clams-server` entry point
- Remove any ruff or mypy configuration specific to `src/clams/`
- Keep the package name as-is for now (changing the package name is a separate concern)

### 5. Update Test Infrastructure

- Update `tests/conftest.py` to remove `from clams.utils.platform import ...` and any other clams imports
- Identify test files that exclusively test `src/clams/` code (not `src/calm/`)
- Remove those test files
- For any shared test infrastructure that imports from clams, update to import from calm

### 6. Update `.claude/settings.local.json`

Remove allowlist entries for old commands. This file contains permission settings - stale entries are harmless but messy.

## Acceptance Criteria

- [ ] `src/clams/` directory is completely removed
- [ ] `.claude/roles/` directory is completely removed
- [ ] `.claude/hooks/check_*.py` files are removed
- [ ] `pyproject.toml` no longer references `src/clams` in packages list
- [ ] `pyproject.toml` no longer has `clams-server` entry point
- [ ] `tests/conftest.py` does not import from `clams`
- [ ] No test files import from `clams` (only `calm`)
- [ ] All remaining tests pass (both old tests updated to `calm` imports and new `calm` tests)
- [ ] Linter passes
- [ ] Type checker passes
- [ ] `.claude/claws.db` is NOT deleted (preserved for cutover)
- [ ] `scripts/cutover.py` is NOT deleted
- [ ] `.claude/bin/claws-*` scripts are NOT deleted (still in active use)
- [ ] `clams_scripts/` is NOT deleted (still referenced by hooks)

## Non-Goals

- Writing new code or features
- Running the cutover script (that's a manual step after this task)
- Deleting `.claude/bin/claws-*` or `clams_scripts/` (deferred to post-cutover)
- Changing the repository name
- Updating external documentation

## Technical Notes

- The test suite currently has ~2923 tests. Many of these test `src/clams/` functionality. After removing `src/clams/`, we expect a significant reduction in test count. The remaining tests (testing `src/calm/` and shared utilities) must all pass.
- The `conftest.py` import of `clams.utils.platform` is used by test fixtures. Check if `calm.utils` has an equivalent, or if the fixture can be simplified.
- After this cleanup, the repository will have a single Python package: `src/calm/`.
