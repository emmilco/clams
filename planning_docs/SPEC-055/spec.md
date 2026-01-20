# SPEC-055: CI Check for Hardcoded Paths

## Problem Statement

Several bugs have resulted from hardcoded paths that work on one developer's machine but fail elsewhere:
- Absolute paths like `/Users/someone/project/...`
- Hardcoded `/tmp/` paths that conflict in CI
- Test fixtures with machine-specific paths

These issues are only caught when someone else runs the code, causing frustrating debugging sessions. A CI check could catch most of these issues early.

**Reference**: Unblocked by SPEC-029 (per spec cross-references)

## Proposed Solution

Create a Python-based CI check script that uses AST parsing to accurately detect hardcoded paths in string literals, avoiding false positives from comments and docstrings.

**Why Python AST instead of grep**: Grep cannot reliably:
- Distinguish string literals from comments
- Handle multi-line strings and docstrings
- Parse f-strings and string concatenation
- Understand context (is this a path or a regex pattern?)

## Acceptance Criteria

### Script Creation

- [ ] Script `.claude/checks/check_hardcoded_paths.py` created
- [ ] Script is executable and has proper shebang
- [ ] Script exits 0 if no violations, 1 if violations found

### Path Detection

- [ ] Detects `/Users/` (macOS home directories) in string literals
- [ ] Detects `/home/[username]/` patterns (Linux home directories) in string literals
- [ ] Detects `C:\Users\` and `C:/Users/` (Windows paths) in string literals
- [ ] Detects hardcoded `/tmp/` paths that don't use temp file utilities

### AST-Based Analysis

- [ ] Uses Python AST to parse files (not grep)
- [ ] Only checks string literals (ast.Constant with str value)
- [ ] Handles f-strings by checking the string parts (ast.JoinedStr)
- [ ] Ignores comments (not in AST)
- [ ] Ignores docstrings by checking if string is first statement in function/class/module

### Allowlist Support

- [ ] Reads allowlist from `.claude/checks/path_allowlist.txt` if it exists
- [ ] Allowlist format: one `filepath:line_number` or `filepath` per line
- [ ] Comments in allowlist start with `#`
- [ ] If allowlist file doesn't exist, proceed without error

### Exclusions

- [ ] Skips files in: `.git/`, `node_modules/`, `__pycache__/`, `.venv/`, `venv/`
- [ ] Skips non-Python files
- [ ] Skips binary files gracefully (catch decode errors)
- [ ] Does not follow symlinks (to avoid loops and external code)

### Output Format

- [ ] Reports `filepath:line_number: violation description`
- [ ] Groups violations by file for readability
- [ ] Shows the actual problematic string (truncated if long)
- [ ] Final summary: `Found N hardcoded path(s) in M file(s)`

### /tmp/ Detection Nuance

- [ ] `/tmp/` is flagged UNLESS the same file imports `tempfile` or uses `tmp_path` fixture
- [ ] Check for `import tempfile`, `from tempfile import`, or `tmp_path` in function signatures

### Error Handling

- [ ] If a file has syntax errors, warn and skip (don't fail entire check)
- [ ] If a file has encoding errors, warn and skip
- [ ] Clear error message if script fails for unexpected reasons

## Implementation Notes

**File**: `.claude/checks/check_hardcoded_paths.py`

Core detection logic:
```python
import ast
import re
import sys
from pathlib import Path

PATTERNS = [
    (r'/Users/[^/]+/', 'macOS home directory'),
    (r'/home/[a-z_][a-z0-9_-]*/[^"\']*', 'Linux home directory'),
    (r'[Cc]:[/\\][Uu]sers[/\\]', 'Windows user directory'),
]

def check_string(value: str, has_tempfile_import: bool) -> str | None:
    """Returns violation description or None if OK."""
    for pattern, description in PATTERNS:
        if re.search(pattern, value):
            return description

    # Special /tmp/ handling
    if '/tmp/' in value and not has_tempfile_import:
        return 'hardcoded /tmp/ path (use tempfile or tmp_path fixture)'

    return None

def has_tempfile_usage(tree: ast.AST) -> bool:
    """Check if file imports tempfile or uses tmp_path."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name == 'tempfile' for alias in node.names):
                return True
        elif isinstance(node, ast.ImportFrom):
            if node.module == 'tempfile':
                return True
        elif isinstance(node, ast.FunctionDef):
            for arg in node.args.args:
                if arg.arg == 'tmp_path':
                    return True
    return False
```

## Testing Requirements

All tests automated via pytest:

- [ ] Test: detects `/Users/foo/bar` in string literal
- [ ] Test: detects `/home/username/project` in string literal
- [ ] Test: detects `C:\Users\name` in string literal
- [ ] Test: ignores paths in comments (# /Users/example)
- [ ] Test: ignores paths in docstrings
- [ ] Test: detects path in f-string like `f"/Users/{user}/file"`
- [ ] Test: respects allowlist entries
- [ ] Test: handles missing allowlist file gracefully
- [ ] Test: skips files with syntax errors with warning
- [ ] Test: handles encoding errors gracefully
- [ ] Test: `/tmp/` OK when file imports tempfile
- [ ] Test: `/tmp/` flagged when no tempfile import
- [ ] Test: does not follow symlinks

## CI Integration

- [ ] Add to `.github/workflows/` or equivalent CI config
- [ ] Run on pull requests
- [ ] Failure blocks merge (can be overridden with allowlist)
- [ ] Clear job name: "Check for hardcoded paths"

## Out of Scope

- Automatic fixing of hardcoded paths
- Detection in non-Python files (can extend later)
- IDE integration
- Detection in configuration files (YAML, JSON, etc.)
