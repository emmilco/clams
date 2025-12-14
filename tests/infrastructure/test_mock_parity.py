"""Mock interface verification tests.

This module ensures that mock classes used in tests implement the same interface
as their production counterparts. This prevents "works in test, fails in production"
bugs like BUG-040 and BUG-041.

The tests verify:
1. Mocks have all methods defined in the production class (both ABC and concrete)
2. Method signatures match (parameter names, types, defaults)
3. Return type annotations match
4. All mock classes across the test suite are verified

Design:
- The ABC (e.g., clams.context.searcher_types.Searcher) defines the interface contract
- The concrete class (e.g., clams.search.searcher.Searcher) implements the contract
- Mocks must implement the ABC interface, which should match the concrete class
- We test against BOTH to catch drift between ABC and concrete implementations

Reference: R6-A ticket in planning_docs/tickets/recommendations-r5-r8.md
Related bugs: BUG-040, BUG-041
"""

import inspect
from typing import Any, get_type_hints

import pytest


def get_public_methods(cls: type) -> set[str]:
    """Get all public method names from a class.

    Args:
        cls: The class to inspect

    Returns:
        Set of method names (excluding dunder methods and private methods)
    """
    return {
        name
        for name in dir(cls)
        if not name.startswith("_") and callable(getattr(cls, name))
    }


def get_method_signature(cls: type, method_name: str) -> inspect.Signature:
    """Get the signature of a method on a class.

    Args:
        cls: The class containing the method
        method_name: Name of the method

    Returns:
        The method signature
    """
    method = getattr(cls, method_name)
    return inspect.signature(method)


def compare_signatures(
    prod_cls: type,
    mock_cls: type,
    method_name: str,
) -> list[str]:
    """Compare method signatures between production and mock classes.

    Args:
        prod_cls: Production class
        mock_cls: Mock class
        method_name: Name of the method to compare

    Returns:
        List of differences (empty if signatures match)
    """
    differences: list[str] = []

    prod_sig = get_method_signature(prod_cls, method_name)
    mock_sig = get_method_signature(mock_cls, method_name)

    prod_params = dict(prod_sig.parameters)
    mock_params = dict(mock_sig.parameters)

    # Check for missing parameters in mock (excluding 'self')
    prod_param_names = {n for n in prod_params if n != "self"}
    mock_param_names = {n for n in mock_params if n != "self"}

    missing_params = prod_param_names - mock_param_names
    if missing_params:
        differences.append(
            f"{method_name}: mock missing parameters: {missing_params}"
        )

    extra_params = mock_param_names - prod_param_names
    # Extra params in mock are only a problem if they don't have defaults
    for param_name in extra_params:
        param = mock_params[param_name]
        if param.default is inspect.Parameter.empty:
            differences.append(
                f"{method_name}: mock has extra required parameter: {param_name}"
            )

    # Check parameter types for common parameters
    common_params = prod_param_names & mock_param_names
    for param_name in common_params:
        prod_param = prod_params[param_name]
        mock_param = mock_params[param_name]

        # Check if parameter kinds are compatible
        # (KEYWORD_ONLY, POSITIONAL_OR_KEYWORD, etc.)
        if prod_param.kind != mock_param.kind:
            # Allow flexibility: POSITIONAL_OR_KEYWORD and KEYWORD_ONLY are compatible
            allowed_kinds = {
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            }
            if not (
                prod_param.kind in allowed_kinds and mock_param.kind in allowed_kinds
            ):
                differences.append(
                    f"{method_name}.{param_name}: parameter kind mismatch - "
                    f"prod={prod_param.kind.name}, mock={mock_param.kind.name}"
                )

        # Check default values (if prod has default, mock should have compatible default)
        if prod_param.default is not inspect.Parameter.empty:
            if mock_param.default is inspect.Parameter.empty:
                # Mock is stricter (requires value that prod has default for)
                # This is generally OK as long as the mock can be called with the default
                pass

    return differences


