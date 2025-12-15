## SPEC-015: Add Searcher ABC Inheritance Regression Test

### Summary
Added regression tests to verify the concrete `Searcher` class properly inherits from the abstract `Searcher` ABC, preventing interface drift bugs like BUG-040 and BUG-041.

### Changes
- Added `tests/search/test_searcher_interface.py` with 13 tests
- Tests verify ABC inheritance via `issubclass()`
- Tests verify instantiability via `__abstractmethods__` check
- Tests verify all 5 expected methods exist and are async
- Fixed pre-existing linter errors (UP017, E402) in test files
