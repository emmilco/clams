# SPEC-055: Grep-based CI Check for Hardcoded Paths

## Problem Statement

Several bugs have resulted from hardcoded paths that work on one developer's machine but fail elsewhere:
- Absolute paths like `/Users/someone/project/...`
- Hardcoded `/tmp/` paths that conflict in CI
- Test fixtures with machine-specific paths

These issues are only caught when someone else runs the code, causing frustrating debugging sessions. A simple grep-based CI check could catch most of these issues early.

**Reference**: Unblocked by SPEC-029 (per spec cross-references)

## Proposed Solution

Create a CI check script that greps for common hardcoded path patterns and fails if any are found (with allowlist for legitimate cases).

## Acceptance Criteria

- [ ] Script `.claude/checks/check_hardcoded_paths.sh` created
- [ ] Script scans Python files for patterns:
  - `/Users/` (macOS home directories)
  - `/home/` followed by username patterns (Linux home directories)
  - `C:\\Users\\` (Windows paths)
  - Absolute paths to `/tmp/` without pytest's `tmp_path` fixture
- [ ] Script has allowlist file `.claude/checks/path_allowlist.txt`
- [ ] Script returns 0 if no violations, 1 if violations found
- [ ] Script output shows file:line for each violation
- [ ] Script ignores:
  - Comments (lines starting with `#`)
  - Docstrings (between `"""`)
  - Test fixtures that use `tmp_path` or `tempfile`
  - Files in `.git/`, `node_modules/`, `__pycache__/`
- [ ] CI job runs this check on PRs

## Implementation Notes

Pattern detection (grep-based for speed):
```bash
# Find potential violations
grep -rn --include="*.py" -E '/Users/|/home/[a-z]|C:\\\\Users\\\\' src/ tests/ \
  | grep -v "^#" \
  | grep -v -f .claude/checks/path_allowlist.txt
```

Allowlist format (one pattern per line):
```
# Legitimate /tmp/ usage with proper cleanup
tests/integration/test_temp_files.py:45
# Documentation example
docs/examples/paths.py
```

For `/tmp/` detection, more nuanced check:
```bash
# Find /tmp/ usage
grep -rn --include="*.py" '"/tmp/' src/ tests/ \
  | grep -v 'tmp_path' \
  | grep -v 'tempfile\.' \
  | grep -v 'TemporaryDirectory'
```

## Testing Requirements

- Test detects `/Users/foo/bar` in Python file
- Test detects `/home/username/` in Python file
- Test ignores allowlisted files
- Test ignores comment lines
- Test passes when no violations exist
- Integration: run on actual codebase

## Out of Scope

- Automatic fixing of hardcoded paths
- Detection in non-Python files (can extend later)
- IDE integration
