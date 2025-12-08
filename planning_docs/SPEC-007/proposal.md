# SPEC-007: Technical Proposal for Rename

## Overview

This proposal details the comprehensive rename of two systems:
1. **learning-memory-server** → **CLAMS** (Claude Learning and Memory System)
2. **CLAMS workflow** → **CLAWS** (Claude Learning Agent Workflow System)

This is a large-scale, atomic change touching 100+ files across Python code, shell scripts, documentation, and configuration.

## Audit Results

### Memory System Files (learning-memory-server → CLAMS)

**Python Package Structure** (56 files):
```
src/learning_memory_server/  →  src/clams/
├── __init__.py
├── clustering/ (4 files)
├── context/ (7 files)
├── embedding/ (4 files)
├── git/ (4 files)
├── indexers/ (5 files)
├── observation/ (6 files)
├── search/ (4 files)
├── server/ (9 files including tools/)
│   └── tools/ (9 files)
├── storage/ (6 files)
├── values/ (3 files)
└── verification/ (1 file)
```

**Python Files with Import Statements** (estimated 124 imports in tests/ alone):
- All test files: `tests/**/*.py` (import from `learning_memory_server.*`)
- Sample: `from learning_memory_server.embedding import NomicEmbedding`
- Pattern: `from learning_memory_server.{module}.{submodule} import {Class}`

**Configuration Files**:
- `pyproject.toml` (package name, entry point, per-file configs)
- `src/learning_memory_server/server/config.py` (env_prefix, docstrings)
- `tests/server/test_config.py` (test env vars)

**Environment Variables** (LMS_* → CLAMS_*):
- `LMS_QDRANT_URL`
- `LMS_EMBEDDING_MODEL`
- `LMS_LOG_LEVEL`
- `LMS_STORAGE_PATH`
- `LMS_EMBEDDING_DIMENSION`
- `LMS_REPO_PATH`

**Documentation Files**:
- `README.md` (title, references, env vars)
- `GETTING_STARTED.md` (title, all references, env vars)
- `planning_docs/SPEC-002-*/spec.md` and `proposal.md` (historical context - leave most as-is)
- `planning_docs/SPEC-003/` (server name reference)

**MCP Server Registration**:
- `src/learning_memory_server/server/main.py` → server name: `"learning-memory-server"` → `"clams"`
- Test assertion in `tests/server/test_main.py`

### Workflow System Files (CLAMS → CLAWS)

**Shell Scripts** (11 files in `.claude/bin/`):
```
clams-backup      →  claws-backup
clams-common.sh   →  claws-common.sh
clams-counter     →  claws-counter
clams-gate        →  claws-gate
clams-init        →  claws-init
clams-review      →  claws-review
clams-session     →  claws-session
clams-status      →  claws-status
clams-task        →  claws-task
clams-worker      →  claws-worker
clams-worktree    →  claws-worktree
```
Total: ~2800 lines of shell scripts

**Database Path**:
- `.claude/clams.db` → `.claude/claws.db`
- Referenced in: `.claude/bin/clams-common.sh`, `.claude/gates/check_tests.sh`

**Documentation**:
- `CLAUDE.md` (extensive references - ~600 lines, heavy CLAMS usage)
- `.claude/roles/*.md` (15 role files, all have "CLAMS Worker" titles and clams-* command examples)

**Historical Files** (EXCLUDE from rename):
- `.claude/journal/session_entries.jsonl` (historical session logs)
- `changelog.d/*.md` (historical changelogs - mentions of old names are acceptable)
- `tests/fixtures/` (test data files)

## File Manifest

### Memory System (learning-memory-server → CLAMS)

**Must Change**:
1. Directory rename: `src/learning_memory_server/` → `src/clams/` (56 files)
2. All Python imports in `src/` and `tests/` (~150+ import statements)
3. `pyproject.toml`:
   - `name = "learning-memory-server"` → `name = "clams"`
   - `learning-memory-server = "learning_memory_server.server.main:main"` → `clams-server = "clams.server.main:main"`
   - Per-file configs: `"src/learning_memory_server/..."` → `"src/clams/..."`
4. `src/clams/server/config.py`:
   - `env_prefix="LMS_"` → `env_prefix="CLAMS_"`
   - Docstring references
