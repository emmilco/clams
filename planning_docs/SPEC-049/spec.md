# SPEC-049: Pre-commit Hook for Hash/Eq Contract

## Problem Statement

BUG-028 revealed that `ContextItem.__hash__` used the first 100 characters but `__eq__` used the full content. This violates Python's fundamental hash/eq contract: if `a == b`, then `hash(a) == hash(b)`. Such violations cause silent bugs in set/dict operations.

These contract violations can be introduced silently without any test or CI failure. A pre-commit hook would catch new `__hash__` or `__eq__` implementations and warn developers to add contract tests.

**Reference**: R16-C from bug pattern analysis (Theme T14: Hash/Eq Contract Violations)

## Dependencies

- **SPEC-047** (Hash/Eq Contract Tests for ContextItem) - Creates `tests/test_data_contracts.py`
- **SPEC-048** (Hash/Eq Contract Tests for Other Hashable Classes) - Extends test coverage

**Note**: This hook can be implemented and used even before SPEC-047/048 are complete. It will warn on all `__hash__`/`__eq__` implementations until tests are added.

## Proposed Solution

Create an advisory pre-commit hook that:
1. Detects new or modified `__hash__` or `__eq__` methods in staged Python files
2. Warns if no corresponding test exists in `tests/test_data_contracts.py`
3. Provides guidance on adding contract tests

The hook is advisory (warning, not blocking) to allow development before SPEC-047/048 complete.

## Acceptance Criteria

### Detection

- [ ] Hook script created at `.claude/hooks/check_hash_eq.py`
- [ ] Hook detects `def __hash__` method definitions in staged Python files
- [ ] Hook detects `def __eq__` method definitions in staged Python files
- [ ] Hook extracts the containing class name for each detected method
- [ ] Hook ignores test files (`tests/**/*.py`) to avoid false positives

### Test Lookup

- [ ] Hook checks if class name appears in `tests/test_data_contracts.py`
- [ ] Matching is case-sensitive and looks for the class name as a word boundary
- [ ] If `tests/test_data_contracts.py` doesn't exist, all classes trigger warnings

### Warning Output

- [ ] Warning message includes: file path, class name, which method(s) defined
- [ ] Warning suggests adding a test to `tests/test_data_contracts.py`
- [ ] Warning references BUG-028 for context
- [ ] Warning format is clear and actionable

### Behavior

- [ ] Hook exits 0 (success) regardless of warnings found (advisory only)
- [ ] Hook can be run manually: `python .claude/hooks/check_hash_eq.py [files...]`
- [ ] With no arguments, hook checks staged files via `git diff --cached --name-only`
- [ ] With file arguments, hook checks those specific files

### Error Handling

- [ ] If a staged file is deleted before hook runs, skip it gracefully
- [ ] If a file has Python syntax errors (AST parse fails), warn and skip that file
- [ ] If git command fails, print error and exit 0 (don't block commits)

### Edge Cases

- [ ] Class with only `__hash__` defined: warn (may inherit broken `__eq__`)
- [ ] Class with only `__eq__` defined: warn (should set `__hash__ = None` or define it)
- [ ] Class with both `__hash__` and `__eq__`: single warning mentioning both
- [ ] Class with `__hash__ = None` (explicit unhashable): no warning needed
- [ ] Nested classes: detect and warn for each separately

## Implementation Notes

Detection approach using AST:
```python
import ast
import subprocess
import sys

def get_staged_files():
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        return []
    return [f for f in result.stdout.strip().split('\n')
            if f.endswith('.py') and not f.startswith('tests/')]

def find_hash_eq_classes(filepath):
    """Returns list of (class_name, has_hash, has_eq, has_hash_none)"""
    try:
        with open(filepath) as f:
            tree = ast.parse(f.read())
    except (SyntaxError, FileNotFoundError) as e:
        print(f"Warning: Could not parse {filepath}: {e}")
        return []

    results = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            has_hash = has_eq = has_hash_none = False
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if item.name == '__hash__':
                        has_hash = True
                    elif item.name == '__eq__':
                        has_eq = True
                elif isinstance(item, ast.Assign):
                    # Check for __hash__ = None
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == '__hash__':
                            if isinstance(item.value, ast.Constant) and item.value.value is None:
                                has_hash_none = True

            if has_hash or has_eq:
                results.append((node.name, has_hash, has_eq, has_hash_none))
    return results
```

Warning message format:
```
WARNING: Class 'MyClass' in src/clams/foo.py defines __hash__/__eq__ but has no contract test.

Add a test to tests/test_data_contracts.py:

    def test_myclass_hash_eq_contract(self):
        obj1 = MyClass(...)
        obj2 = MyClass(...)
        if obj1 == obj2:
            assert hash(obj1) == hash(obj2), "Hash/eq contract violation"

See BUG-028 for why this matters.
```

## Testing Requirements

All tests automated via pytest:

- [ ] Test: hook detects new `__hash__` method in staged file
- [ ] Test: hook detects new `__eq__` method in staged file
- [ ] Test: hook ignores classes already tested in `test_data_contracts.py`
- [ ] Test: hook ignores test files (paths starting with `tests/`)
- [ ] Test: hook handles missing `test_data_contracts.py` (warns on everything)
- [ ] Test: hook handles file with syntax error (warns and continues)
- [ ] Test: hook handles deleted staged file (skips gracefully)
- [ ] Test: hook detects `__hash__ = None` and skips warning
- [ ] Test: hook exits 0 even when warnings found

## Out of Scope

- Hash/eq contract tests themselves (SPEC-047, SPEC-048)
- Automatic test generation
- Blocking mode (future enhancement if requested)
- Integration with `.pre-commit-config.yaml` (can be added later)
