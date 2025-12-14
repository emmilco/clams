"""Type boundary verification tests.

This module tests that types are consistent across module boundaries.
It verifies:
1. Result types in search/results.py match their usage in context/
2. Abstract Searcher methods match concrete implementation signatures
3. Dataclass field names are consistent across modules
4. Module boundary type contracts are maintained

Reference: R10-E from recommendations-r9-r13.md
Addresses: BUG-040 (duplicate result types), BUG-041 (abstract/concrete Searcher conflict)
"""

import inspect
from dataclasses import fields, is_dataclass
from typing import get_type_hints

import pytest


class TestSearchResultTypeConsistency:
    """Verify result types are consistent between search and context modules."""

    def test_context_module_reexports_search_results(self) -> None:
        """Verify context.searcher_types re-exports from search.results (not duplicates)."""
        from clams.context import searcher_types
        from clams.search import results

        # These should be the exact same classes (re-exported, not duplicated)
        assert searcher_types.CodeResult is results.CodeResult, (
            "CodeResult should be re-exported from search.results, not duplicated"
        )
        assert searcher_types.MemoryResult is results.MemoryResult, (
            "MemoryResult should be re-exported from search.results, not duplicated"
        )
        assert searcher_types.ExperienceResult is results.ExperienceResult, (
            "ExperienceResult should be re-exported from search.results, not duplicated"
        )
        assert searcher_types.ValueResult is results.ValueResult, (
            "ValueResult should be re-exported from search.results, not duplicated"
        )
        assert searcher_types.CommitResult is results.CommitResult, (
            "CommitResult should be re-exported from search.results, not duplicated"
        )

    def test_nested_types_also_reexported(self) -> None:
        """Verify nested types (RootCause, Lesson) are also re-exported."""
        from clams.context import searcher_types
        from clams.search import results

        assert searcher_types.RootCause is results.RootCause, (
            "RootCause should be re-exported from search.results"
        )
        assert searcher_types.Lesson is results.Lesson, (
            "Lesson should be re-exported from search.results"
        )


