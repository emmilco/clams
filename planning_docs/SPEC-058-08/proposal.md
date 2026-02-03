# SPEC-058-08: Technical Proposal - CALM Cleanup

## Approach

This is a pure deletion and reference-update task. No new features are written. The work proceeds in a carefully ordered sequence: first remove source code, then remove stale configuration entries, then remove test files that exclusively test removed code, then update shared test infrastructure, and finally verify everything passes.

The ordering is designed so that each step produces a state that can be independently verified before moving on, and so that the riskiest changes (removing source) happen first when rollback is cheapest.

## Execution Order

1. **Remove `src/clams/`** -- the root cause of all downstream cleanup. Everything else depends on this being gone.
2. **Remove `.claude/roles/`** -- independent of source code, simple directory deletion.
3. **Remove `.claude/hooks/`** -- independent of source code, simple file deletion.
4. **Update `pyproject.toml`** -- must happen after `src/clams/` is removed, because the build system will fail if it references a nonexistent package directory. Also removes stale ruff per-file-ignores for test files deleted in step 5.
5. **Remove clams-only test files** -- must happen after `src/clams/` removal, since these tests will fail with import errors. Removing them restores test collection. Includes `tests/utils/` (7 files, all clams-only).
6. **Update `tests/conftest.py`** -- must happen after step 5, since conftest imports `clams.utils.platform` which no longer exists. The `PlatformInfo` and `get_platform_info` functionality must be either moved to `calm.utils.platform` or inlined into conftest, since it is still needed by the test platform-skip infrastructure.
7. **Address `.claude/settings.local.json`** -- spec item 7 requires this, but the file does not exist in the worktree. No action needed.
8. **Verify** -- run the full test suite, linter, and type checker on the remaining codebase.

## Step 1: Remove `src/clams/`

### What
Delete the entire `src/clams/` directory tree. This contains 74 Python source files across 14 subdirectories (clustering, config, context, embedding, git, indexers, observation, search, server, storage, utils, values, verification, plus `__init__.py` and `config.py` at the top level).

### Files Affected
- `src/clams/` -- entire directory tree (recursive delete)

### Do NOT Delete
- `src/calm/` -- the replacement package, must remain untouched

### Verification
- `ls src/clams` returns "No such file or directory"
- `ls src/calm/__init__.py` still exists
- `python -c "import calm"` succeeds (from the repo root, with the venv)

## Step 2: Remove `.claude/roles/`

### What
Delete all 16 role files. These files are now managed at `~/.calm/roles/` by the CALM install script (SPEC-058-01).

### Files Affected
- `.claude/roles/` -- entire directory (16 files: `_base.md`, `ai-dl.md`, `architect.md`, `backend.md`, `bug-investigator.md`, `doc-writer.md`, `e2e-runner.md`, `frontend.md`, `infra.md`, `planning.md`, `product.md`, `proposal-reviewer.md`, `qa.md`, `reviewer.md`, `spec-reviewer.md`, `ux.md`)

### Verification
- `ls .claude/roles/` returns "No such file or directory"
- `ls ~/.calm/roles/` still contains the role files (external to repo, unaffected)

## Step 3: Remove `.claude/hooks/`

### What
Delete the 3 hook stub files. These are pre-implementation stubs that were never integrated into the active hook system (the active hooks live in `clams_scripts/hooks/` which is preserved).

### Files Affected
- `.claude/hooks/check_hash_eq.py`
- `.claude/hooks/check_heavy_imports.py`
- `.claude/hooks/check_subprocess.py`
- `.claude/hooks/__pycache__/` (if exists)
- The `.claude/hooks/` directory itself

### Do NOT Delete
- `clams_scripts/hooks/` -- still referenced by `~/.claude/settings.json` active hooks

### Verification
- `ls .claude/hooks/` returns "No such file or directory"
- `.claude/claws.db` still exists (verify we did not accidentally remove sibling files)
- `.claude/bin/` still exists with all `claws-*` scripts

## Step 4: Update `pyproject.toml`

### What
Remove all references to the `clams` package from the build and tool configuration.

### Changes

1. **Remove `clams-server` entry point** (line 51): Delete `clams-server = "clams.server.main:main"`. Keep `calm = "calm.cli.main:cli"`.

2. **Remove `"src/clams"` from packages list** (line 55): Change `packages = ["src/clams", "src/calm"]` to `packages = ["src/calm"]`.

3. **Remove ruff per-file-ignores for `src/clams/` paths** (lines 75, 78): Delete the entries for `"src/clams/server/tools/__init__.py"` and `"src/clams/search/searcher.py"`.

4. **Remove stale ruff per-file-ignores for deleted test files** (lines 80-83): Delete the entries for `"tests/integration/test_e2e.py"`, `"tests/integration/test_data_flows.py"`, `"tests/integration/test_round_trip.py"`, and `"tests/test_bug_006_experience_schema.py"`. These test files are removed in Step 5, so their per-file-ignores are stale.

