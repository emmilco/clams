## SPEC-049: Pre-commit Hook for Hash/Eq Contract

### Summary
Created an advisory pre-commit hook that warns when classes define __hash__ or __eq__ without corresponding contract tests.

### Changes
- Added `.claude/hooks/check_hash_eq.py` for AST-based detection
- Detects __hash__, __eq__, and __hash__ = None patterns
- Checks for tests in `tests/context/test_data_contracts.py`
- Advisory mode (exits 0) to avoid blocking commits
- References BUG-028 in warnings for context
