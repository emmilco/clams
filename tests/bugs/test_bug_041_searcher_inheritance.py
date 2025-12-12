"""Regression tests for BUG-041: Searcher class inheritance.

This test ensures that the concrete Searcher class properly inherits from the
abstract Searcher ABC, establishing proper type safety for components like
ContextAssembler that depend on the Searcher interface.

BUG-041: Searcher class conflict - abstract vs concrete incompatible interfaces
Root cause: The concrete Searcher in search/searcher.py was not inheriting from
the abstract Searcher in context/searcher_types.py, causing a type system gap.
"""

from unittest.mock import MagicMock

import pytest


def test_searcher_is_subclass_of_abc() -> None:
    """Verify concrete Searcher is a subclass of abstract Searcher ABC."""
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    # Concrete Searcher must inherit from ABC
    assert issubclass(Searcher, SearcherABC), (
        "Concrete Searcher must be a subclass of SearcherABC. "
        "This ensures type safety when passing Searcher to components "
        "that expect the abstract interface (like ContextAssembler)."
    )


def test_searcher_instance_is_abc_instance() -> None:
    """Verify Searcher instances are also instances of the ABC."""
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    # Create a concrete Searcher instance with mock dependencies
    embedding_service = MagicMock()
    vector_store = MagicMock()
    searcher = Searcher(embedding_service, vector_store)

    # Instance must pass isinstance check for ABC
    assert isinstance(searcher, SearcherABC), (
        "Concrete Searcher instance must be an instance of SearcherABC. "
        "This is required for duck typing and type checking to work correctly."
    )


def test_searcher_implements_all_abstract_methods() -> None:
    """Verify concrete Searcher implements all abstract methods."""
    from clams.search.searcher import Searcher

    # Create instance with mock dependencies
    embedding_service = MagicMock()
    vector_store = MagicMock()
    searcher = Searcher(embedding_service, vector_store)

    # All abstract methods must be implemented
    required_methods = [
        "search_memories",
        "search_code",
        "search_experiences",
        "search_values",
        "search_commits",
    ]

    for method_name in required_methods:
        assert hasattr(searcher, method_name), (
            f"Searcher must implement {method_name}"
        )
        method = getattr(searcher, method_name)
        assert callable(method), f"{method_name} must be callable"


def test_context_assembler_accepts_concrete_searcher() -> None:
    """Verify ContextAssembler can accept concrete Searcher (type safety)."""
    from clams.context.assembler import ContextAssembler
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    # Create concrete searcher with mock dependencies
    embedding_service = MagicMock()
    vector_store = MagicMock()
    searcher = Searcher(embedding_service, vector_store)

    # Verify it's an instance of the ABC (type safety check)
    assert isinstance(searcher, SearcherABC)

    # Should be accepted by ContextAssembler without type errors
    assembler = ContextAssembler(searcher)

    # Verify the searcher was properly assigned
    assert assembler._searcher is searcher


@pytest.mark.asyncio
async def test_concrete_searcher_methods_are_callable() -> None:
    """Verify concrete Searcher methods can be called with ABC signature.

    This test verifies that calling the search methods with just the minimal
    required parameters (as the ABC originally defined) still works.
    """
    from unittest.mock import AsyncMock

    from clams.search.searcher import Searcher

    # Create instance with async mocks that return empty results
    embedding_service = MagicMock()
    embedding_service.embed = AsyncMock(return_value=[0.0] * 384)
    vector_store = MagicMock()
    vector_store.search = AsyncMock(return_value=[])

    searcher = Searcher(embedding_service, vector_store)

    # All methods should be callable with minimal arguments (query only)
    # The extra parameters in the concrete implementation have defaults
    await searcher.search_memories(query="test")
    await searcher.search_code(query="test")
    await searcher.search_experiences(query="test")
    await searcher.search_values(query="test")
    await searcher.search_commits(query="test")

    # If we get here without exceptions, the methods are properly callable


def test_abc_method_signatures_match_concrete() -> None:
    """Verify ABC method signatures are compatible with concrete implementation.

    The ABC should define all parameters that the concrete implementation supports,
    with appropriate defaults, so that type checkers are satisfied.
    """
    import inspect

    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.search.searcher import Searcher

    method_names = [
        "search_memories",
        "search_code",
        "search_experiences",
        "search_values",
        "search_commits",
    ]

    for method_name in method_names:
        abc_method = getattr(SearcherABC, method_name)
        concrete_method = getattr(Searcher, method_name)

        abc_sig = inspect.signature(abc_method)
        concrete_sig = inspect.signature(concrete_method)

        # Parameter names should match between ABC and concrete
        abc_params = list(abc_sig.parameters.keys())
        concrete_params = list(concrete_sig.parameters.keys())

        assert abc_params == concrete_params, (
            f"Method {method_name} parameters don't match:\n"
            f"  ABC: {abc_params}\n"
            f"  Concrete: {concrete_params}"
        )
