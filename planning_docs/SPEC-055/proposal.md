# Technical Proposal: SPEC-055 CI Check for Hardcoded Paths

## Problem Statement

Hardcoded paths in the codebase cause environment-specific failures that are only discovered when someone else runs the code. Common violations include:

1. **macOS home directories**: `/Users/someone/project/...`
2. **Linux home directories**: `/home/username/...`
3. **Windows user directories**: `C:\Users\...`
4. **Hardcoded `/tmp/` paths**: Conflict in CI or multi-process environments

These issues waste developer time on debugging and can block CI pipelines. A static analysis check can catch most of these issues before code reaches the repository.

## Proposed Solution

Create a Python AST-based scanner that analyzes string literals for hardcoded path patterns. The scanner will:

1. Parse Python files using the `ast` module for accuracy
2. Detect path patterns in string literals only (not comments or docstrings)
3. Support an allowlist for intentional exceptions
4. Integrate with the existing gate check system

### Why Python AST (Not Grep)

Grep-based approaches fail because they:
- Cannot distinguish string literals from comments (e.g., `# /Users/example`)
- Cannot identify docstrings vs code strings
- Struggle with multi-line strings and f-strings
- Produce false positives on regex patterns or documentation

The AST approach:
- Ignores comments entirely (not in AST)
- Can identify docstrings by position (first expression in module/class/function)
- Handles f-strings via `ast.JoinedStr` nodes
- Provides line number information for precise reporting

## Architecture

### File Layout

```
.claude/checks/
    check_hardcoded_paths.py      # Main script (executable, with shebang)
    path_allowlist.txt            # Optional allowlist (created if needed)

tests/checks/
    test_check_hardcoded_paths.py # Unit tests
```

### Core Components

```
+-------------------+
|     main()        |  Entry point, CLI argument handling
+-------------------+
         |
         v
+-------------------+
|  scan_directory() |  Recursively find Python files
+-------------------+
         |
         v
+-------------------+
|   scan_file()     |  Parse single file, collect violations
+-------------------+
         |
         v
+-------------------+
|  PathVisitor      |  AST visitor that checks string nodes
+-------------------+
         |
         v
+-------------------+
| check_string()    |  Pattern matching against path patterns
+-------------------+
```

## Implementation Details

### 1. AST Visitor Pattern

The core of the scanner is an `ast.NodeVisitor` subclass that traverses the AST and examines string literals.

```python
class PathVisitor(ast.NodeVisitor):
    """AST visitor that collects hardcoded path violations."""

    def __init__(
        self,
        filepath: str,
        has_tempfile: bool,
        allowlist: set[tuple[str, int | None]],
    ) -> None:
        self.filepath = filepath
        self.has_tempfile = has_tempfile
        self.allowlist = allowlist
        self.violations: list[Violation] = []
        self._docstring_lines: set[int] = set()

    def visit_Module(self, node: ast.Module) -> None:
        # Mark module docstring
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._mark_docstring(node)
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str):
            self._check_string(node.value, node.lineno)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        # f-strings: check each string part
        for part in node.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                self._check_string(part.value, node.lineno)
        self.generic_visit(node)
```

### 2. Docstring Detection

Docstrings are the first expression statement in a module, class, or function body. The visitor marks these lines to skip them.

```python
def _mark_docstring(
    self, node: ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
) -> None:
    """Mark the line of a docstring so it can be skipped."""
    if node.body:
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
            if isinstance(first.value.value, str):
                self._docstring_lines.add(first.lineno)
```

### 3. Path Pattern Matching

Patterns are defined as compiled regex with descriptions:

```python
PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"/Users/[^/]+/"), "macOS home directory"),
    (re.compile(r"/home/[a-z_][a-z0-9_-]*/"), "Linux home directory"),
    (re.compile(r"[Cc]:[/\\][Uu]sers[/\\]"), "Windows user directory"),
]
```

The `/tmp/` check is conditional on tempfile usage:

```python
def check_string(value: str, has_tempfile: bool) -> str | None:
    """Check a string for hardcoded path violations.

    Args:
        value: The string literal to check
        has_tempfile: Whether the file imports tempfile or uses tmp_path

    Returns:
        Violation description, or None if clean
    """
    for pattern, description in PATTERNS:
        if pattern.search(value):
            return description

    if "/tmp/" in value and not has_tempfile:
        return "hardcoded /tmp/ path (use tempfile or tmp_path fixture)"

    return None
```

