# SPEC-015: Technical Proposal

## Problem Statement

The codebase maintains an abstract `Searcher` interface in `clams.context.searcher_types` that defines the contract for semantic search operations, with a concrete implementation in `clams.search.searcher`. Previous bugs (BUG-040, BUG-041) demonstrated that mock searchers in tests can drift from the production interface, causing test-production divergence. Without a regression test that explicitly validates the inheritance relationship and interface compliance, future changes could accidentally break the ABC-implementation contract without immediate detection.

## Proposed Solution

Add a new test file `tests/search/test_searcher_interface.py` that explicitly verifies:
1. The concrete `Searcher` class inherits from the `Searcher` ABC
2. All abstract methods defined in the ABC are implemented in the concrete class
3. The concrete class can be instantiated (is not abstract itself)
4. Expected method signatures are present

### Test File Location

```
tests/search/test_searcher_interface.py
```

This location is consistent with the existing test structure (`tests/search/test_searcher.py` already exists for behavior tests).

### Test Structure

The test file will contain the following test functions:

```python
"""Regression tests for Searcher ABC inheritance.

These tests verify that the concrete Searcher class maintains proper
inheritance from the abstract Searcher interface. This prevents
interface drift bugs like BUG-040 and BUG-041.
"""

import inspect
from typing import get_type_hints

import pytest

from clams.context.searcher_types import Searcher as SearcherABC
from clams.search.searcher import Searcher


class TestSearcherInheritance:
    """Tests for Searcher ABC inheritance compliance."""

    def test_searcher_inherits_from_abc(self) -> None:
        """Verify Searcher is a subclass of SearcherABC."""
        assert issubclass(Searcher, SearcherABC), (
            "Searcher must inherit from SearcherABC (clams.context.searcher_types.Searcher)"
        )

    def test_searcher_is_not_abstract(self) -> None:
        """Verify Searcher can be instantiated (all abstract methods implemented)."""
        # If there are any unimplemented abstract methods, this will fail
        # We check this by inspecting __abstractmethods__
        abstract_methods = getattr(Searcher, "__abstractmethods__", frozenset())
        assert len(abstract_methods) == 0, (
            f"Searcher has unimplemented abstract methods: {abstract_methods}"
        )

    def test_all_abc_methods_implemented(self) -> None:
        """Verify all abstract methods from SearcherABC exist on Searcher."""
        # Get the abstract methods from the ABC
        abc_abstract_methods = SearcherABC.__abstractmethods__

        for method_name in abc_abstract_methods:
            assert hasattr(Searcher, method_name), (
                f"Searcher missing abstract method: {method_name}"
            )
            # Verify it's actually a method (not just an attribute)
            method = getattr(Searcher, method_name)
            assert callable(method), (
                f"Searcher.{method_name} is not callable"
            )


class TestSearcherMethodSignatures:
    """Tests for expected method presence."""

    EXPECTED_METHODS = [
        "search_memories",
        "search_code",
        "search_experiences",
        "search_values",
        "search_commits",
    ]

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_expected_method_exists(self, method_name: str) -> None:
        """Verify each expected method exists on Searcher."""
        assert hasattr(Searcher, method_name), (
            f"Searcher missing expected method: {method_name}"
        )

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_expected_method_is_async(self, method_name: str) -> None:
        """Verify each expected method is an async method."""
        method = getattr(Searcher, method_name)
        assert inspect.iscoroutinefunction(method), (
            f"Searcher.{method_name} should be async"
        )
```

## Design Decisions

### Why Separate Test File

A dedicated test file for interface compliance keeps these structural tests separate from behavioral tests in `test_searcher.py`. This makes it clear that these tests are regression guards, not feature tests.

### Why Not Test Instantiation With Mocks

The spec mentions "Test verifies `Searcher` can be instantiated (not left abstract)". Rather than actually instantiating with mock dependencies (which is covered in `test_searcher.py`), we check `__abstractmethods__` directly. This is more robust because:
1. It catches the issue at the class level, not instance level
2. It doesn't require setting up mocks
3. It provides clearer error messages about which methods are missing

### Why Parametrized Tests

Using `@pytest.mark.parametrize` for the expected methods list makes test output clearer (each method gets its own test case) and makes it easy to add new methods to the list as the interface evolves.

### Why Check Async

The ABC methods are all async, so we verify the concrete implementations are async too. This prevents a scenario where someone accidentally implements a sync method that shadows the ABC's async method.

## Implementation Checklist

1. Create `tests/search/test_searcher_interface.py` with the test code above
2. Run tests to verify they pass: `pytest tests/search/test_searcher_interface.py -v`
3. Verify tests would fail if inheritance is broken (manual verification by temporarily modifying imports)

## Dependencies

None. This spec adds tests only and does not modify production code.

## Test Requirements (from spec)

- [x] Test file exists at `tests/search/test_searcher_interface.py`
- [x] Test verifies `Searcher` (from `clams.search.searcher`) is a subclass of `Searcher` ABC (from `clams.context.searcher_types`)
- [x] Test verifies `Searcher` can be instantiated (not left abstract) - via `__abstractmethods__` check
- [x] Test verifies all ABC abstract methods are implemented in the concrete class
- [x] Test includes assertions that the Searcher class has expected methods: `search_memories`, `search_code`, `search_experiences`, `search_values`, `search_commits`
- [x] Tests run in CI and fail if inheritance is broken - standard pytest tests

## Risks

Low. This is a pure test addition that does not touch production code.