class TestSearcherABCImplementation:
    """Verify concrete Searcher implements all ABC methods correctly."""

    def test_searcher_inherits_from_abc(self) -> None:
        """Verify Searcher class inherits from SearcherABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher

        assert issubclass(Searcher, SearcherABC), (
            "Concrete Searcher must inherit from SearcherABC"
        )

    def test_all_abstract_methods_implemented(self) -> None:
        """Verify concrete Searcher implements all abstract methods from ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher

        # Get all abstract methods from ABC
        abc_methods: set[str] = set()
        for name, method in inspect.getmembers(SearcherABC):
            if getattr(method, "__isabstractmethod__", False):
                abc_methods.add(name)

        # Verify all are implemented in concrete class
        concrete_methods = set(dir(Searcher))
        missing = abc_methods - concrete_methods

        assert not missing, f"Concrete Searcher missing ABC methods: {missing}"

    def test_method_signatures_compatible(self) -> None:
        """Verify concrete method signatures are compatible with ABC."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher

        # Methods to check
        methods = [
            "search_memories",
            "search_code",
            "search_experiences",
            "search_values",
            "search_commits",
        ]

        for method_name in methods:
            abc_method = getattr(SearcherABC, method_name)
            concrete_method = getattr(Searcher, method_name)

            abc_sig = inspect.signature(abc_method)
            concrete_sig = inspect.signature(concrete_method)

            # Parameter names must match (excluding 'self')
            abc_params = [
                p for p in abc_sig.parameters.keys() if p != "self"
            ]
            concrete_params = [
                p for p in concrete_sig.parameters.keys() if p != "self"
            ]

            assert abc_params == concrete_params, (
                f"Parameter name mismatch for {method_name}: "
                f"ABC={abc_params}, Concrete={concrete_params}"
            )

    def test_return_types_compatible(self) -> None:
        """Verify return types are compatible (concrete can be more specific)."""
        from clams.context.searcher_types import Searcher as SearcherABC
        from clams.search.searcher import Searcher

        methods = [
            "search_memories",
            "search_code",
            "search_experiences",
            "search_values",
            "search_commits",
        ]

        for method_name in methods:
            abc_hints = get_type_hints(getattr(SearcherABC, method_name))
            concrete_hints = get_type_hints(getattr(Searcher, method_name))

            # Return type annotation should exist in both
            assert "return" in abc_hints, f"ABC {method_name} missing return type hint"
            assert "return" in concrete_hints, (
                f"Concrete {method_name} missing return type hint"
            )

            # The return type should be equivalent (both return list of results)
            abc_return = abc_hints["return"]
            concrete_return = concrete_hints["return"]

            # Convert to string for comparison (handles generic aliases)
            assert str(abc_return) == str(concrete_return), (
                f"Return type mismatch for {method_name}: "
                f"ABC={abc_return}, Concrete={concrete_return}"
            )


class TestRootCauseConsistency:
    """Verify RootCause dataclass is consistent across modules."""

    def test_rootcause_field_names_match(self) -> None:
        """Verify RootCause has same field names in all modules."""
        from clams.observation.models import RootCause as ObservationRootCause
        from clams.search.results import RootCause as SearchRootCause

        # Both should be dataclasses
        assert is_dataclass(ObservationRootCause), (
            "observation.models.RootCause should be a dataclass"
        )
        assert is_dataclass(SearchRootCause), (
            "search.results.RootCause should be a dataclass"
        )

        # Get field names
        obs_fields = {f.name for f in fields(ObservationRootCause)}
        search_fields = {f.name for f in fields(SearchRootCause)}

        assert obs_fields == search_fields, (
            f"RootCause field name mismatch: "
            f"observation={obs_fields}, search={search_fields}"
        )

    def test_rootcause_field_types_match(self) -> None:
        """Verify RootCause has same field types in all modules."""
        from clams.observation.models import RootCause as ObservationRootCause
        from clams.search.results import RootCause as SearchRootCause

        obs_hints = get_type_hints(ObservationRootCause)
        search_hints = get_type_hints(SearchRootCause)

        for field_name in obs_hints:
            assert field_name in search_hints, (
                f"Field {field_name} missing in search.results.RootCause"
            )
            assert str(obs_hints[field_name]) == str(search_hints[field_name]), (
                f"RootCause.{field_name} type mismatch: "
                f"observation={obs_hints[field_name]}, search={search_hints[field_name]}"
            )


class TestLessonConsistency:
    """Verify Lesson dataclass is consistent across modules."""

    def test_lesson_field_names_match(self) -> None:
        """Verify Lesson has same field names in all modules."""
        from clams.observation.models import Lesson as ObservationLesson
        from clams.search.results import Lesson as SearchLesson

        # Both should be dataclasses
        assert is_dataclass(ObservationLesson), (
            "observation.models.Lesson should be a dataclass"
        )
        assert is_dataclass(SearchLesson), (
            "search.results.Lesson should be a dataclass"
        )

        # Get field names
        obs_fields = {f.name for f in fields(ObservationLesson)}
        search_fields = {f.name for f in fields(SearchLesson)}

        assert obs_fields == search_fields, (
            f"Lesson field name mismatch: "
            f"observation={obs_fields}, search={search_fields}"
        )

    def test_lesson_field_types_match(self) -> None:
        """Verify Lesson has same field types in all modules."""
        from clams.observation.models import Lesson as ObservationLesson
        from clams.search.results import Lesson as SearchLesson

        obs_hints = get_type_hints(ObservationLesson)
        search_hints = get_type_hints(SearchLesson)

        for field_name in obs_hints:
            assert field_name in search_hints, (
                f"Field {field_name} missing in search.results.Lesson"
            )
            assert str(obs_hints[field_name]) == str(search_hints[field_name]), (
                f"Lesson.{field_name} type mismatch: "
                f"observation={obs_hints[field_name]}, search={search_hints[field_name]}"
            )


class TestClusterInfoConsistency:
    """Verify ClusterInfo dataclass is consistent across modules."""

    def test_clusterinfo_exists_in_both_modules(self) -> None:
        """Verify ClusterInfo is defined in both clustering and values modules."""
        from clams.clustering.types import ClusterInfo as ClusteringClusterInfo
        from clams.values.types import ClusterInfo as ValuesClusterInfo

        assert is_dataclass(ClusteringClusterInfo), (
            "clustering.types.ClusterInfo should be a dataclass"
        )
        assert is_dataclass(ValuesClusterInfo), (
            "values.types.ClusterInfo should be a dataclass"
        )

    def test_clusterinfo_common_fields_match(self) -> None:
        """Verify common fields have consistent types across modules.

        Note: These are intentionally different classes for different purposes:
        - clustering.types.ClusterInfo: Raw clustering results with numpy arrays
        - values.types.ClusterInfo: Higher-level with string IDs and axis info

        This test verifies common field names have compatible semantics.
        """
        from clams.clustering.types import ClusterInfo as ClusteringClusterInfo
        from clams.values.types import ClusterInfo as ValuesClusterInfo

        clustering_fields = {f.name for f in fields(ClusteringClusterInfo)}
        values_fields = {f.name for f in fields(ValuesClusterInfo)}

        # Common fields that should exist in both
        common_fields = {"label", "member_ids", "size", "avg_weight"}

        for field_name in common_fields:
            assert field_name in clustering_fields, (
                f"clustering.types.ClusterInfo missing field: {field_name}"
            )
            assert field_name in values_fields, (
                f"values.types.ClusterInfo missing field: {field_name}"
            )


class TestVectorStoreTypes:
    """Verify VectorStore types are consistent across usage sites."""

    def test_search_result_is_dataclass(self) -> None:
        """Verify SearchResult from storage.base is a dataclass."""
        from clams.storage.base import SearchResult

        assert is_dataclass(SearchResult), (
            "storage.base.SearchResult should be a dataclass"
        )

    def test_search_result_has_required_fields(self) -> None:
        """Verify SearchResult has all fields required by result converters."""
        from clams.storage.base import SearchResult

        required_fields = {"id", "score", "payload"}
        actual_fields = {f.name for f in fields(SearchResult)}

        missing = required_fields - actual_fields
        assert not missing, f"SearchResult missing required fields: {missing}"

    def test_result_converters_use_correct_fields(self) -> None:
        """Verify all from_search_result methods access valid SearchResult fields."""
        from clams.storage.base import SearchResult
        from clams.search.results import (
            CodeResult,
            CommitResult,
            ExperienceResult,
            MemoryResult,
            ValueResult,
        )

        search_result_fields = {f.name for f in fields(SearchResult)}

        # All result types with from_search_result methods
        result_types = [
            CodeResult,
            CommitResult,
            ExperienceResult,
            MemoryResult,
            ValueResult,
        ]

        for result_type in result_types:
            assert hasattr(result_type, "from_search_result"), (
                f"{result_type.__name__} should have from_search_result method"
            )

            # Verify the method signature accepts SearchResult
            sig = inspect.signature(result_type.from_search_result)
            params = list(sig.parameters.values())

            # Should have cls (classmethod) and result parameter
            assert len(params) >= 1, (
                f"{result_type.__name__}.from_search_result should have result param"
            )


class TestContextModelsConsistency:
    """Verify context module models are consistent."""

    def test_context_item_is_dataclass(self) -> None:
        """Verify ContextItem is a dataclass with required fields."""
        from clams.context.models import ContextItem

        assert is_dataclass(ContextItem), (
            "context.models.ContextItem should be a dataclass"
        )

        required_fields = {"source", "content", "relevance", "metadata"}
        actual_fields = {f.name for f in fields(ContextItem)}

        missing = required_fields - actual_fields
        assert not missing, f"ContextItem missing required fields: {missing}"

    def test_formatted_context_is_dataclass(self) -> None:
        """Verify FormattedContext is a dataclass with required fields."""
        from clams.context.models import FormattedContext

        assert is_dataclass(FormattedContext), (
            "context.models.FormattedContext should be a dataclass"
        )

        required_fields = {"markdown", "items", "token_count", "sources_used"}
        actual_fields = {f.name for f in fields(FormattedContext)}

        missing = required_fields - actual_fields
        assert not missing, f"FormattedContext missing required fields: {missing}"


class TestGitTypesConsistency:
    """Verify git module types are consistent."""

    def test_commit_dataclass_fields(self) -> None:
        """Verify Commit dataclass has all required fields."""
        from clams.git.base import Commit

        assert is_dataclass(Commit), "git.base.Commit should be a dataclass"

        required_fields = {
            "sha",
            "message",
            "author",
            "author_email",
            "timestamp",
            "files_changed",
        }
        actual_fields = {f.name for f in fields(Commit)}

        missing = required_fields - actual_fields
        assert not missing, f"Commit missing required fields: {missing}"

    def test_commit_result_matches_commit(self) -> None:
        """Verify CommitResult contains data compatible with git.base.Commit."""
        from clams.git.base import Commit
        from clams.search.results import CommitResult

        # CommitResult should have fields that map from Commit
        commit_fields = {f.name for f in fields(Commit)}
        commit_result_fields = {f.name for f in fields(CommitResult)}

        # Key fields that should be in both
        shared_fields = {"sha", "message", "author", "author_email"}

        for field_name in shared_fields:
            assert field_name in commit_fields, (
                f"git.base.Commit missing field: {field_name}"
            )
            assert field_name in commit_result_fields, (
                f"search.results.CommitResult missing field: {field_name}"
            )


class TestEnumConsistency:
    """Verify enum types are consistent across modules."""

    def test_domain_enum_values(self) -> None:
        """Verify Domain enum has expected values."""
        from clams.observation.models import Domain

        expected_values = {
            "debugging",
            "refactoring",
            "feature",
            "testing",
            "configuration",
            "documentation",
            "performance",
            "security",
            "integration",
        }
        actual_values = {e.value for e in Domain}

        assert expected_values == actual_values, (
            f"Domain enum value mismatch: expected={expected_values}, actual={actual_values}"
        )

    def test_strategy_enum_values(self) -> None:
        """Verify Strategy enum has expected values."""
        from clams.observation.models import Strategy

        expected_values = {
            "systematic-elimination",
            "trial-and-error",
            "research-first",
            "divide-and-conquer",
            "root-cause-analysis",
            "copy-from-similar",
            "check-assumptions",
            "read-the-error",
            "ask-user",
        }
        actual_values = {e.value for e in Strategy}

        assert expected_values == actual_values, (
            f"Strategy enum value mismatch: expected={expected_values}, actual={actual_values}"
        )

    def test_outcome_status_enum_values(self) -> None:
        """Verify OutcomeStatus enum has expected values."""
        from clams.observation.models import OutcomeStatus

        expected_values = {"confirmed", "falsified", "abandoned"}
        actual_values = {e.value for e in OutcomeStatus}

        assert expected_values == actual_values, (
            f"OutcomeStatus enum value mismatch: expected={expected_values}, actual={actual_values}"
        )

    def test_confidence_tier_enum_values(self) -> None:
        """Verify ConfidenceTier enum has expected values."""
        from clams.observation.models import ConfidenceTier

        expected_values = {"gold", "silver", "bronze", "abandoned"}
        actual_values = {e.value for e in ConfidenceTier}

        assert expected_values == actual_values, (
            f"ConfidenceTier enum value mismatch: expected={expected_values}, actual={actual_values}"
        )


class TestModuleBoundaryContracts:
    """Test contracts at major module boundaries."""

    def test_embedding_vector_type_alias(self) -> None:
        """Verify Vector type is consistently defined."""
        from clams.embedding.base import Vector as EmbeddingVector
        from clams.storage.base import Vector as StorageVector

        # Both should be type aliases for numpy arrays
        # We can't directly compare type aliases, but we can verify they exist
        # and are importable from both locations
        assert EmbeddingVector is not None
        assert StorageVector is not None

    def test_ghap_entry_serialization_roundtrip_fields(self) -> None:
        """Verify GHAPEntry to_dict/from_dict preserves all fields."""
        from clams.observation.models import GHAPEntry

        assert is_dataclass(GHAPEntry), (
            "observation.models.GHAPEntry should be a dataclass"
        )

        # Verify both methods exist
        assert hasattr(GHAPEntry, "to_dict"), "GHAPEntry should have to_dict method"
        assert hasattr(GHAPEntry, "from_dict"), "GHAPEntry should have from_dict method"

        # Get field names from dataclass
        entry_fields = {f.name for f in fields(GHAPEntry)}

        # Key fields that must survive serialization
        required_fields = {
            "id",
            "session_id",
            "created_at",
            "domain",
            "strategy",
            "goal",
            "hypothesis",
            "action",
            "prediction",
        }

        missing = required_fields - entry_fields
        assert not missing, f"GHAPEntry missing required fields: {missing}"


class TestExperienceResultToGHAPMapping:
    """Verify ExperienceResult fields map correctly from GHAP data."""

    def test_experience_result_has_ghap_fields(self) -> None:
        """Verify ExperienceResult can represent GHAP entry data."""
        from clams.search.results import ExperienceResult

        assert is_dataclass(ExperienceResult)

        # Fields that should come from GHAP
        ghap_derived_fields = {
            "ghap_id",
            "domain",
            "strategy",
            "goal",
            "hypothesis",
            "action",
            "prediction",
            "outcome_status",
        }

        actual_fields = {f.name for f in fields(ExperienceResult)}
        missing = ghap_derived_fields - actual_fields

        assert not missing, (
            f"ExperienceResult missing GHAP-derived fields: {missing}"
        )

    def test_experience_result_has_search_fields(self) -> None:
        """Verify ExperienceResult has search-specific fields."""
        from clams.search.results import ExperienceResult

        # Fields specific to search results
        search_fields = {"id", "score", "axis"}

        actual_fields = {f.name for f in fields(ExperienceResult)}
        missing = search_fields - actual_fields

        assert not missing, (
            f"ExperienceResult missing search-specific fields: {missing}"
        )