5. `src/clams/server/main.py`:
   - `Server("learning-memory-server")` → `Server("clams")`
   - Logger message: `"learning_memory_server.starting"` → `"clams.starting"`
6. `tests/server/test_main.py`:
   - Assertion: `server.name == "learning-memory-server"` → `server.name == "clams"`
   - All imports
7. `tests/server/test_config.py`:
   - All `"LMS_*"` env var strings
8. All test files with imports (~30+ files)
9. `README.md`:
   - Title: "Learning Memory Server" → "CLAMS - Claude Learning and Memory System"
   - All `LMS_*` env var references → `CLAMS_*`
   - Tool path references
   - Installation commands: `learning-memory-server` → `clams-server`
10. `GETTING_STARTED.md`:
    - Title: "Learning Memory Server: Getting Started" → "CLAMS: Getting Started"
    - All descriptive references
    - All `LMS_*` → `CLAMS_*`
    - All tool path references
    - Command: `learning-memory-server` → `clams-server`

**Keep Historical Context**:
- `planning_docs/SPEC-002-*/`: Add note at top "Note: This spec predates rename; 'learning-memory-server' refers to what is now CLAMS"
- `changelog.d/*.md`: Leave as-is (historical record)

### Workflow System (CLAMS → CLAWS)

**Must Change**:
1. Rename all `.claude/bin/clams-*` → `.claude/bin/claws-*` (11 files)
2. Update internal script references:
   - Source statements: `. "$(dirname "$0")/clams-common.sh"` → `claws-common.sh`
   - Help text mentioning command names
   - Error messages with script names
3. Database path in scripts:
   - `.claude/bin/claws-common.sh`: `DB_PATH="$CLAUDE_DIR/clams.db"` → `DB_PATH="$CLAUDE_DIR/claws.db"`
   - `.claude/gates/check_tests.sh`: Same change
4. `CLAUDE.md` (~600 lines):
   - Title: "CLAMS Orchestrator" → "CLAWS Orchestrator"
   - First paragraph: "CLAMS (Claude Agent Management System)" → "CLAWS (Claude Learning Agent Workflow System)"
   - All command examples: `clams-*` → `claws-*`
   - All prose references to "CLAMS" workflow → "CLAWS"
   - Database path examples: `.claude/clams.db` → `.claude/claws.db`
5. `.claude/roles/*.md` (15 files):
   - Title line: "# CLAMS Worker: {Role}" → "# CLAWS Worker: {Role}"
   - First paragraph mentions of CLAMS system → CLAWS
   - Command examples: `.claude/bin/clams-*` → `.claude/bin/claws-*`
   - Files: `_base.md`, `ai-dl.md`, `architect.md`, `backend.md`, `bug-investigator.md`, `doc-writer.md`, `e2e-runner.md`, `frontend.md`, `infra.md`, `planning.md`, `product.md`, `proposal-reviewer.md`, `qa.md`, `reviewer.md`, `spec-reviewer.md`, `ux.md`

**Do NOT Change**:
- `.claude/journal/session_entries.jsonl`
- Historical `planning_docs/` that mention CLAMS workflow (add clarifying note if needed)

## Implementation Strategy

### Phase 1: Package Rename (Memory System)

**Goal**: Atomically rename the Python package without breaking imports.

**Order of Operations**:
1. **Rename directory first** (git handles this well):
   ```bash
   git mv src/learning_memory_server src/clams
   ```

2. **Update all imports** using batch find-replace:
   ```bash
   # In src/ directory
   find src/clams -name "*.py" -exec sed -i '' \
     's/from learning_memory_server\./from clams./g' {} \;
   find src/clams -name "*.py" -exec sed -i '' \
     's/import learning_memory_server/import clams/g' {} \;

   # In tests/ directory
   find tests -name "*.py" -exec sed -i '' \
     's/from learning_memory_server\./from clams./g' {} \;
   find tests -name "*.py" -exec sed -i '' \
     's/import learning_memory_server/import clams/g' {} \;
   ```

3. **Update pyproject.toml**:
   ```toml
   [project]
   name = "clams"

   [project.scripts]
   clams-server = "clams.server.main:main"

   [tool.ruff.lint.per-file-ignores]
   "src/clams/server/tools/__init__.py" = ["E501"]
   "src/clams/search/searcher.py" = ["E501"]
   ```

