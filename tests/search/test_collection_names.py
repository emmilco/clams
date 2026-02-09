"""Regression tests for BUG-079: CollectionName.CODE consistency.

Ensures the CollectionName.CODE constant matches the actual collection name
used by CodeIndexer and that ALL_COLLECTIONS in backups uses only
CollectionName constants (no hardcoded strings).
"""

from calm.indexers.indexer import CodeIndexer
from calm.orchestration.backups import ALL_COLLECTIONS
from calm.search.collections import CollectionName


class TestCollectionNameConsistency:
    """BUG-079: Verify collection name constants are consistent across modules."""

    def test_collection_name_code_matches_code_indexer(self) -> None:
        """CollectionName.CODE must equal CodeIndexer.COLLECTION_NAME.

        If these drift apart, the Searcher (which uses CollectionName.CODE)
        will query a different collection than the one CodeIndexer writes to,
        causing CollectionNotFoundError.
        """
        assert CollectionName.CODE == CodeIndexer.COLLECTION_NAME

    def test_collection_name_code_is_code_units(self) -> None:
        """CollectionName.CODE must be 'code_units' (the actual Qdrant collection)."""
        assert CollectionName.CODE == "code_units"

    def test_all_collections_uses_only_collection_name_constants(self) -> None:
        """ALL_COLLECTIONS in backups must use CollectionName constants only.

        This test verifies that every entry in ALL_COLLECTIONS is a known
        CollectionName constant, preventing hardcoded strings from sneaking in.
        """
        known_constants = {
            CollectionName.MEMORIES,
            CollectionName.CODE,
            CollectionName.EXPERIENCES_FULL,
            CollectionName.EXPERIENCES_STRATEGY,
            CollectionName.EXPERIENCES_SURPRISE,
            CollectionName.EXPERIENCES_ROOT_CAUSE,
            CollectionName.VALUES,
            CollectionName.COMMITS,
        }

        for collection in ALL_COLLECTIONS:
            assert collection in known_constants, (
                f"ALL_COLLECTIONS contains '{collection}' which is not a "
                f"CollectionName constant. Use CollectionName.* instead of "
                f"hardcoded strings."
            )

    def test_all_collections_contains_code(self) -> None:
        """ALL_COLLECTIONS must include the CODE collection for backups."""
        assert CollectionName.CODE in ALL_COLLECTIONS