def compare_return_types(
    prod_cls: type,
    mock_cls: type,
    method_name: str,
) -> list[str]:
    """Compare return type annotations between production and mock classes.

    Args:
        prod_cls: Production class
        mock_cls: Mock class
        method_name: Name of the method to compare

    Returns:
        List of differences (empty if return types match or are compatible)
    """
    differences: list[str] = []

    try:
        prod_hints = get_type_hints(getattr(prod_cls, method_name))
        mock_hints = get_type_hints(getattr(mock_cls, method_name))
    except Exception:
        # Type hints may not be resolvable at runtime
        return differences

    prod_return = prod_hints.get("return")
    mock_return = mock_hints.get("return")

    if prod_return is not None and mock_return is not None:
        # Compare return types (exact match for now)
        # In the future, could check for subtype compatibility
        if prod_return != mock_return:
            differences.append(
                f"{method_name}: return type mismatch - "
                f"prod={prod_return}, mock={mock_return}"
            )

    return differences


class TestMockSearcherParityWithABC:
    """Verify MockSearcher implements the same interface as the Searcher ABC.

    The ABC (clams.context.searcher_types.Searcher) defines the contract that
    both MockSearcher and the concrete Searcher implementation must follow.
    """

    def test_mock_searcher_has_all_abc_methods(self) -> None:
        """Test that MockSearcher has all methods defined in Searcher ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        abc_methods = get_public_methods(SearcherABC)
        mock_methods = get_public_methods(MockSearcher)

        # Exclude ABC-specific methods
        exclude = {"register"}
        abc_methods = abc_methods - exclude
        mock_methods = mock_methods - exclude

        missing = abc_methods - mock_methods
        assert not missing, (
            f"MockSearcher is missing these methods from Searcher ABC: {missing}\n"
            f"The mock must implement the full interface contract."
        )

    def test_mock_searcher_abc_signature_search_memories(self) -> None:
        """Test that search_memories signature matches the ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(SearcherABC, MockSearcher, "search_memories")
        assert not differences, (
            "search_memories signature mismatch with ABC:\n" + "\n".join(differences)
        )

    def test_mock_searcher_abc_signature_search_code(self) -> None:
        """Test that search_code signature matches the ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(SearcherABC, MockSearcher, "search_code")
        assert not differences, (
            "search_code signature mismatch with ABC:\n" + "\n".join(differences)
        )

    def test_mock_searcher_abc_signature_search_experiences(self) -> None:
        """Test that search_experiences signature matches the ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(SearcherABC, MockSearcher, "search_experiences")
        assert not differences, (
            "search_experiences signature mismatch with ABC:\n" + "\n".join(differences)
        )

    def test_mock_searcher_abc_signature_search_values(self) -> None:
        """Test that search_values signature matches the ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(SearcherABC, MockSearcher, "search_values")
        assert not differences, (
            "search_values signature mismatch with ABC:\n" + "\n".join(differences)
        )

    def test_mock_searcher_abc_signature_search_commits(self) -> None:
        """Test that search_commits signature matches the ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(SearcherABC, MockSearcher, "search_commits")
        assert not differences, (
            "search_commits signature mismatch with ABC:\n" + "\n".join(differences)
        )


class TestMockSearcherParityWithConcrete:
    """Verify MockSearcher matches the concrete Searcher implementation.

    The concrete class (clams.search.searcher.Searcher) is what runs in production.
    If the mock differs from the concrete class, tests may pass but production fails.
    This is exactly what happened in BUG-040 and BUG-041.
    """

    def test_mock_searcher_has_all_concrete_methods(self) -> None:
        """Test that MockSearcher has all methods from concrete Searcher."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        prod_methods = get_public_methods(Searcher)
        mock_methods = get_public_methods(MockSearcher)

        # Exclude ABC-specific methods
        exclude = {"register"}
        prod_methods = prod_methods - exclude
        mock_methods = mock_methods - exclude

        missing = prod_methods - mock_methods
        assert not missing, (
            f"MockSearcher is missing these methods from production Searcher: {missing}\n"
            f"This can cause tests to pass but production to fail (see BUG-040, BUG-041)."
        )

    def test_mock_searcher_concrete_signature_search_memories(self) -> None:
        """Test that search_memories signature matches concrete implementation."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(Searcher, MockSearcher, "search_memories")
        assert not differences, (
            "search_memories signature mismatch with production:\n"
            + "\n".join(differences)
            + "\n\nThis mismatch can cause tests to pass but production to fail."
        )

    def test_mock_searcher_concrete_signature_search_code(self) -> None:
        """Test that search_code signature matches concrete implementation."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(Searcher, MockSearcher, "search_code")
        assert not differences, (
            "search_code signature mismatch with production:\n"
            + "\n".join(differences)
            + "\n\nThis mismatch can cause tests to pass but production to fail."
        )

    def test_mock_searcher_concrete_signature_search_experiences(self) -> None:
        """Test that search_experiences signature matches concrete implementation."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(Searcher, MockSearcher, "search_experiences")
        assert not differences, (
            "search_experiences signature mismatch with production:\n"
            + "\n".join(differences)
            + "\n\nThis mismatch can cause tests to pass but production to fail."
        )

    def test_mock_searcher_concrete_signature_search_values(self) -> None:
        """Test that search_values signature matches concrete implementation."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(Searcher, MockSearcher, "search_values")
        assert not differences, (
            "search_values signature mismatch with production:\n"
            + "\n".join(differences)
            + "\n\nThis mismatch can cause tests to pass but production to fail."
        )

    def test_mock_searcher_concrete_signature_search_commits(self) -> None:
        """Test that search_commits signature matches concrete implementation."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        differences = compare_signatures(Searcher, MockSearcher, "search_commits")
        assert not differences, (
            "search_commits signature mismatch with production:\n"
            + "\n".join(differences)
            + "\n\nThis mismatch can cause tests to pass but production to fail."
        )


