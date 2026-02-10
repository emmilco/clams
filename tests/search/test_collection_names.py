"""Regression tests for BUG-079: CollectionName.CODE_UNITS consistency.

Ensures the CollectionName.CODE_UNITS constant matches the actual collection name
used by CodeIndexer and that ALL_COLLECTIONS in backups uses only
CollectionName constants (no hardcoded strings).
"""

from calm.indexers.indexer import CodeIndexer
from calm.orchestration.backups import ALL_COLLECTIONS
from calm.search.collections import CollectionName


class TestCollectionNameConsistency:
    """BUG-079: Verify collection name constants are consistent across modules."""

    def test_collection_name_code_matches_code_indexer(self) -> None:
        """CollectionName.CODE_UNITS must equal CodeIndexer.COLLECTION_NAME.

        If these drift apart, the Searcher (which uses CollectionName.CODE_UNITS)
        will query a different collection than the one CodeIndexer writes to,
        causing CollectionNotFoundError.
        """
        assert CollectionName.CODE_UNITS == CodeIndexer.COLLECTION_NAME

    def test_collection_name_code_is_code_units(self) -> None:
        """CollectionName.CODE_UNITS must be 'code_units' (the actual Qdrant collection)."""
        assert CollectionName.CODE_UNITS == "code_units"

    def test_all_collections_uses_only_collection_name_constants(self) -> None:
        """ALL_COLLECTIONS in backups must use CollectionName constants only.

        This test verifies that every entry in ALL_COLLECTIONS is a known
        CollectionName constant, preventing hardcoded strings from sneaking in.
        """
        known_constants = {
            CollectionName.MEMORIES,
            CollectionName.CODE_UNITS,
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
        assert CollectionName.CODE_UNITS in ALL_COLLECTIONS


class TestCollectionNameNamingConsistency:
    """BUG-087: Verify CollectionName members have values matching their lowercase names."""

    def test_code_units_value_matches_name(self) -> None:
        """CollectionName.CODE_UNITS.value must be 'code_units'.

        BUG-087 regression: The enum member name should match the Qdrant
        collection name to avoid confusion. CODE was renamed to CODE_UNITS
        so the Python name matches the storage name.
        """
        assert CollectionName.CODE_UNITS == "code_units"

    def test_non_experience_collection_names_match_lowercase_member_names(self) -> None:
        """Non-experience CollectionName members should have values matching their lowercase names.

        BUG-087 regression: Ensures consistency between Python constant names
        and actual Qdrant collection names. For example, MEMORIES -> 'memories',
        CODE_UNITS -> 'code_units', COMMITS -> 'commits'.

        Experience collections (EXPERIENCES_*) use the 'ghap_' prefix for their
        Qdrant collection names, so they are excluded from this check.
        """
        # These members use a different naming scheme (ghap_ prefix)
        skip = {"EXPERIENCE_AXES", "EXPERIENCES_FULL", "EXPERIENCES_STRATEGY",
                "EXPERIENCES_SURPRISE", "EXPERIENCES_ROOT_CAUSE"}
        for attr_name in dir(CollectionName):
            if attr_name.startswith("_"):
                continue
            if attr_name in skip:
                continue
            value = getattr(CollectionName, attr_name)
            if not isinstance(value, str):
                continue
            expected = attr_name.lower()
            assert value == expected, (
                f"CollectionName.{attr_name} = {value!r} but expected "
                f"{expected!r} (lowercase of member name). "
                f"Rename the member or fix the value."
            )

    def test_no_code_member_exists(self) -> None:
        """CollectionName must NOT have a bare CODE member.

        BUG-087 regression: CODE was renamed to CODE_UNITS. Ensure the old
        name does not reappear.
        """
        assert not hasattr(CollectionName, "CODE"), (
            "CollectionName.CODE should not exist. "
            "Use CollectionName.CODE_UNITS instead."
        )