4. **Update config.py**:
   ```python
   model_config = SettingsConfigDict(env_prefix="CLAMS_")
   ```
   Also update docstring: "All settings can be overridden via environment variables with CLAMS_ prefix."

5. **Update server name in main.py**:
   ```python
   server = Server("clams")
   logger.info("clams.starting", version="0.1.0")
   ```

6. **Update test files**:
   - `tests/server/test_main.py`: `server.name == "clams"`
   - `tests/server/test_config.py`: All `"LMS_*"` → `"CLAMS_*"`

7. **Verify with mypy and tests**:
   ```bash
   mypy src --strict
   pytest -vvsx
   ```

### Phase 2: Script Rename (Workflow System)

**Goal**: Rename all workflow scripts and update cross-references.

**Order of Operations**:
1. **Rename all scripts atomically** (git mv preserves history):
   ```bash
   cd .claude/bin
   for f in clams-*; do
     git mv "$f" "${f/clams-/claws-}"
   done
   ```

2. **Update source statements** in all scripts:
   ```bash
   cd .claude/bin
   sed -i '' 's/clams-common\.sh/claws-common.sh/g' claws-*
   ```

3. **Update database path** in:
   - `.claude/bin/claws-common.sh`:
     ```bash
     DB_PATH="$CLAUDE_DIR/claws.db"
     ```
   - `.claude/gates/check_tests.sh`:
     ```bash
     DB_PATH="$CLAUDE_DIR/claws.db"
     ```