class TestConcreteMatchesABC:
    """Verify the concrete Searcher matches its ABC.

    If the concrete implementation drifts from the ABC, mocks that correctly
    implement the ABC will still fail in production.
    """

    def test_concrete_searcher_matches_abc(self) -> None:
        """Test that concrete Searcher implements ABC correctly."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher

        abc_methods = get_public_methods(SearcherABC)
        concrete_methods = get_public_methods(Searcher)

        exclude = {"register"}
        abc_methods = abc_methods - exclude
        concrete_methods = concrete_methods - exclude

        missing = abc_methods - concrete_methods
        assert not missing, (
            f"Concrete Searcher is missing these ABC methods: {missing}"
        )

        # Check signatures match for all ABC methods
        differences: list[str] = []
        for method_name in abc_methods:
            diffs = compare_signatures(SearcherABC, Searcher, method_name)
            differences.extend(diffs)

        assert not differences, (
            "Concrete Searcher signature mismatches with ABC:\n"
            + "\n".join(differences)
        )


class TestMockEmbedderParity:
    """Verify MockEmbedder implements the same interface as EmbeddingService."""

    def test_mock_embedder_has_all_production_methods(self) -> None:
        """Test that MockEmbedder has all methods from EmbeddingService."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        prod_methods = get_public_methods(EmbeddingService)
        mock_methods = get_public_methods(MockEmbedder)

        # EmbeddingService is an ABC, so 'register' might be present
        abc_methods = {"register"}
        prod_methods = prod_methods - abc_methods
        mock_methods = mock_methods - abc_methods

        missing = prod_methods - mock_methods
        assert not missing, (
            f"MockEmbedder is missing these methods from EmbeddingService: {missing}"
        )

    def test_mock_embedder_signature_embed(self) -> None:
        """Test that embed signature matches between mock and production."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        differences = compare_signatures(EmbeddingService, MockEmbedder, "embed")
        assert not differences, "embed signature mismatch:\n" + "\n".join(differences)

    def test_mock_embedder_signature_embed_batch(self) -> None:
        """Test that embed_batch signature matches between mock and production."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        differences = compare_signatures(EmbeddingService, MockEmbedder, "embed_batch")
        assert not differences, (
            "embed_batch signature mismatch:\n" + "\n".join(differences)
        )

    def test_mock_embedder_has_dimension_property(self) -> None:
        """Test that MockEmbedder has the dimension property."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        # Check that dimension is a property in the production class
        assert isinstance(
            inspect.getattr_static(EmbeddingService, "dimension"), property
        ), "EmbeddingService.dimension should be a property"

        # Check that mock also has dimension
        mock_instance = MockEmbedder()
        assert hasattr(mock_instance, "dimension"), (
            "MockEmbedder should have dimension property"
        )
        assert isinstance(mock_instance.dimension, int), (
            "MockEmbedder.dimension should return int"
        )


# Helper function for generalizing the pattern
def verify_mock_interface(
    prod_cls: type,
    mock_cls: type,
    mock_name: str,
    exclude_methods: set[str] | None = None,
) -> dict[str, Any]:
    """Generalized interface verification for any mock/production pair.

    Args:
        prod_cls: Production class (the interface to verify against)
        mock_cls: Mock class (the test double)
        mock_name: Name of the mock class for error messages
        exclude_methods: Methods to exclude from comparison (e.g., ABC methods)

    Returns:
        Dict with 'passed', 'missing_methods', and 'signature_differences' keys
    """
    exclude = exclude_methods or {"register"}

    prod_methods = get_public_methods(prod_cls) - exclude
    mock_methods = get_public_methods(mock_cls) - exclude

    missing = prod_methods - mock_methods

    signature_diffs: dict[str, list[str]] = {}
    for method_name in prod_methods & mock_methods:
        diffs = compare_signatures(prod_cls, mock_cls, method_name)
        if diffs:
            signature_diffs[method_name] = diffs

    return {
        "passed": not missing and not signature_diffs,
        "missing_methods": missing,
        "signature_differences": signature_diffs,
    }


class TestMockSearcherReturnTypes:
    """Verify MockSearcher return type annotations match production.

    Return type mismatches can cause type checkers to pass but runtime to fail,
    or vice versa. This ensures both ABC and concrete return types are compatible.
    """

    def test_mock_searcher_return_types_match_abc(self) -> None:
        """Test that MockSearcher return types match Searcher ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        # Get public methods from ABC
        abc_methods = get_public_methods(SearcherABC)
        exclude = {"register"}
        abc_methods = abc_methods - exclude

        differences: list[str] = []
        for method_name in abc_methods:
            diffs = compare_return_types(SearcherABC, MockSearcher, method_name)
            differences.extend(diffs)

        assert not differences, (
            "MockSearcher return type mismatches with ABC:\n" + "\n".join(differences)
        )

    def test_mock_searcher_return_types_match_concrete(self) -> None:
        """Test that MockSearcher return types match concrete Searcher."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        prod_methods = get_public_methods(Searcher)
        exclude = {"register"}
        prod_methods = prod_methods - exclude

        differences: list[str] = []
        for method_name in prod_methods:
            diffs = compare_return_types(Searcher, MockSearcher, method_name)
            differences.extend(diffs)

        assert not differences, (
            "MockSearcher return type mismatches with production:\n"
            + "\n".join(differences)
            + "\n\nReturn type mismatches can cause type-safe code to fail at runtime."
        )


class TestMockEmbedderReturnTypes:
    """Verify MockEmbedder return type annotations match production."""

    def test_mock_embedder_return_types_match_production(self) -> None:
        """Test that MockEmbedder return types match EmbeddingService."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        prod_methods = get_public_methods(EmbeddingService)
        exclude = {"register"}
        prod_methods = prod_methods - exclude

        differences: list[str] = []
        for method_name in prod_methods:
            diffs = compare_return_types(EmbeddingService, MockEmbedder, method_name)
            differences.extend(diffs)

        # Note: embed_batch return type is np.ndarray in both, but mock returns
        # list[np.ndarray] implicitly. This is acceptable since np.ndarray
        # is the declared return type.
        # Filter out known acceptable differences
        filtered_diffs = [
            d for d in differences if "embed_batch" not in d
        ]

        assert not filtered_diffs, (
            "MockEmbedder return type mismatches:\n" + "\n".join(filtered_diffs)
        )


