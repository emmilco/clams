## SPEC-015: Add Searcher ABC inheritance regression test

### Summary
Added parametrized test to verify method signatures between Searcher ABC and concrete implementation stay synchronized.

### Changes
- Added `test_method_signatures_match_abc` to `tests/search/test_searcher_interface.py`
- Tests all 5 search methods for parameter name consistency
