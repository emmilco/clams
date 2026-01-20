# SPEC-049: Pre-commit Hook for Hash/Eq Contract

## Problem Statement

BUG-028 revealed that `ContextItem.__hash__` used the first 100 characters but `__eq__` used the full content. This violates Python's fundamental hash/eq contract: if `a == b`, then `hash(a) == hash(b)`. Such violations cause silent bugs in set/dict operations.

These contract violations can be introduced silently without any test or CI failure. A pre-commit hook would catch new `__hash__` or `__eq__` implementations that lack corresponding contract tests.

**Reference**: R16-C from bug pattern analysis (Theme T14: Hash/Eq Contract Violations)

## Proposed Solution

Create an advisory pre-commit hook that:
1. Detects new or modified `__hash__` or `__eq__` methods in staged files
2. Warns if no corresponding test exists in `tests/test_data_contracts.py`
3. Provides guidance on adding contract tests

The hook is advisory (warning, not blocking) because not all hash/eq implementations need tests immediately.

## Acceptance Criteria

- [ ] Pre-commit hook script `.claude/hooks/check_hash_eq.py` created
- [ ] Hook detects `def __hash__` and `def __eq__` in staged Python files
- [ ] Hook checks if class name appears in `tests/test_data_contracts.py`
- [ ] Hook prints warning with guidance if test is missing
- [ ] Hook is advisory only (exits 0 even when warning)
- [ ] Hook can be run manually: `python .claude/hooks/check_hash_eq.py`
- [ ] Hook documented in `.pre-commit-config.yaml` (if project uses pre-commit)
- [ ] Hook ignores test files themselves (no infinite loop)
- [ ] Hook provides clear guidance on what test to add

## Implementation Notes

Detection approach:
```python
import ast
import subprocess

# Get staged Python files
staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '--diff-filter=AM'])
py_files = [f for f in staged.decode().split('\n') if f.endswith('.py')]

# Parse each file and find __hash__ or __eq__ methods
for file in py_files:
    tree = ast.parse(open(file).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name in ('__hash__', '__eq__'):
                    # Check if class is tested
                    ...
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

- Test hook detects new `__hash__` method
- Test hook detects new `__eq__` method
- Test hook ignores classes already in test_data_contracts.py
- Test hook ignores test files
- Test hook exits 0 (advisory only)
- Manual test: stage a new __hash__ method, run hook

## Out of Scope

- Hash/eq contract tests themselves (covered by SPEC-047, SPEC-048)
- Automatic test generation
- Blocking mode (future enhancement if needed)
