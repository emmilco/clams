## SPEC-047: Hash/eq contract tests for ContextItem (R16-A)

### Summary
Added comprehensive tests to verify ContextItem maintains Python's hash/eq contract, preventing silent bugs in set/dict operations.

### Changes
- Added `tests/context/test_data_contracts.py` with 19 tests covering:
  - Hash/eq contract invariant verification
  - Edge cases (prefix collisions, unicode, whitespace, empty content)
  - Set membership and deduplication consistency
  - Dict key lookup consistency
  - Property-based testing with hypothesis
- Tests reference BUG-028 which originally identified the contract violation
