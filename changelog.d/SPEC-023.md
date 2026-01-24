## SPEC-023: Mock Interface Verification Tests

### Summary
Added systematic tests to verify mock classes implement the same interface as production counterparts, preventing mock drift bugs.

### Changes
- Added `tests/infrastructure/test_mock_parity.py` with 39 tests covering:
  - MockSearcher verification against both ABC and concrete Searcher
  - MockEmbedder verification against EmbeddingService ABC
  - MockExperienceResult verification against ExperienceResult dataclass
  - Parameterized tests via central registries
- Helper functions: `get_public_methods()`, `compare_signatures()`, `compare_return_types()`
- Central registries: `get_all_mock_production_pairs()`, `get_all_mock_dataclass_pairs()`
- Added docstrings to mock classes referencing test_mock_parity.py
- Prevents BUG-040, BUG-041 class issues (mock field name mismatches)
