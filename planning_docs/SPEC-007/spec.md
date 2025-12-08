# SPEC-007: Rename Systems to CLAMS and CLAWS

## Problem Statement

The project currently contains two systems with unclear naming:

1. **learning-memory-server**: An MCP server providing semantic memory, code indexing, git analysis, GHAP tracking, and value formation
2. **CLAMS**: An agent orchestration workflow system for coordinating AI workers (currently "Claude Agent Management System")

The current names don't clearly communicate what each system does or their relationship to Claude.

## Proposed Naming

| Current Name | New Name | Acronym | Purpose |
|--------------|----------|---------|---------|
| learning-memory-server | Claude Learning and Memory System | **CLAMS** | Semantic memory, code indexing, experience learning |
| CLAMS (Claude Agent Management System) | Claude Learning Agent Workflow System | **CLAWS** | Agent orchestration, task management, phase gates |

Both are "Claude L* A* *S" - a consistent naming pattern that:
- Clearly identifies them as Claude-related tooling
- Distinguishes their purposes (Memory vs Workflow)
- Creates memorable, pronounceable acronyms (CLAMS and CLAWS)
- CLAMS keeps its name but changes meaning; workflow system becomes CLAWS

## Scope

This is a **comprehensive rename** that must touch every file containing references to the old names. No orphaned references allowed.

### Files and Patterns to Update

#### CLAMS (formerly learning-memory-server)

**Package/Module Names:**
- `src/learning_memory_server/` → `src/clams/`
- All imports: `from learning_memory_server.` → `from clams.`
- `pyproject.toml`: package name, entry points
- Test imports in `tests/`

**Documentation and Comments:**
- README.md references
- Docstrings mentioning "learning memory server"
- Code comments
- Planning docs

**Configuration:**
- MCP server name in configs
- Environment variable prefixes: `LMS_*` → `CLAMS_*`
- Any hardcoded strings

#### CLAWS (formerly CLAMS workflow system)

**Scripts and Utilities:**
- `.claude/bin/clams-*` → `.claude/bin/claws-*`
- Database: `.claude/clams.db` → `.claude/claws.db`
- All script internals referencing "clams"

**Documentation:**
- `CLAUDE.md` - extensive CLAMS references → CLAWS
- `.claude/roles/*.md` - role definitions
- Planning docs mentioning CLAMS workflow

**Code References:**
- Any Python/shell scripts referencing CLAMS workflow
- Comments and docstrings

### Exclusions

- Git history (commit messages stay as-is)
- External URLs (if any)
- Third-party package names
- `.claude/journal/session_entries.jsonl` (historical session logs)
- Existing `changelog.d/*.md` entries (historical changelogs)
- `tests/fixtures/` (test data files, not production references)
- Historical references in `planning_docs/` (acceptable for context, e.g., "formerly known as CLAMS")

## Requirements

### Functional Requirements

1. **Complete Rename**: Every file in the repository must be checked for old name references
2. **Working Imports**: All Python imports must work after rename
3. **Working Scripts**: All `.claude/bin/` scripts must work after rename
4. **Database Migration**: Existing `.claude/clams.db` must be migrated or recreated as `.claude/claws.db`
5. **MCP Server**: Server must register as `clams` (short, memorable)

### Non-Functional Requirements

1. **No Orphans**: `grep -r` for old names must return zero matches (excluding git history)
2. **Tests Pass**: Full test suite must pass after rename
3. **Atomic Change**: All renames happen in one coordinated change

## Implementation Approach

### Phase 1: Audit (Generate Complete File List)

Run comprehensive search for all references:

```bash
# Find all learning-memory-server references (case-insensitive)
grep -ri "learning.memory" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
grep -ri "learning_memory" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
grep -ri "LMS_" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .

# Find config files that might have references
find . -name "*.json" -o -name "settings*.json" | xargs grep -l "learning.memory\|LMS_\|clams"

# Check GETTING_STARTED.md specifically (known to have LMS references)
grep -n "LMS_\|learning" GETTING_STARTED.md
```

Create a complete manifest of files to change.

### Phase 2: Package Rename (CLAMS - memory system)

1. Rename `src/learning_memory_server/` → `src/clams/`
2. Update all imports in `src/` and `tests/`
3. Update `pyproject.toml`
4. Update any `__init__.py` module docstrings
5. Rename environment variables `LMS_*` → `CLAMS_*`

### Phase 3: Script Rename (CLAWS - workflow system)

1. Rename `.claude/bin/clams-*` → `.claude/bin/claws-*`
2. Update internal references in each script
3. Rename `.claude/clams.db` → `.claude/claws.db`
4. Update all scripts that reference the database path

### Phase 4: Documentation Update

1. Update `CLAUDE.md` (extensive changes - CLAMS → CLAWS for workflow)
2. Update all `.claude/roles/*.md`
3. Update `README.md`
4. Update `GETTING_STARTED.md` (has `LMS_*` env vars and "Learning Memory Server" references)
5. Update `.claude/settings.local.json` if it exists
6. Update all `planning_docs/` references (except historical context)
7. Update code comments and docstrings

### Phase 5: Verification

1. Run `grep -r` to verify no orphaned references
2. Run full test suite
3. Manually test key workflows:
   - MCP server startup (CLAMS)
   - `claws-status`
   - `claws-task` operations
   - Code indexing

## Acceptance Criteria

1. [ ] `src/clams/` exists and `src/learning_memory_server/` is removed
2. [ ] All Python imports use `from clams.` and work correctly
3. [ ] `.claude/bin/claws-*` scripts exist and `.claude/bin/clams-*` are removed
4. [ ] `.claude/claws.db` is the database path (migration handled)
5. [ ] `CLAUDE.md` references CLAWS throughout (for workflow system)
6. [ ] Environment variables use `CLAMS_*` prefix (for memory system)
7. [ ] `grep -ri "learning.memory\|learning_memory\|LMS_" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml"` returns no matches (excluding git/planning history)
8. [ ] Full test suite passes
9. [ ] MCP server registers as `clams`
10. [ ] `GETTING_STARTED.md` updated with CLAMS references and `CLAMS_*` environment variables

## Risks

1. **Missed References**: Mitigated by comprehensive grep audit and verification step
2. **Broken Imports**: Mitigated by running full test suite
3. **Database Path Issues**: Mitigated by explicit migration step
4. **Script Breakage**: Mitigated by testing each renamed script

## Notes

- This is a large but mechanical change
- Consider using `sed` or a refactoring tool for bulk updates
- The audit phase is critical - don't skip it
- Planning docs may retain historical references (acceptable for context)
