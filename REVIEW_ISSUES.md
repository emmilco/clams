# Code Review #1 - CHANGES REQUESTED

## Summary
106 orphaned references to old naming (learning-memory-server, learning_memory_server, LMS_) remain in the codebase.

## Required Fixes

### 1. Test File Docstrings (6 files)
- [ ] `tests/__init__.py` - Replace "learning-memory-server" → "CLAMS"
- [ ] `tests/integration/__init__.py` - Replace "Learning Memory Server" → "CLAMS"
- [ ] `tests/integration/test_e2e.py` - Update docstring
- [ ] `tests/performance/__init__.py` - Replace "Learning Memory Server" → "CLAMS"
- [ ] `tests/performance/test_benchmarks.py` - Update docstring

### 2. Test Code Imports/References (4 files)
- [ ] `tests/integration/test_e2e.py` - Replace `learning_memory_server.clustering` → `clams.clustering`
- [ ] `tests/hooks/test_mcp_client.py` - Replace `learning_memory_server` → `clams` (2 refs)
- [ ] `tests/server/test_config.py` - Replace `~/.learning-memory` → `~/.clams` (2 refs)
- [ ] `tests/performance/test_benchmarks.py` - Replace `learning_memory_server.clustering` → `clams.clustering`

### 3. Source Code (3 files)
- [ ] `src/clams/__init__.py` - Replace "Learning Memory Server" → "CLAMS (Claude Learning and Memory System)"
- [ ] `src/clams/server/config.py` - Replace `~/.learning-memory` → `~/.clams` (2 refs)
- [ ] `src/clams/storage/base.py` - Replace `~/.learning-memory` → `~/.clams` (2 refs)

### 4. Bug Reports (12 files)
Replace all `src/learning_memory_server/` → `src/clams/` and "learning-memory-server" → "clams":
- [ ] `bug_reports/BUG-001.md` (8 refs)
- [ ] `bug_reports/BUG-002.md` (14 refs)
- [ ] `bug_reports/BUG-003.md` (5 refs)
- [ ] `bug_reports/BUG-005.md` (9 refs)
- [ ] `bug_reports/BUG-006.md` (3 refs)
- [ ] `bug_reports/BUG-008.md` (2 refs)
- [ ] `bug_reports/BUG-009.md` (10 refs)
- [ ] `bug_reports/BUG-010.md` (4 refs)
- [ ] `bug_reports/BUG-011.md` (4 refs)
- [ ] `bug_reports/BUG-012.md` (11 refs)
- [ ] `bug_reports/BUG-013.md` (7 refs)
- [ ] `bug_reports/BUG-014.md` (12 refs)

## Verification Command
After fixes, this command should return 0 matches:
```bash
grep -ri "learning.memory\|learning_memory\|LMS_" \
  --include="*.py" --include="*.md" --include="*.sh" --include="*.toml" \
  . | grep -v ".git/" | grep -v "planning_docs/" | grep -v "changelog.d/" | grep -v ".venv/"
```

## Acceptance Criterion
Criterion #7: grep command returns no matches (currently 106 matches)
