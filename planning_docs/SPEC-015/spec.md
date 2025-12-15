# SPEC-015: Add Searcher ABC Inheritance Regression Test

## Problem Statement

The codebase has an abstract `Searcher` interface defined in `src/clams/context/searcher_types.py` and a concrete implementation in `src/clams/search/searcher.py`. Previous bugs (BUG-040, BUG-041) showed that mock searchers in tests drifted from the production interface, causing test-production divergence.

A regression test is needed to verify that:
1. The concrete `Searcher` class properly inherits from the `Searcher` ABC
2. All abstract methods are implemented
3. The inheritance relationship is not accidentally broken

## Proposed Solution

Add a simple regression test that verifies the Searcher class inheritance relationship and interface compliance.

## Acceptance Criteria

- [ ] Test file exists at `tests/search/test_searcher_interface.py`
- [ ] Test verifies `Searcher` (from `clams.search.searcher`) is a subclass of `Searcher` ABC (from `clams.context.searcher_types`)
- [ ] Test verifies `Searcher` can be instantiated (not left abstract) by checking `__abstractmethods__` is empty
- [ ] Test verifies all ABC abstract methods are implemented in the concrete class
- [ ] Test includes assertions that the Searcher class has expected methods: `search_memories`, `search_code`, `search_experiences`, `search_values`, `search_commits`
- [ ] Tests run in CI and fail if inheritance is broken

## Implementation Notes

- The ABC is at `src/clams/context/searcher_types.py` (class `Searcher`)
- The concrete implementation is at `src/clams/search/searcher.py` (class `Searcher`)
- Use `issubclass()` and `inspect` module to verify inheritance and method presence
- Example test pattern:
  ```python
  from clams.context.searcher_types import Searcher as SearcherABC
  from clams.search.searcher import Searcher

  def test_searcher_inherits_from_abc():
      assert issubclass(Searcher, SearcherABC)

  def test_searcher_implements_all_abstract_methods():
      # Verify it's not abstract (can be instantiated with deps)
      abstract_methods = SearcherABC.__abstractmethods__
      for method in abstract_methods:
          assert hasattr(Searcher, method)
  ```

## Testing Requirements

- Test must fail if `Searcher` stops inheriting from the ABC
- Test must fail if any abstract method is removed from concrete class
- Test must run as part of standard test suite (not just CI)

## Out of Scope

- Testing mock searchers match production interface (covered by SPEC-023)
- Testing method behavior or return values (covered by existing integration tests)