5. **Remove `clams.*` from mypy overrides** (line 95): Change `module = ["structlog", "mcp.*", "aiofiles", "hdbscan", "clams.*", "calm.*"]` to remove `"clams.*"`.

### Files Affected
- `pyproject.toml`

### Verification
- `grep -r "src/clams" pyproject.toml` returns nothing
- `grep "clams-server" pyproject.toml` returns nothing
- `grep "clams\.\*" pyproject.toml` returns nothing
- `grep "test_e2e\|test_data_flows\|test_round_trip\|test_bug_006" pyproject.toml` returns nothing
- `python -m build --wheel` succeeds (or at minimum, `pip install -e .` succeeds)

## Step 5: Remove Clams-Only Test Files

### What
Remove test files and directories that exclusively test `src/clams/` code. These tests will fail with `ModuleNotFoundError` after Step 1 and serve no purpose once the source is gone.

There are 118 test files that import from `clams` but NOT from `calm`. These need to be categorized:

**Test directories to delete entirely** (mirror `src/clams/` subpackages):
- `tests/clustering/` -- tests `clams.clustering`
- `tests/context/` -- tests `clams.context`
- `tests/embedding/` -- tests `clams.embedding`
- `tests/git/` -- tests `clams.git`
- `tests/indexers/` -- tests `clams.indexers`
- `tests/observation/` -- tests `clams.observation`
- `tests/search/` -- tests `clams.search`
- `tests/server/` -- tests `clams.server` (NOT `tests/calm/` which tests `calm.server`)
- `tests/storage/` -- tests `clams.storage`
- `tests/utils/` -- tests `clams.utils` (7 files, all import exclusively from `clams`)
- `tests/values/` -- tests `clams.values`

**Test directories/files to delete** (clams-focused integration/infrastructure tests):
- `tests/integration/` -- all 6 files import exclusively from `clams`
- `tests/infrastructure/` -- all 6 files import exclusively from `clams`
- `tests/validation/` -- all files import exclusively from `clams`
- `tests/cold_start/` -- all files import from `clams`
- `tests/performance/` -- all files import from `clams`
- `tests/bugs/` -- imports from `clams`
- `tests/unit/` -- imports from `clams`

**Standalone test files to delete**:
- `tests/test_bug_006_experience_schema.py` -- imports from `clams`

**Test files/dirs to KEEP** (they test `calm` or are infrastructure):
- `tests/calm/` -- tests `calm` package
- `tests/test_cutover.py` -- tests cutover script (must be preserved per spec)
- `tests/conftest.py` -- shared infrastructure (updated in Step 6)
- `tests/fixtures/` -- needs review; `cold_start.py` and `generators/ghap.py` import from `clams`, `test_cold_start_fixtures.py` imports from `clams`. These should be removed IF they are only used by clams tests. The `tests/fixtures/code_samples/` subdirectory (if it exists) may be needed by calm tests.
- `tests/checks/` -- review if imports from clams
- `tests/gates/` -- review if imports from clams
- `tests/hooks/` -- review if imports from clams
- `tests/scripts/` -- review if imports from clams
- `tests/test_bug_052_regression.py`, `tests/test_bug_055_regression.py`, `tests/test_bug_057_regression.py`, `tests/test_bug_061_centralized_dirs.py` -- review individually
- `tests/test_gate_dispatch.py`, `tests/test_json_merge.py`, `tests/test_placeholder.py` -- review individually
- `tests/test_install/` -- imports from `calm`, keep

**Important**: The implementer must check each file/directory before deletion. The rule is simple: if it imports from `clams` and has no `calm` equivalent or shared use, delete it. If it imports from both or only from `calm`, keep it.

### Files Affected
- ~25 test directories/files removed (see list above)
- Estimated removal of ~100+ test files

### Verification
- `grep -r "from clams\." tests/` returns only matches in `tests/conftest.py` (which is fixed in Step 6) and possibly `tests/fixtures/` (which may need cleanup)
- `python -m pytest --collect-only` succeeds (no import errors during collection)

## Step 6: Update `tests/conftest.py` and Shared Test Infrastructure

### What
The `tests/conftest.py` file imports `PlatformInfo` and `get_platform_info` from `clams.utils.platform`. This module provides platform detection (OS, GPU, Docker, Qdrant, ripgrep) used by the conftest's `pytest_collection_modifyitems` hook to skip tests based on platform capabilities.

This functionality is still needed by the remaining `calm` tests (some have `@pytest.mark.requires_qdrant` etc.). The implementer must:

1. **Move `clams.utils.platform` to `calm.utils.platform`**: Copy the `PlatformInfo` dataclass and `get_platform_info()` function into `src/calm/utils/platform.py`. This is a straightforward copy since the module has no internal `clams` dependencies (it only uses stdlib and optional torch import).

