"""Regression tests for Searcher ABC inheritance.

These tests verify that the concrete Searcher class maintains proper
inheritance from the abstract Searcher interface. This prevents
interface drift bugs like BUG-040 and BUG-041.
"""

import inspect

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
        abstract_methods: frozenset[str] = getattr(
            Searcher, "__abstractmethods__", frozenset()
        )
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

    @pytest.mark.parametrize("method_name", EXPECTED_METHODS)
    def test_method_signatures_match_abc(self, method_name: str) -> None:
        """Verify method signatures in concrete Searcher match the ABC.

        This regression test ensures parameter names remain synchronized
        between the abstract interface and concrete implementation.
        BUG-041 was caused by signature drift between these classes.
        """
        abc_method = getattr(SearcherABC, method_name)
        concrete_method = getattr(Searcher, method_name)

        abc_sig = inspect.signature(abc_method)
        concrete_sig = inspect.signature(concrete_method)

        # Parameter names should match exactly
        abc_params = list(abc_sig.parameters.keys())
        concrete_params = list(concrete_sig.parameters.keys())

        assert abc_params == concrete_params, (
            f"Method {method_name} parameter names don't match:\n"
            f"  ABC: {abc_params}\n"
            f"  Concrete: {concrete_params}"
        )