### 4. Tempfile Usage Detection

Before scanning a file, we check if it uses proper temp file utilities:

```python
def has_tempfile_usage(tree: ast.AST) -> bool:
    """Check if file imports tempfile or uses tmp_path fixture."""
    for node in ast.walk(tree):
        # import tempfile
        if isinstance(node, ast.Import):
            if any(alias.name == "tempfile" for alias in node.names):
                return True
        # from tempfile import ...
        elif isinstance(node, ast.ImportFrom):
            if node.module == "tempfile":
                return True
        # def test_foo(tmp_path): ...
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(arg.arg == "tmp_path" for arg in node.args.args):
                return True
    return False
```

### 5. Allowlist Handling

The allowlist file uses a simple format:

```
# Comments start with #
# Full file allowlist
some/file.py

# Specific line allowlist
another/file.py:42
```

Parsing logic:

```python
def load_allowlist(path: Path) -> set[tuple[str, int | None]]:
    """Load allowlist entries from file.

    Returns:
        Set of (filepath, line_number_or_None) tuples
    """
    if not path.exists():
        return set()

    entries: set[tuple[str, int | None]] = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if ":" in line:
            filepath, lineno = line.rsplit(":", 1)
            try:
                entries.add((filepath, int(lineno)))
            except ValueError:
                # Malformed line number, treat as whole-file
                entries.add((line, None))
        else:
            entries.add((line, None))

    return entries
```

Checking allowlist:

```python
def is_allowed(
    filepath: str, lineno: int, allowlist: set[tuple[str, int | None]]
) -> bool:
    """Check if a violation is allowlisted."""
    # Normalize path for comparison
    normalized = filepath.replace("\\", "/")

    # Check exact line match
    if (normalized, lineno) in allowlist:
        return True

    # Check file-level allowlist
    if (normalized, None) in allowlist:
        return True

    # Check if path ends with allowlist entry (for relative paths)
    for entry_path, entry_line in allowlist:
        if entry_line is None and normalized.endswith(entry_path):
            return True
        if entry_line == lineno and normalized.endswith(entry_path):
            return True

    return False
```

### 6. File Exclusions

Skip irrelevant directories and handle errors gracefully:

```python
EXCLUDED_DIRS = frozenset({
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
})

def should_skip_dir(dirname: str) -> bool:
    """Check if directory should be skipped."""
    return dirname in EXCLUDED_DIRS or dirname.endswith(".egg-info")

def scan_directory(
    root: Path,
    allowlist: set[tuple[str, int | None]],
) -> list[Violation]:
    """Scan directory recursively for hardcoded paths."""
    violations: list[Violation] = []

    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        # Remove excluded directories in-place to prevent descending
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d)]

        for filename in filenames:
            if not filename.endswith(".py"):
                continue

            filepath = Path(dirpath) / filename
            file_violations = scan_file(filepath, allowlist)
            violations.extend(file_violations)

    return violations
```

### 7. Error Handling

Files with syntax or encoding errors are skipped with warnings:

```python
def scan_file(
    filepath: Path,
    allowlist: set[tuple[str, int | None]],
) -> list[Violation]:
    """Scan a single Python file for hardcoded paths."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        print(f"WARNING: Skipping {filepath} (encoding error: {e})", file=sys.stderr)
        return []

    try:
        tree = ast.parse(content, filename=str(filepath))
    except SyntaxError as e:
        print(f"WARNING: Skipping {filepath} (syntax error: {e})", file=sys.stderr)
        return []

    has_tempfile = has_tempfile_usage(tree)
    visitor = PathVisitor(str(filepath), has_tempfile, allowlist)
    visitor.visit(tree)

    return visitor.violations
```

### 8. Output Format

Violations are reported grouped by file for readability:

```
=== Checking for hardcoded paths ===

src/example.py:15: macOS home directory
  String: "/Users/john/project/config.json"
src/example.py:42: Linux home directory
  String: "/home/developer/data"

src/other.py:10: hardcoded /tmp/ path (use tempfile or tmp_path fixture)
  String: "/tmp/cache/data.json"

=== Summary ===
Found 3 hardcoded path(s) in 2 file(s)
```