2. **Update conftest import**: Change `from clams.utils.platform import PlatformInfo, get_platform_info` to `from calm.utils.platform import PlatformInfo, get_platform_info`.

3. **Remove `get_server_command` function**: This function references `clams-server` and `clams.server.main` which no longer exist. If any remaining tests use it, they need to be updated to reference `calm` equivalents. If no remaining tests use it, simply delete it.

4. **Remove cold-start fixture imports**: The `from tests.fixtures.cold_start import ...` block (lines 97-107) imports fixtures that are used by clams tests. If `tests/fixtures/cold_start.py` is deleted in Step 5, this import must be removed. If any calm tests use these fixtures, the fixtures must be updated to import from `calm` instead.

### Files Affected
- `src/calm/utils/platform.py` (new file -- move from `clams.utils.platform`)
- `src/calm/utils/__init__.py` (may need update)
- `tests/conftest.py` (import updates, function removal)
- `tests/fixtures/cold_start.py` (delete or update)

### Verification
- `python -c "from calm.utils.platform import PlatformInfo, get_platform_info"` succeeds
- `grep -r "from clams" tests/conftest.py` returns nothing
- `pytest --collect-only` succeeds with no import errors

## Step 7: Address `.claude/settings.local.json`

### What
The spec (item 7) requires removing stale allowlist entries from `.claude/settings.local.json`. This file does **not exist** in the worktree (verified by `ls`). No action is needed for this item -- there are no stale entries to remove because the file is absent.

### Files Affected
- None (file does not exist)

### Verification
- `ls .claude/settings.local.json` returns "No such file or directory"

## Step 8: Verify Preserved Files

### What
Explicitly verify that files marked as "do NOT delete" in the spec are still present.

### Checklist
- `.claude/claws.db` exists
- `scripts/cutover.py` exists
- `tests/test_cutover.py` exists
- `.claude/bin/claws-*` scripts all exist (12 files: `claws-backup`, `claws-common.sh`, `claws-counter`, `claws-gate`, `claws-gate-dispatch`, `claws-init`, `claws-review`, `claws-session`, `claws-status`, `claws-task`, `claws-worker`, `claws-worktree`)
- `clams_scripts/hooks/` directory exists
- `planning_docs/` and `changelog.d/` directories exist

### Verification
- Each file/directory is confirmed present via `ls` or `test -f`/`test -d`

## Risks and Mitigations

### Risk 1: Deleting a test file that is actually needed by calm tests
**Likelihood**: Low-Medium. Some test fixtures or utility files may be shared.
**Mitigation**: The implementer must check imports in BOTH directions before deleting any test file. Run `pytest --collect-only` after each batch of deletions to catch import errors immediately. If a shared fixture is found, move it to `tests/calm/` or `tests/fixtures/` and update imports.

### Risk 2: PlatformInfo move introduces subtle behavior change
**Likelihood**: Very low. The `clams.utils.platform` module is self-contained (stdlib only, optional torch).
**Mitigation**: The move is a literal copy. Run the platform-related tests after the move to verify behavior is identical. The only change needed is updating the `CLAMS_QDRANT_URL` env var reference to `CALM_QDRANT_URL` (or keeping both for compatibility).

### Risk 3: Accidentally deleting preserved files
**Likelihood**: Low. The spec clearly lists what must be preserved.
**Mitigation**: Step 8 is an explicit verification step. The implementer should also use `git diff --stat` before committing to review exactly what was deleted.

### Risk 4: conftest.py cold-start fixture removal breaks calm tests
**Likelihood**: Medium. The cold-start fixtures (`cold_start_db`, `cold_start_env`, etc.) may be used by `tests/calm/` tests.
**Mitigation**: Before removing the fixture imports, grep `tests/calm/` for usage of each fixture name. If any are used, keep the fixture file and update its imports from `clams` to `calm`.

### Risk 5: `get_server_command` removal breaks remaining tests
**Likelihood**: Low-Medium. Need to check if any calm tests or test_cutover use this function.
**Mitigation**: Grep all remaining test files for `get_server_command` before removing it. If used, update it to reference `calm` equivalents.

## Test Strategy

### During Implementation
1. After each step, run `pytest --collect-only 2>&1 | tail -20` to verify test collection does not crash with import errors.
2. After Steps 1-6 are complete, run the full test suite: `pytest -x --timeout=60`
3. Run the linter: `ruff check src/calm/ tests/`
4. Run the type checker: `mypy --strict src/calm/`

### Final Verification
1. Full test suite passes with zero import errors
2. `ruff check` passes clean
3. `mypy --strict src/calm/` passes clean
4. `grep -r "from clams\." src/ tests/` returns zero matches (excluding `tests/test_cutover.py` which legitimately references old module paths in its test logic)
5. All preserved files confirmed present (Step 8 checklist)
6. `git diff --stat` shows only deletions and the expected edits to `pyproject.toml`, `conftest.py`, and new `calm/utils/platform.py`