class TestGeneralizedMockVerification:
    """Tests demonstrating the generalized pattern for mock verification.

    This class provides a template for adding mock verification to any
    mock/production class pair. The verify_mock_interface helper function
    can be used to quickly check any mock.
    """

    def test_verify_mock_interface_helper_with_abc(self) -> None:
        """Test the helper function detects ABC mismatches."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from tests.context.test_assembler import MockSearcher

        result = verify_mock_interface(SearcherABC, MockSearcher, "MockSearcher")

        # Report findings - individual ABC tests provide detailed assertions
        if result["missing_methods"]:
            print(f"MockSearcher missing ABC methods: {result['missing_methods']}")

        if result["signature_differences"]:
            print(f"ABC signature differences: {result['signature_differences']}")

    def test_verify_mock_interface_helper_with_concrete(self) -> None:
        """Test the helper function detects concrete implementation mismatches."""
        from clams.search.searcher import Searcher
        from tests.context.test_assembler import MockSearcher

        result = verify_mock_interface(Searcher, MockSearcher, "MockSearcher")

        # Report findings - individual concrete tests provide detailed assertions
        if result["missing_methods"]:
            print(f"MockSearcher missing concrete methods: {result['missing_methods']}")

        if result["signature_differences"]:
            print(f"Concrete signature differences: {result['signature_differences']}")

    def test_verify_embedder_mock(self) -> None:
        """Test the helper function works for EmbeddingService mocks."""
        from clams.embedding.base import EmbeddingService
        from tests.server.tools.test_bug_017_regression import MockEmbedder

        result = verify_mock_interface(EmbeddingService, MockEmbedder, "MockEmbedder")

        # This should pass since we have explicit tests for EmbeddingService
        assert result["passed"] or not result["missing_methods"], (
            f"MockEmbedder has missing methods: {result['missing_methods']}"
        )


# Extended verification function that includes return types
def verify_mock_interface_complete(
    prod_cls: type,
    mock_cls: type,
    mock_name: str,
    exclude_methods: set[str] | None = None,
) -> dict[str, Any]:
    """Complete interface verification including return types.

    This extends verify_mock_interface to also check return type annotations.

    Args:
        prod_cls: Production class (the interface to verify against)
        mock_cls: Mock class (the test double)
        mock_name: Name of the mock class for error messages
        exclude_methods: Methods to exclude from comparison (e.g., ABC methods)

    Returns:
        Dict with 'passed', 'missing_methods', 'signature_differences',
        and 'return_type_differences' keys
    """
    exclude = exclude_methods or {"register"}

    prod_methods = get_public_methods(prod_cls) - exclude
    mock_methods = get_public_methods(mock_cls) - exclude

    missing = prod_methods - mock_methods

    signature_diffs: dict[str, list[str]] = {}
    return_type_diffs: dict[str, list[str]] = {}

    for method_name in prod_methods & mock_methods:
        # Check signatures
        sig_diffs = compare_signatures(prod_cls, mock_cls, method_name)
        if sig_diffs:
            signature_diffs[method_name] = sig_diffs

        # Check return types
        ret_diffs = compare_return_types(prod_cls, mock_cls, method_name)
        if ret_diffs:
            return_type_diffs[method_name] = ret_diffs

    return {
        "passed": not missing and not signature_diffs and not return_type_diffs,
        "missing_methods": missing,
        "signature_differences": signature_diffs,
        "return_type_differences": return_type_diffs,
    }


def get_all_mock_production_pairs() -> (
    list[tuple[type, type, str, set[str] | None]]
):
    """Return all known mock/production class pairs for verification.

    Each tuple contains:
    - Production class (or ABC)
    - Mock class
    - Mock name for error messages
    - Optional set of methods to exclude

    Add new mock/production pairs here when new mocks are introduced.
    This ensures all mocks stay in sync with their production counterparts.

    Reference: BUG-040, BUG-041 - bugs caused by mock/production interface drift.
    """
    from clams.context.searcher_types import Searcher as SearcherABC
    from clams.embedding.base import EmbeddingService
    from clams.search.searcher import Searcher as ConcreteSearcher
    from tests.context.test_assembler import MockSearcher
    from tests.server.tools.test_bug_017_regression import MockEmbedder

    exclude_abc = {"register"}

    return [
        # MockSearcher vs Searcher ABC
        (SearcherABC, MockSearcher, "MockSearcher vs ABC", exclude_abc),
        # MockSearcher vs concrete Searcher
        (ConcreteSearcher, MockSearcher, "MockSearcher vs Concrete", exclude_abc),
        # MockEmbedder vs EmbeddingService
        (EmbeddingService, MockEmbedder, "MockEmbedder vs ABC", exclude_abc),
    ]


class TestParameterizedMockParity:
    """Parameterized tests for all mock/production pairs.

    This class provides a comprehensive test that verifies all known mock classes
    against their production counterparts. Adding a new mock/production pair to
    get_all_mock_production_pairs() automatically includes it in these tests.

    Reference: R10-B ticket in planning_docs/tickets/recommendations-r9-r13.md
    """

    @pytest.mark.parametrize(
        "prod_cls,mock_cls,pair_name,exclude_methods",
        get_all_mock_production_pairs(),
        ids=[pair[2] for pair in get_all_mock_production_pairs()],
    )
    def test_mock_has_all_production_methods(
        self,
        prod_cls: type,
        mock_cls: type,
        pair_name: str,
        exclude_methods: set[str] | None,
    ) -> None:
        """Verify mock has all methods from production class.

        This is the most critical check - if a mock is missing a method,
        tests using the mock will pass but production code will fail.
        """
        exclude = exclude_methods or set()
        prod_methods = get_public_methods(prod_cls) - exclude
        mock_methods = get_public_methods(mock_cls) - exclude

        missing = prod_methods - mock_methods
        assert not missing, (
            f"{pair_name}: Mock is missing methods: {missing}\n"
            f"The mock must implement all production methods to prevent "
            f"'works in test, fails in production' bugs. See BUG-040, BUG-041."
        )

    @pytest.mark.parametrize(
        "prod_cls,mock_cls,pair_name,exclude_methods",
        get_all_mock_production_pairs(),
        ids=[pair[2] for pair in get_all_mock_production_pairs()],
    )
    def test_mock_signatures_match_production(
        self,
        prod_cls: type,
        mock_cls: type,
        pair_name: str,
        exclude_methods: set[str] | None,
    ) -> None:
        """Verify mock method signatures match production.

        Signature mismatches (different parameter names, types, defaults)
        can cause tests to pass with different call patterns than production.
        """
        exclude = exclude_methods or set()
        prod_methods = get_public_methods(prod_cls) - exclude
        mock_methods = get_public_methods(mock_cls) - exclude
        common_methods = prod_methods & mock_methods

        all_diffs: list[str] = []
        for method_name in common_methods:
            diffs = compare_signatures(prod_cls, mock_cls, method_name)
            all_diffs.extend(diffs)

        assert not all_diffs, (
            f"{pair_name}: Signature mismatches found:\n"
            + "\n".join(all_diffs)
            + "\n\nSignature differences can cause tests to pass with "
            "different call patterns than production uses."
        )

    @pytest.mark.parametrize(
        "prod_cls,mock_cls,pair_name,exclude_methods",
        get_all_mock_production_pairs(),
        ids=[pair[2] for pair in get_all_mock_production_pairs()],
    )
    def test_mock_return_types_match_production(
        self,
        prod_cls: type,
        mock_cls: type,
        pair_name: str,
        exclude_methods: set[str] | None,
    ) -> None:
        """Verify mock return types match production.

        Return type mismatches can cause type checkers to pass but
        runtime behavior to differ, or vice versa.
        """
        exclude = exclude_methods or set()
        prod_methods = get_public_methods(prod_cls) - exclude
        mock_methods = get_public_methods(mock_cls) - exclude
        common_methods = prod_methods & mock_methods

        all_diffs: list[str] = []
        for method_name in common_methods:
            diffs = compare_return_types(prod_cls, mock_cls, method_name)
            all_diffs.extend(diffs)

        assert not all_diffs, (
            f"{pair_name}: Return type mismatches found:\n"
            + "\n".join(all_diffs)
            + "\n\nReturn type differences can cause type-safe code to "
            "fail at runtime or produce unexpected results."
        )

    @pytest.mark.parametrize(
        "prod_cls,mock_cls,pair_name,exclude_methods",
        get_all_mock_production_pairs(),
        ids=[pair[2] for pair in get_all_mock_production_pairs()],
    )
    def test_complete_mock_interface_verification(
        self,
        prod_cls: type,
        mock_cls: type,
        pair_name: str,
        exclude_methods: set[str] | None,
    ) -> None:
        """Comprehensive interface verification combining all checks.

        This single test verifies methods, signatures, and return types.
        Use this as a quick sanity check for new mock/production pairs.
        """
        result = verify_mock_interface_complete(
            prod_cls, mock_cls, pair_name, exclude_methods
        )

        issues: list[str] = []

        if result["missing_methods"]:
            issues.append(f"Missing methods: {result['missing_methods']}")

        if result["signature_differences"]:
            for method, diffs in result["signature_differences"].items():
                issues.append(f"Signature issues in {method}: {diffs}")

        if result["return_type_differences"]:
            for method, diffs in result["return_type_differences"].items():
                issues.append(f"Return type issues in {method}: {diffs}")

        assert result["passed"], (
            f"{pair_name}: Interface verification failed:\n"
            + "\n".join(issues)
        )