4. **Update help text and error messages** in scripts (manual review required for each script to catch:
   - Usage examples showing script names
   - Error messages mentioning "clams-*"
   - Comments explaining the system

### Phase 3: Documentation Updates

**Order of Operations**:

1. **README.md**:
   ```markdown
   # CLAMS - Claude Learning and Memory System

   Environment variables:
   - `CLAMS_QDRANT_URL` - Qdrant URL (default: http://localhost:6333)
   - `CLAMS_EMBEDDING_MODEL` - Embedding model (default: nomic-ai/nomic-embed-text-v1.5)
   - `CLAMS_LOG_LEVEL` - Logging level (default: INFO)

   ### Start Server
   clams-server

   ### Available Tools
   See `src/clams/server/tools/` for all MCP tools:
   ```

2. **GETTING_STARTED.md**:
   - Title: "CLAMS: Getting Started"
   - "What Is This?" section: "CLAMS (Claude Learning and Memory System)"
   - Command: `clams-server`
   - Env vars: `CLAMS_*`
   - All paths: `src/clams/...`

3. **CLAUDE.md** (largest change - ~600 lines):
   ```markdown
   # CLAWS Orchestrator

   You are the CLAWS (Claude Learning Agent Workflow System) orchestrator.

   ## Available Tools

   All CLAWS utilities are in `.claude/bin/`.

   **IMPORTANT**: Always run CLAWS commands from the main repository...

   ```bash
   # Database & Status
   .claude/bin/claws-init
   .claude/bin/claws-status
   ...
   ```
   ```

   Strategy: Use find-replace for command examples, but manually review prose to ensure context is correct.

4. **.claude/roles/*.md** (15 files):
   ```markdown
   # CLAWS Worker: {Role Name}

   You are a worker agent in the CLAWS (Claude Learning Agent Workflow System)...

   .claude/bin/claws-review record...
   .claude/bin/claws-gate check...
   ```

### Phase 4: Database Migration

**Goal**: Handle existing `.claude/clams.db` gracefully.

**Approach**: Migration script (optional, for safety):
```bash
#!/bin/bash
# .claude/bin/migrate-clams-to-claws.sh

if [ -f .claude/clams.db ] && [ ! -f .claude/claws.db ]; then
    echo "Migrating database: clams.db → claws.db"
    cp .claude/clams.db .claude/claws.db
    echo "Migration complete. Old clams.db preserved for safety."
    echo "Once verified, you can remove: rm .claude/clams.db"
fi
```

**Alternative** (simpler): Just rename it:
```bash
git mv .claude/clams.db .claude/claws.db
```

**Recommendation**: Simple rename with git mv, since this is a greenfield system with no external users.

### Phase 5: Verification

**Goal**: Ensure zero orphaned references and all functionality works.

**Automated Checks**:
```bash
# 1. Check for orphaned "learning" references (exclude git/historical)
grep -ri "learning.memory\|learning_memory" \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" \
  . | grep -v ".git" | grep -v "changelog.d" | grep -v "planning_docs/SPEC-002"

# 2. Check for orphaned LMS_ references
grep -ri "LMS_" \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" \
  . | grep -v ".git" | grep -v "changelog.d"

# 3. Check for old CLAMS workflow references (context-sensitive - may have false positives)
grep -ri "clams-" \
  --include="*.md" --include="*.sh" \
  . | grep -v ".git" | grep -v "changelog.d"

# 4. Verify no old script files remain
ls .claude/bin/clams-* 2>/dev/null && echo "ERROR: Old clams-* scripts still exist!"

# 5. Verify database path is updated
grep -r "clams\.db" .claude/bin .claude/gates
```

**Functional Tests**:
```bash
# 1. Type checking
mypy src --strict

# 2. Linting
ruff check src tests

# 3. Full test suite
pytest -vvsx

# 4. MCP server registration
clams-server &  # Should register as "clams" MCP server
sleep 5
pkill -f clams-server

# 5. Workflow commands
.claude/bin/claws-status health
.claude/bin/claws-task list
```

**Manual Verification**:
1. Read `CLAUDE.md` for clarity and consistency
2. Spot-check role files
3. Review README and GETTING_STARTED for clarity
4. Check a sample planning doc for historical note placement

## Risk Mitigation

### Risk 1: Missed References

**Likelihood**: Medium
**Impact**: High (broken functionality)
**Mitigation**:
- Comprehensive grep audit (done above)
- Automated verification script
- Full test suite must pass
- Manual spot-checks of key files

### Risk 2: Broken Imports

**Likelihood**: Low (git mv handles well)
**Impact**: High (package unusable)
**Mitigation**:
- Use git mv to preserve history
- Batch sed replacements with verification
- mypy --strict type checking
- Full pytest run

### Risk 3: Script Cross-References

**Likelihood**: Medium (scripts source each other)
**Impact**: Medium (workflow breaks)
**Mitigation**:
- Update all source statements first
- Test each script individually
- Database path updated in common.sh (single source of truth)

### Risk 4: Database Path Confusion

**Likelihood**: Low
**Impact**: Medium (tasks/workers lost)
**Mitigation**:
- Simple rename (git mv)
- Update both .claude/bin/claws-common.sh and .claude/gates/check_tests.sh
- Verify grep shows no clams.db references

### Risk 5: Documentation Inconsistency

**Likelihood**: Medium
**Impact**: Low (confusion, not breakage)
**Mitigation**:
- Add historical notes to old planning docs
- Manual review of CLAUDE.md and GETTING_STARTED.md
- Consistent find-replace patterns

## Implementation Order (Recommended)

1. **Create feature branch** (if desired for safety):
   ```bash
   git checkout -b rename-clams-claws
   ```

2. **Phase 1: Package rename** (most critical, atomic):
   - Rename directory: `git mv src/learning_memory_server src/clams`
   - Update all imports (find-replace)
   - Update pyproject.toml
   - Update config.py env_prefix
   - Update server name in main.py
   - Update test assertions and env vars
   - **VERIFY**: `mypy src --strict && pytest -vvsx`

3. **Phase 2: Script rename**:
   - Rename all scripts: `git mv clams-* claws-*`
   - Update source statements
   - Update database path
   - Update help text (manual)
   - **VERIFY**: `.claude/bin/claws-status` works

4. **Phase 3: Documentation**:
   - Update README.md
   - Update GETTING_STARTED.md
   - Update CLAUDE.md (large, careful review)
   - Update all .claude/roles/*.md
   - Add historical notes to planning docs
   - **VERIFY**: Manual readthrough for clarity

5. **Phase 4: Database migration**:
   - Rename: `git mv .claude/clams.db .claude/claws.db`
   - **VERIFY**: Scripts reference correct path

6. **Phase 5: Final verification**:
   - Run all grep checks (zero orphans)
   - Run all functional tests
   - Manually test MCP server and workflow commands
   - Review CLAUDE.md one more time

7. **Commit**:
   ```bash
   git add -A
   git commit -m "SPEC-007: Rename systems to CLAMS and CLAWS"
   ```

## Files Summary

**Total files affected**: ~150+

**Breakdown**:
- Python package files: 56 (directory rename)
- Python import statements: ~150+ (find-replace)
- Shell scripts: 11 (rename + internal updates)
- Gate scripts: 1 (database path)
- Config files: 1 (pyproject.toml)
- Documentation: ~20 (.md files)
- Test files: ~30

**Historical files preserved**: ~50+ (changelogs, old planning docs, session logs)

## Verification Commands Summary

```bash
# Post-implementation verification checklist

# 1. No orphaned learning-memory-server references
! grep -ri "learning.memory\|learning_memory" \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" \
  . | grep -v ".git" | grep -v "changelog.d" | grep -v "planning_docs/SPEC-002"

# 2. No orphaned LMS_ env vars
! grep -ri "LMS_" \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" \
  . | grep -v ".git" | grep -v "changelog.d"

# 3. No old script files
! ls .claude/bin/clams-* 2>/dev/null

# 4. No old database references
! grep -r "clams\.db" .claude/bin .claude/gates

# 5. Package works
mypy src --strict
ruff check src tests
pytest -vvsx

# 6. MCP server registers correctly
clams-server &
sleep 5
pkill -f clams-server

# 7. Workflow commands work
.claude/bin/claws-status health
.claude/bin/claws-task list
```

## Concerns and Open Questions

### 1. Historical Planning Docs

**Question**: Should we add a note to ALL SPEC-002-* planning docs, or just leave them as historical context?

**Recommendation**: Add a single-line note at the top of each SPEC-002-*/spec.md and proposal.md:
```markdown
> **Note**: This spec predates the SPEC-007 rename. References to "learning-memory-server" now refer to CLAMS (Claude Learning and Memory System).
```

**Reasoning**: Minimal disruption, preserves history, adds clarity for future readers.

### 2. Entry Point Name

**Question**: Should the CLI command be `clams` or `clams-server`?

**Current**: `learning-memory-server` (single command)
**Proposed**: `clams-server` (more explicit, avoids confusion with CLAWS)

**Reasoning**:
- `clams` is ambiguous (could refer to workflow system)
- `clams-server` is explicit (it's the MCP server for CLAMS)
- Consistent with MCP naming patterns

### 3. MCP Server Name vs Package Name

**Question**: Should MCP server register as "clams" or "clams-server"?

**Recommendation**: Register as `"clams"` (short, memorable for MCP configs)

**Reasoning**:
- MCP config files reference server by name
- Short names are better for UX
- Package name can differ from server registration name
- Matches spec requirement: "MCP Server: Server must register as `clams` (short, memorable)"

### 4. Gradual vs Atomic Rollout

**Question**: Can this be done in multiple commits, or must it be atomic?

**Recommendation**: Single atomic commit (preferred)

**Reasoning**:
- Package rename breaks imports if done incrementally
- Scripts reference each other (must rename together)
- Easier to review as one change
- Easier to revert if needed
- Matches greenfield "refactor freely" principle

**Alternative**: If desired, could split into 2 commits:
1. Memory system rename (package + tests + docs)
2. Workflow system rename (scripts + CLAUDE.md + roles)

But even this has risk of confusion during the in-between state.

## Implementation Complexity Estimate

**Total effort**: ~4-6 hours

**Breakdown**:
- Phase 1 (Package): 1-2 hours (careful find-replace, verification)
- Phase 2 (Scripts): 1 hour (rename + update internals)
- Phase 3 (Docs): 2-3 hours (CLAUDE.md is large, requires careful review)
- Phase 4 (Database): 15 minutes (simple rename)
- Phase 5 (Verification): 30-60 minutes (run all checks, manual testing)

**Automation potential**: High for phases 1, 2, 4. Manual review required for phase 3.

## Success Criteria

1. All imports work: `mypy src --strict` passes
2. All tests pass: `pytest -vvsx` succeeds
3. MCP server starts: `clams-server` runs and registers as "clams"
4. Workflow commands work: `claws-status`, `claws-task`, etc. all function
5. Zero orphaned references: grep checks return empty
6. Documentation is clear: CLAUDE.md, README.md, GETTING_STARTED.md read naturally
7. Historical context preserved: Old planning docs have clarifying notes

## Next Steps

After proposal approval:
1. Human reviews this proposal
2. Architect makes any requested changes
3. Human approves proposal
4. Implementation proceeds (Backend specialist or Orchestrator)
5. Gate check verifies all tests pass and no orphaned references
6. Merge to main
