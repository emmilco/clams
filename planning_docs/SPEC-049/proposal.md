# SPEC-049: Pre-commit Hook for Hash/Eq Contract - Technical Proposal

## Problem Statement

BUG-028 revealed a critical bug: `ContextItem.__hash__` used only the first 100 characters of content, while `__eq__` compared the full content. This violated Python's fundamental hash/eq contract:

> If `a == b`, then `hash(a) == hash(b)`

When this contract is violated:
- Set membership tests become unpredictable
- Dict key lookups fail silently
- Deduplication produces incorrect results

The bug was silent - no test caught it, no CI failed. A developer added `__hash__` without adding a contract test, and the violation went unnoticed.

**Goal**: Create an advisory pre-commit hook that warns when new `__hash__` or `__eq__` methods are added without corresponding contract tests.

## Proposed Solution

### High-Level Design

Create a standalone Python script `.claude/hooks/check_hash_eq.py` that:

1. Parses staged Python files using Python's built-in `ast` module
2. Detects class definitions containing `__hash__` or `__eq__` methods
3. Checks `tests/context/test_data_contracts.py` for the class name
4. Warns if no test reference is found

The hook is **advisory only** (always exits 0) to allow commits during development before tests are written.

### Architecture

```
check_hash_eq.py
    |
    +-- get_staged_files() -> list[str]
    |       Uses: git diff --cached --name-only --diff-filter=AM
    |       Filters: .py files, excludes tests/**
    |
    +-- find_hash_eq_classes(filepath) -> list[HashEqInfo]
    |       Uses: ast.parse(), ast.NodeVisitor
    |       Returns: (class_name, has_hash, has_eq, has_hash_none, line_number)
    |
    +-- class_has_test(class_name) -> bool
    |       Checks: tests/context/test_data_contracts.py
    |       Match: word boundary search for class name
    |
    +-- format_warning(warnings) -> str
    |       Outputs: actionable warning message
    |
    +-- main() -> int
            Returns: 0 always (advisory)
```

### AST Parsing Approach

The hook uses Python's `ast` module for reliable detection:

```python
class HashEqVisitor(ast.NodeVisitor):
    """Visit class definitions to find __hash__ and __eq__ methods."""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        has_hash = False
        has_eq = False
        has_hash_none = False

        for item in node.body:
            # Method definitions: def __hash__(self) or def __eq__(self, other)
            if isinstance(item, ast.FunctionDef):
                if item.name == "__hash__":
                    has_hash = True
                elif item.name == "__eq__":
                    has_eq = True

            # Assignment: __hash__ = None (explicit unhashable)
            elif isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__hash__":
                        if isinstance(item.value, ast.Constant) and item.value.value is None:
                            has_hash_none = True

        if has_hash or has_eq:
            self.results.append(HashEqInfo(
                class_name=node.name,
                has_hash=has_hash,
                has_eq=has_eq,
                has_hash_none=has_hash_none,
                line_number=node.lineno,
            ))

        # Recurse into nested classes
        self.generic_visit(node)
```

**Key AST nodes handled**:
- `ast.ClassDef`: Class definitions (including nested classes)
- `ast.FunctionDef`: Method definitions (`def __hash__`, `def __eq__`)
- `ast.Assign`: Assignments (`__hash__ = None`)
- `ast.Constant`: Literal values (to check for `None`)

**Why AST over regex**:
- Regex cannot reliably distinguish methods from similarly-named functions at module level
- Regex cannot handle nested classes correctly
- Regex struggles with multi-line method signatures
- AST provides accurate line numbers for error messages

### Test Lookup Strategy

The hook checks if the class has a corresponding test in `tests/context/test_data_contracts.py`:

```python
def class_has_test(class_name: str, test_file_path: Path) -> bool:
    """Check if class appears in the test file using word boundary matching."""
    if not test_file_path.exists():
        return False

    content = test_file_path.read_text()
    # Word boundary regex: class name as complete word
    # Matches: "ContextItem" in "ContextItem(" or "ContextItem,"
    # Does not match: "ContextItemExtra" or "MyContextItem"
    pattern = rf'\b{re.escape(class_name)}\b'
    return bool(re.search(pattern, content))
```

**Test location rationale**:
- SPEC-047 establishes `tests/context/test_data_contracts.py` as the canonical location for hash/eq contract tests
- Using a single file makes it easy to verify test existence
- Word boundary matching avoids false positives from substring matches

### Warning Output Format

The warning message is designed to be actionable:

