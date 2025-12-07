# SPEC-007: Rename Systems to CAMS and CAWS

## Problem Statement

The project currently contains two systems with unclear naming:

1. **learning-memory-server**: An MCP server providing semantic memory, code indexing, git analysis, GHAP tracking, and value formation
2. **CLAMS**: An agent orchestration workflow system for coordinating AI workers

The current names don't clearly communicate what each system does or their relationship to Claude.

## Proposed Naming

| Current Name | New Name | Acronym | Purpose |
|--------------|----------|---------|---------|
| learning-memory-server | Claude Agent Memory System | **CAMS** | Semantic memory, code indexing, experience learning |
| CLAMS (Claude Agent Management System) | Claude Agent Workflow System | **CAWS** | Agent orchestration, task management, phase gates |

Both are "Claude Agent *X* System" - a consistent naming pattern that:
- Clearly identifies them as Claude-related tooling
- Distinguishes their purposes (Memory vs Workflow)
- Creates memorable, pronounceable acronyms

## Scope

This is a **comprehensive rename** that must touch every file containing references to the old names. No orphaned references allowed.

### Files and Patterns to Update

#### CAMS (formerly learning-memory-server)

**Package/Module Names:**
- `src/learning_memory_server/` → `src/cams/`
- All imports: `from learning_memory_server.` → `from cams.`
- `pyproject.toml`: package name, entry points
- Test imports in `tests/`

**Documentation and Comments:**
- README.md references
- Docstrings mentioning "learning memory server"
- Code comments
- Planning docs

**Configuration:**
- MCP server name in configs
- Environment variable prefixes: `LMS_*` → `CAMS_*`
- Any hardcoded strings

#### CAWS (formerly CLAMS)

**Scripts and Utilities:**
- `.claude/bin/clams-*` → `.claude/bin/caws-*`
- Database: `.claude/clams.db` → `.claude/caws.db`
- All script internals referencing "clams"

**Documentation:**
- `CLAUDE.md` - extensive CLAMS references
- `.claude/roles/*.md` - role definitions
- Planning docs mentioning CLAMS

**Code References:**
- Any Python/shell scripts referencing CLAMS
- Comments and docstrings

### Exclusions

- Git history (commit messages stay as-is)
- External URLs (if any)
- Third-party package names

## Requirements

### Functional Requirements

1. **Complete Rename**: Every file in the repository must be checked for old name references
2. **Working Imports**: All Python imports must work after rename
3. **Working Scripts**: All `.claude/bin/` scripts must work after rename
4. **Database Migration**: Existing `.claude/clams.db` must be migrated or recreated as `.claude/caws.db`
5. **MCP Server**: Server must register with new name

### Non-Functional Requirements

1. **No Orphans**: `grep -r` for old names must return zero matches (excluding git history)
2. **Tests Pass**: Full test suite must pass after rename
3. **Atomic Change**: All renames happen in one coordinated change

## Implementation Approach

### Phase 1: Audit (Generate Complete File List)

Run comprehensive search for all references:

```bash
# Find all CLAMS references
grep -r "clams" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
grep -r "CLAMS" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .

# Find all learning-memory-server references
grep -r "learning.memory" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
grep -r "learning_memory" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
grep -r "LMS_" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" --include="*.json" .
```

Create a complete manifest of files to change.

### Phase 2: Package Rename (CAMS)

1. Rename `src/learning_memory_server/` → `src/cams/`
2. Update all imports in `src/` and `tests/`
3. Update `pyproject.toml`
4. Update any `__init__.py` module docstrings
5. Rename environment variables `LMS_*` → `CAMS_*`

### Phase 3: Script Rename (CAWS)

1. Rename `.claude/bin/clams-*` → `.claude/bin/caws-*`
2. Update internal references in each script
3. Rename `.claude/clams.db` → `.claude/caws.db`
4. Update all scripts that reference the database path

### Phase 4: Documentation Update

1. Update `CLAUDE.md` (extensive changes)
2. Update all `.claude/roles/*.md`
3. Update `README.md`
4. Update all `planning_docs/` references
5. Update code comments and docstrings

### Phase 5: Verification

1. Run `grep -r` to verify no orphaned references
2. Run full test suite
3. Manually test key workflows:
   - MCP server startup
   - `caws-status`
   - `caws-task` operations
   - Code indexing

## Acceptance Criteria

1. [ ] `src/cams/` exists and `src/learning_memory_server/` is removed
2. [ ] All Python imports use `from cams.` and work correctly
3. [ ] `.claude/bin/caws-*` scripts exist and `.claude/bin/clams-*` are removed
4. [ ] `.claude/caws.db` is the database path (migration handled)
5. [ ] `CLAUDE.md` references CAWS throughout
6. [ ] Environment variables use `CAMS_*` prefix
7. [ ] `grep -ri "clams\|learning.memory\|learning_memory" --include="*.py" --include="*.md" --include="*.sh" --include="*.toml"` returns no matches (excluding git/planning history)
8. [ ] Full test suite passes
9. [ ] MCP server registers as "cams" or "claude-agent-memory-system"

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
