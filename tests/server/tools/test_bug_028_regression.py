"""Regression test for BUG-028: ContextItem hash/eq contract should be consistent."""

from clams.context.models import ContextItem


class TestContextItemHashEqContract:
    """Test that ContextItem hash and eq are consistent."""

    def test_equal_items_have_equal_hash(self) -> None:
        """Verify if a == b, then hash(a) == hash(b)."""
        item1 = ContextItem(
            source="memory",
            content="Test content",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="memory",
            content="Test content",
            relevance=0.8,  # Different relevance, but same source/content
            metadata={"key": "value"},  # Different metadata
        )

        # Items with same source and content should be equal
        assert item1 == item2
        # Equal items MUST have equal hashes
        assert hash(item1) == hash(item2)

    def test_items_with_different_length_have_different_hash(self) -> None:
        """BUG-028: Items with same 100-char prefix but different length should have different hash.

        Previously, hash only used first 100 chars, so items with same prefix
        but different full content had the same hash but weren't equal.
        """
        prefix = "A" * 100
        item1 = ContextItem(
            source="file.py",
            content=prefix + "X",  # 101 chars
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="file.py",
            content=prefix + "XY",  # 102 chars
            relevance=0.9,
            metadata={},
        )

        # Items are NOT equal (different content)
        assert item1 != item2
        # Items should have different hashes (different lengths)
        assert hash(item1) != hash(item2)

    def test_items_with_same_prefix_different_suffix_in_set(self) -> None:
        """BUG-028: Items with same prefix but different content should both be in set."""
        prefix = "A" * 100
        item1 = ContextItem(
            source="file.py",
            content=prefix + "X",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="file.py",
            content=prefix + "Y",
            relevance=0.9,
            metadata={},
        )

        # Both should be in the set (they're different items)
        s = {item1, item2}
        assert len(s) == 2
        assert item1 in s
        assert item2 in s

    def test_identical_items_deduplicate_in_set(self) -> None:
        """Verify identical items are deduplicated in a set."""
        item1 = ContextItem(
            source="memory",
            content="Same content",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="memory",
            content="Same content",
            relevance=0.8,
            metadata={"different": "metadata"},
        )

        # Should deduplicate (same source + content)
        s = {item1, item2}
        assert len(s) == 1

    def test_items_with_different_source_not_equal(self) -> None:
        """Verify items with different sources are not equal."""
        item1 = ContextItem(
            source="memory",
            content="Same content",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="code",
            content="Same content",
            relevance=0.9,
            metadata={},
        )

        assert item1 != item2
        # Different sources should have different hashes
        assert hash(item1) != hash(item2)

    def test_dict_key_behavior(self) -> None:
        """Verify ContextItem works correctly as dict key."""
        item1 = ContextItem(
            source="memory",
            content="Content 1",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="memory",
            content="Content 2",
            relevance=0.9,
            metadata={},
        )
        item1_copy = ContextItem(
            source="memory",
            content="Content 1",
            relevance=0.5,
            metadata={"different": True},
        )

        d = {item1: "first", item2: "second"}

        # Can lookup by equal item
        assert d[item1_copy] == "first"
        assert len(d) == 2

    def test_short_content_hashes_correctly(self) -> None:
        """Verify items with content < 100 chars hash correctly."""
        item1 = ContextItem(
            source="memory",
            content="Short",
            relevance=0.9,
            metadata={},
        )
        item2 = ContextItem(
            source="memory",
            content="Short",
            relevance=0.9,
            metadata={},
        )

        assert item1 == item2
        assert hash(item1) == hash(item2)