```
NOTICE: Class 'MyClass' in src/clams/foo.py (line 42) defines __hash__/__eq__.

No contract test found in tests/context/test_data_contracts.py.

Add a test to verify the hash/eq contract:

    class TestMyClassContract:
        def test_equal_items_have_equal_hashes(self) -> None:
            obj1 = MyClass(...)
            obj2 = MyClass(...)
            if obj1 == obj2:
                assert hash(obj1) == hash(obj2), "Hash/eq contract violation"

See BUG-028 for context on why this matters.
```

**Format features**:
- Uses "NOTICE" instead of "WARNING" to indicate advisory nature
- Includes file path and line number for easy navigation
- Specifies which methods are defined (`__hash__`, `__eq__`, or both)
- Provides a concrete test template
- References BUG-028 for context

### Error Handling

The hook handles errors gracefully to avoid blocking commits:

| Error Condition | Behavior |
|----------------|----------|
| File deleted before hook runs | Skip file (check exists before read) |
| Python syntax error in file | Warn to stderr, skip file, continue |
| Git command fails | Print error, return 0 (don't block) |
| Test file doesn't exist | Treat as no tests (warn on all classes) |
| Non-Python file in list | Skip silently |

```python
def check_file(filepath: Path) -> list[HashEqInfo]:
    """Parse a file for __hash__/__eq__ definitions."""
    if not filepath.exists():
        return []  # File deleted after staging

    try:
        source = filepath.read_text()
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"Notice: Could not parse {filepath}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Notice: Error reading {filepath}: {e}", file=sys.stderr)
        return []

    visitor = HashEqVisitor()
    visitor.visit(tree)
    return visitor.results
```

### Edge Cases

| Case | Behavior |
|------|----------|
| Only `__hash__` defined | Warn (may inherit broken `__eq__`) |
| Only `__eq__` defined | Warn (should set `__hash__ = None` or define it) |
| Both defined | Single warning mentioning both |
| `__hash__ = None` (explicit unhashable) | No warning (intentionally unhashable) |
| Nested classes | Detect and warn for each separately |
| Abstract base classes | Warn (implementers may forget contract tests) |
| Test files | Skip (no warnings for test code) |

### Command-Line Interface

```bash
# Check staged files (default pre-commit mode)
python .claude/hooks/check_hash_eq.py

# Check specific files (manual mode)
python .claude/hooks/check_hash_eq.py src/clams/context/models.py src/clams/storage/base.py

# Exit code is always 0 (advisory)
echo $?  # 0
```

## Data Structures

```python
from typing import NamedTuple

class HashEqInfo(NamedTuple):
    """Information about a class with __hash__ or __eq__."""
    class_name: str      # Name of the class
    has_hash: bool       # True if defines __hash__ method
    has_eq: bool         # True if defines __eq__ method
    has_hash_none: bool  # True if has __hash__ = None
    line_number: int     # Line where class is defined
    filepath: str        # File containing the class

class Warning(NamedTuple):
    """A warning to display to the user."""
    filepath: str
    class_name: str
    line_number: int
    methods: str  # "__hash__", "__eq__", or "__hash__ and __eq__"
```

## File Structure

```
.claude/
  hooks/
    check_hash_eq.py     # The hook script (new)
    check_heavy_imports.py  # Existing pattern to follow
    check_subprocess.py     # Existing pattern to follow

tests/
  hooks/
    test_check_hash_eq.py   # Tests for the hook (new)
  context/
    test_data_contracts.py  # Canonical location for contract tests (exists)
```

## Testing Strategy

### Unit Tests (in `tests/hooks/test_check_hash_eq.py`)

**Detection tests**:
- `test_detects_hash_method`: Detects `def __hash__(self)`
- `test_detects_eq_method`: Detects `def __eq__(self, other)`
- `test_detects_both_methods`: Detects class with both methods
- `test_detects_hash_none`: Recognizes `__hash__ = None` as intentionally unhashable
- `test_detects_nested_classes`: Finds __hash__/__eq__ in nested class definitions
- `test_reports_correct_line_number`: Line number matches class definition

**Filtering tests**:
- `test_ignores_test_files`: No warnings for `tests/**/*.py`
- `test_ignores_methods_in_test_classes`: Even if test file has __hash__, no warning
- `test_processes_only_python_files`: Non-.py files are skipped

**Test lookup tests**:
- `test_class_with_test_no_warning`: No warning if class name in test file
- `test_class_without_test_warns`: Warning if class name not in test file
- `test_missing_test_file_warns_all`: Warns on all classes if test file doesn't exist
- `test_word_boundary_matching`: "Item" doesn't match "ContextItem"

**Error handling tests**:
- `test_handles_syntax_error`: Skips file, continues processing
- `test_handles_deleted_file`: Skips without error
- `test_handles_unreadable_file`: Skips without error

**Exit code tests**:
- `test_exits_zero_with_warnings`: Advisory - always exits 0
- `test_exits_zero_without_warnings`: Clean run exits 0

### Integration Tests

- `test_actual_contextitem_has_test`: Verify ContextItem is detected and has test
- `test_manual_file_argument`: Test with explicit file paths

### Test Fixtures

Create temporary Python files with various __hash__/__eq__ patterns:

```python
@pytest.fixture
def temp_python_file(tmp_path: Path) -> Callable[[str], Path]:
    """Factory to create temporary Python files for testing."""
    def create(content: str) -> Path:
        f = tmp_path / "test_module.py"
        f.write_text(content)
        return f
    return create
```

## Implementation Notes

### Following Existing Patterns

The implementation follows patterns from existing hooks:

1. **From `check_heavy_imports.py`**:
   - Use `NamedTuple` for result types
   - AST visitor pattern for parsing
   - `check_file()` function signature
   - Test file detection logic
   - Error handling in `main()`

2. **From `check_subprocess.py`**:
   - Simple visitor pattern without nested tracking
   - Clean issue reporting

### Type Annotations

Full type annotations for mypy --strict compliance:

```python
def find_hash_eq_classes(filepath: Path) -> list[HashEqInfo]:
    ...

def class_has_test(class_name: str, test_file: Path) -> bool:
    ...

def format_warnings(warnings: list[Warning]) -> str:
    ...

def main() -> int:
    ...
```

### No External Dependencies

The hook uses only Python standard library:
- `ast` - AST parsing
- `sys` - Command line arguments, stderr
- `subprocess` - Git commands
- `pathlib` - Path handling
- `re` - Word boundary matching

This avoids adding dependencies to `.claude/hooks/` which should remain lightweight.

## Alternatives Considered

### 1. Blocking Mode (Exit 1 on Warnings)

**Rejected because**:
- Would block commits before SPEC-047/048 add contract tests
- Pre-commit hooks should be fast and non-blocking for best developer experience
- Advisory mode still surfaces the issue without friction

### 2. Regex-Based Detection

**Rejected because**:
- Cannot distinguish class methods from module-level functions
- Struggles with nested classes and multi-line signatures
- Would require complex patterns for all edge cases
- AST is more maintainable and accurate

### 3. Check All Test Files for Class Name

**Rejected because**:
- Harder to know where tests should go
- Contract tests belong in a specific location for consistency
- Would produce false positives from other test types

### 4. Integration with pre-commit Framework

**Deferred** (marked as out of scope in spec):
- Can be added later by adding to `.pre-commit-config.yaml`
- Current approach allows immediate use without framework dependency

## Acceptance Criteria Mapping

| Spec Criterion | Proposal Coverage |
|----------------|-------------------|
| Hook at `.claude/hooks/check_hash_eq.py` | Yes - File Structure section |
| Detect `def __hash__` | Yes - AST parsing handles |
| Detect `def __eq__` | Yes - AST parsing handles |
| Extract containing class name | Yes - ast.ClassDef.name |
| Ignore test files | Yes - `is_test_file()` function |
| Check test_data_contracts.py | Yes - `class_has_test()` function |
| Word boundary matching | Yes - regex `\b{class_name}\b` |
| Handle missing test file | Yes - return False, warn all |
| Warning includes file/class/methods | Yes - Warning NamedTuple |
| Suggest test_data_contracts.py | Yes - warning message |
| Reference BUG-028 | Yes - warning message |
| Exit 0 always | Yes - advisory mode |
| Manual mode with file args | Yes - `main()` handles |
| Default mode checks staged | Yes - `get_staged_files()` |
| Handle deleted files | Yes - exists check |
| Handle syntax errors | Yes - try/except in check_file |
| Handle git failures | Yes - try/except in get_staged_files |
| Only `__hash__` warns | Yes - Edge Cases table |
| Only `__eq__` warns | Yes - Edge Cases table |
| Both methods: single warning | Yes - Edge Cases table |
| `__hash__ = None` no warning | Yes - has_hash_none check |
| Nested classes detected | Yes - generic_visit() recurses |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| False positives on test helper classes | Skip test files entirely |
| Missing nested class edge case | Use generic_visit() for full AST traversal |
| Test file location changes | Single constant `TEST_FILE_PATH` to update |
| Class renamed in test | Word boundary matching + manual review |