Note: Violations from the same file are grouped together (not interleaved with other files).

### 9. Exit Codes

| Code | Meaning |
|------|---------|
| 0 | No violations found |
| 1 | Violations found |
| 2 | Script error (e.g., invalid arguments, unexpected exception) |

### 10. Script Structure

The script starts with a proper shebang and has top-level error handling:

```python
#!/usr/bin/env python3
"""Check for hardcoded paths in Python source files."""

import sys
# ... other imports ...

def main() -> int:
    """Main entry point."""
    try:
        # ... argument parsing and scanning logic ...
        return 0 if not violations else 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
```

## CI Integration

### Option 1: Pre-commit Hook (Recommended)

Add to `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: local
    hooks:
      - id: check-hardcoded-paths
        name: Check for hardcoded paths
        entry: python .claude/checks/check_hardcoded_paths.py
        language: python
        types: [python]
        pass_filenames: false
```

### Option 2: GitHub Actions

Add to `.github/workflows/ci.yml`:

```yaml
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Check for hardcoded paths
        run: python .claude/checks/check_hardcoded_paths.py
```

### Option 3: Gate Check Integration

Add to `.claude/gates/registry.json`:

```json
{
  "checks": {
    "paths": {
      "python": "check_hardcoded_paths.py",
      "default": null
    }
  }
}
```

**Recommendation**: Use pre-commit (Option 1) for immediate feedback, plus GitHub Actions (Option 2) as a safety net for commits that bypass pre-commit.

## Data Structures

### Violation

```python
@dataclasses.dataclass
class Violation:
    """A single hardcoded path violation."""

    filepath: str
    lineno: int
    description: str
    string_value: str  # Truncated if > 80 chars
```

### ScanResult

```python
@dataclasses.dataclass
class ScanResult:
    """Result of scanning a directory."""

    violations: list[Violation]
    files_scanned: int
    files_skipped: int  # Due to errors
```

## Testing Strategy

### Unit Tests

```python
# tests/checks/test_check_hardcoded_paths.py

import ast
import pytest

from check_hardcoded_paths import (
    check_string,
    has_tempfile_usage,
    PathVisitor,
    load_allowlist,
)


class TestCheckString:
    """Tests for check_string function."""

    def test_detects_macos_path(self):
        result = check_string("/Users/john/project/file.txt", has_tempfile=False)
        assert result == "macOS home directory"

    def test_detects_linux_path(self):
        result = check_string("/home/username/project", has_tempfile=False)
        assert result == "Linux home directory"

    def test_detects_windows_path(self):
        result = check_string("C:\\Users\\name\\file.txt", has_tempfile=False)
        assert result == "Windows user directory"

    def test_flags_tmp_without_tempfile(self):
        result = check_string("/tmp/cache/data.json", has_tempfile=False)
        assert "hardcoded /tmp/" in result

    def test_allows_tmp_with_tempfile(self):
        result = check_string("/tmp/cache/data.json", has_tempfile=True)
        assert result is None

    def test_ignores_safe_paths(self):
        assert check_string("/usr/bin/python", has_tempfile=False) is None
        assert check_string("/etc/config", has_tempfile=False) is None


class TestHasTempfileUsage:
    """Tests for tempfile detection."""

    def test_detects_import_tempfile(self):
        code = "import tempfile\nf = tempfile.mktemp()"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_from_tempfile_import(self):
        code = "from tempfile import NamedTemporaryFile"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_detects_tmp_path_fixture(self):
        code = "def test_foo(tmp_path):\n    pass"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is True

    def test_no_tempfile(self):
        code = "x = '/tmp/foo'"
        tree = ast.parse(code)
        assert has_tempfile_usage(tree) is False


class TestPathVisitor:
    """Tests for AST visitor."""

    def test_ignores_comments(self):
        # Comments aren't in AST, so this should find nothing
        code = "# /Users/example/path\nx = 1"
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_ignores_docstrings(self):
        code = '''
def foo():
    """/Users/example is documented here."""
    pass
'''
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 0

    def test_detects_string_literal(self):
        code = 'path = "/Users/john/project"'
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 1

    def test_detects_f_string(self):
        code = 'path = f"/Users/{name}/project"'
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, set())
        visitor.visit(tree)
        assert len(visitor.violations) == 1


class TestAllowlist:
    """Tests for allowlist handling."""

    def test_load_missing_file(self, tmp_path):
        result = load_allowlist(tmp_path / "missing.txt")
        assert result == set()

    def test_load_with_comments(self, tmp_path):
        allowlist = tmp_path / "allowlist.txt"
        allowlist.write_text("# Comment\nfile.py\n# Another\nother.py:10\n")
        result = load_allowlist(allowlist)
        assert result == {("file.py", None), ("other.py", 10)}

    def test_specific_line_allowed(self):
        allowlist = {("test.py", 5)}
        code = 'x = "/Users/test"'
        tree = ast.parse(code)
        visitor = PathVisitor("test.py", False, allowlist)
        visitor.visit(tree)
        # Line 1, not line 5, so should be flagged
        assert len(visitor.violations) == 1
```

### Integration Tests

```python
class TestEndToEnd:
    """End-to-end tests."""

    def test_scan_clean_directory(self, tmp_path):
        # Create a clean Python file
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_scan_with_violation(self, tmp_path):
        (tmp_path / "bad.py").write_text('path = "/Users/john/file"\n')
        result = scan_directory(tmp_path, set())
        assert len(result) == 1
        assert result[0].lineno == 1

    def test_skips_pycache(self, tmp_path):
        cache = tmp_path / "__pycache__"
        cache.mkdir()
        (cache / "bad.py").write_text('x = "/Users/john"')
        result = scan_directory(tmp_path, set())
        assert len(result) == 0

    def test_handles_syntax_error(self, tmp_path, capsys):
        (tmp_path / "broken.py").write_text("def broken(\n")
        result = scan_directory(tmp_path, set())
        assert len(result) == 0
        captured = capsys.readouterr()
        assert "syntax error" in captured.err.lower()

    def test_does_not_follow_symlinks(self, tmp_path):
        # Create external directory with violation
        external = tmp_path / "external"
        external.mkdir()
        (external / "bad.py").write_text('x = "/Users/john"')

        # Create project with symlink to external
        project = tmp_path / "project"
        project.mkdir()
        (project / "link").symlink_to(external)

        result = scan_directory(project, set())
        assert len(result) == 0  # Should not follow symlink
```

## Security Considerations

1. **No code execution**: The scanner only parses files, never executes them
2. **No symlink following**: Prevents scanning outside the project boundary
3. **Allowlist location**: The allowlist is in the repo, so changes are tracked in version control

## Performance Considerations

1. **Single-pass AST traversal**: Each file is parsed once
2. **Compiled regexes**: Patterns are pre-compiled module-level constants
3. **In-place directory filtering**: Excluded directories are removed from walk list
4. **Expected performance**: < 1 second for ~100 Python files

## Future Extensions

These are out of scope for SPEC-055 but could be added later:

1. **JSON/YAML support**: Add parsers for configuration files
2. **Auto-fix mode**: Suggest replacements using `Path.home()` or `tmp_path`
3. **IDE integration**: Language server protocol support
4. **Additional languages**: JavaScript, TypeScript, Go, etc.

## Acceptance Verification

The implementation will be verified against the spec's acceptance criteria:

| Criterion | Verification Method |
|-----------|---------------------|
| Script created at correct path | `test -x .claude/checks/check_hardcoded_paths.py` |
| Exit codes | Unit tests for 0, 1, 2 cases |
| Path detection | Unit tests for each pattern |
| AST-based analysis | Unit tests showing comments/docstrings ignored |
| Allowlist support | Unit tests for file and line-level allowlist |
| Exclusions | Integration tests for each excluded directory |
| Output format | Integration test capturing stdout |
| /tmp/ nuance | Unit tests for with/without tempfile |
| Error handling | Integration tests for syntax/encoding errors |

## Summary

This proposal describes a Python AST-based scanner for detecting hardcoded paths. Key design decisions:

1. **AST over grep**: Accuracy and context-awareness
2. **Visitor pattern**: Clean, extensible traversal
3. **Conditional /tmp/ checks**: Avoid false positives in test code
4. **Simple allowlist format**: Easy to maintain
5. **Integration via pre-commit**: Immediate developer feedback

The implementation is straightforward, testable, and fits naturally into the existing gate check infrastructure.
