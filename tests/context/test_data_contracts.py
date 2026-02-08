"""Tests for hash/eq contracts across the codebase.

Python's hash/eq contract requires:
- If a == b, then hash(a) == hash(b)
- If hash(a) != hash(b), then a != b

Violating this contract causes silent bugs in set/dict operations:
1. Set operations become unpredictable (item not found even though equal item exists)
2. Dict key lookups fail silently
3. Deduplication produces wrong results

## Hashable Classes Audit (2026-01-28)

Classes tested in this file:
- ContextItem (src/clams/context/models.py) - custom __hash__/__eq__

Classes tested in tests/utils/test_platform_contracts.py:
- PlatformInfo (src/clams/utils/platform.py) - frozen dataclass

Classes excluded (Enums use identity-based hash/eq, always correct):
- Domain, Strategy, OutcomeStatus, ConfidenceTier (observation/models.py)
- UnitType (indexers/base.py)

All other dataclasses are NOT hashable (no frozen=True or __hash__).

Reference: BUG-028 - ContextItem hash/eq contract violation
"""

from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from calm.context.models import ContextItem


def verify_hash_eq_contract[T](
    cls: type[T],
    *args: Any,
    **kwargs: Any,
) -> None:
    """Verify hash/eq contract for any class.

    Creates two instances with the same arguments and verifies:
    1. They are equal
    2. They have the same hash (contract requirement)
    3. Set membership is consistent
    4. Dict key lookup is consistent

    Args:
        cls: Class to test
        *args: Positional arguments for constructor
        **kwargs: Keyword arguments for constructor

    Raises:
        AssertionError: If contract is violated
    """
    obj1 = cls(*args, **kwargs)
    obj2 = cls(*args, **kwargs)

    # Basic equality check
    assert obj1 == obj2, (
        f"{cls.__name__}: instances with same args must be equal"
    )

    # Contract: equal objects must have equal hashes
    assert hash(obj1) == hash(obj2), (
        f"{cls.__name__} violates hash/eq contract: "
        f"equal objects have different hashes "
        f"(hash1={hash(obj1)}, hash2={hash(obj2)})"
    )

    # Set membership must be consistent
    s: set[T] = {obj1}
    assert obj2 in s, (
        f"{cls.__name__}: equal object not found in set "
        f"(contract violation)"
    )

    # Dict key lookup must be consistent
    d: dict[T, str] = {obj1: "value"}
    assert d.get(obj2) == "value", (
        f"{cls.__name__}: equal object cannot find dict entry "
        f"(contract violation)"
    )


class TestContextItemContract:
    """Verify ContextItem maintains hash/eq contract.

    The hash/eq contract is fundamental to Python's data model:
    - If two objects are equal (a == b), they MUST have the same hash
    - If two objects have different hashes, they MUST NOT be equal
    - Note: Objects may have the same hash but still be unequal (collisions are allowed)

    Violating this contract breaks set/dict operations.
    """

    def test_equal_items_have_equal_hashes(self) -> None:
        """INVARIANT: if a == b then hash(a) == hash(b).

        This is the fundamental contract requirement. Equal items must
        always produce equal hashes for set/dict operations to work correctly.
        """
        item1 = ContextItem(
            source="test",
            content="identical content",
            relevance=0.8,
            metadata={"id": "1"},
        )
        item2 = ContextItem(
            source="test",
            content="identical content",
            relevance=0.9,  # Different relevance, but equality only checks source/content
            metadata={"id": "2"},  # Different metadata
        )

        # Verify they are equal
        assert item1 == item2, "Items with same source/content must be equal"

        # Contract: equal items must have equal hashes
        assert hash(item1) == hash(item2), (
            "Contract violation: equal items must have equal hashes"
        )

    def test_contract_holds_for_short_content(self) -> None:
        """Test items with content shorter than 100 chars.

        The hash function uses content[:100], so short content is used entirely.
        This should not cause any contract issues.
        """
        item1 = ContextItem(
            source="test", content="short", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="short", relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: short content items with equal content "
            "must have equal hashes"
        )

    def test_contract_holds_for_exact_100_chars(self) -> None:
        """Test items with content exactly 100 chars.

        Boundary case where content[:100] uses all characters.
        """
        content_100 = "x" * 100
        item1 = ContextItem(
            source="test", content=content_100, relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content=content_100, relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: 100-char content items must have equal hashes "
            "when content is identical"
        )

    def test_contract_holds_for_long_content(self) -> None:
        """Test items with content longer than 100 chars.

        The hash uses content[:100] + len(content), so two items with
        identical content must still produce identical hashes.
        """
        long_content = "x" * 200
        item1 = ContextItem(
            source="test", content=long_content, relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content=long_content, relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: long content items with identical content "
            "must have equal hashes"
        )

    def test_prefix_collision_items_are_not_equal(self) -> None:
        """Items with same first 100 chars but different suffix must not be equal.

        This was the original BUG-028 scenario: hash only used first 100 chars
        but eq used full content, causing items to hash the same but not be equal.

        With the current implementation (hash includes len(content)), these items
        will have different hashes AND be unequal, which satisfies the contract.
        """
        prefix = "x" * 100
        item1 = ContextItem(
            source="test",
            content=prefix + "suffix_a",
            relevance=0.5,
            metadata={},
        )
        item2 = ContextItem(
            source="test",
            content=prefix + "suffix_b",
            relevance=0.5,
            metadata={},
        )

        # These must NOT be equal (different content)
        assert item1 != item2, "Items with different content must not be equal"

        # If they ARE equal (which would be a bug), hashes must match
        # This is a defensive check - if eq is broken, at least verify contract
        if item1 == item2:
            assert hash(item1) == hash(item2), "Contract violation detected"

    def test_whitespace_only_differences(self) -> None:
        """Items with only whitespace differences are still different.

        Whitespace at end, beginning, or internally matters for equality.
        The hash/eq contract must hold regardless.
        """
        # Trailing whitespace
        item1 = ContextItem(
            source="test", content="content", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="content ", relevance=0.5, metadata={}
        )
        assert item1 != item2, "Trailing whitespace makes items different"

        # Internal whitespace
        item3 = ContextItem(
            source="test", content="hello world", relevance=0.5, metadata={}
        )
        item4 = ContextItem(
            source="test", content="hello  world", relevance=0.5, metadata={}
        )
        assert item3 != item4, "Internal whitespace makes items different"

        # Items that ARE equal with whitespace
        item5 = ContextItem(
            source="test", content="  spaced  ", relevance=0.5, metadata={}
        )
        item6 = ContextItem(
            source="test", content="  spaced  ", relevance=0.5, metadata={}
        )
        assert item5 == item6
        assert hash(item5) == hash(item6), (
            "Contract violation: identical whitespace content must have equal hashes"
        )

    def test_empty_content(self) -> None:
        """Items with empty string content.

        Empty content is a boundary case that must satisfy the contract.
        """
        item1 = ContextItem(
            source="test", content="", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="", relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: empty content items must have equal hashes"
        )

    def test_single_character_content(self) -> None:
        """Items with single character content."""
        item1 = ContextItem(
            source="test", content="a", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="a", relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: single-char content must have equal hashes"
        )

    def test_unicode_content(self) -> None:
        """Items with unicode characters.

        Unicode content, including multi-byte characters, must satisfy
        the hash/eq contract. Slicing unicode strings could potentially
        cause issues if done incorrectly (e.g., slicing bytes vs chars).
        """
        # Multi-byte unicode characters
        unicode_content = "\u4e2d\u6587\u6587\u5b57" * 30  # Chinese characters
        item1 = ContextItem(
            source="test", content=unicode_content, relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content=unicode_content, relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: unicode content must have equal hashes"
        )

    def test_unicode_crossing_100_char_boundary(self) -> None:
        """Test unicode where 100-char boundary falls within multi-char sequence.

        This tests that character slicing (not byte slicing) is used correctly.
        """
        # Create content where the 100th char is a unicode character
        prefix = "a" * 99
        unicode_char = "\U0001F600"  # Emoji (4-byte UTF-8)
        content = prefix + unicode_char + "suffix"

        item1 = ContextItem(
            source="test", content=content, relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content=content, relevance=0.5, metadata={}
        )

        assert item1 == item2
        assert hash(item1) == hash(item2), (
            "Contract violation: unicode at 100-char boundary must hash correctly"
        )


class TestContextItemSetBehavior:
    """Test that set operations work correctly with ContextItem.

    Sets rely on hash/eq contract. If violated:
    - Items may not be found even when equal item exists
    - Deduplication may keep duplicates
    - Membership tests may give wrong results
    """

    def test_set_membership_consistent(self) -> None:
        """Equal items should have consistent set membership.

        If item1 is in a set, and item2 == item1, then item2 should
        be found in the set. This fails if hash/eq contract is violated.
        """
        items: set[ContextItem] = set()
        item1 = ContextItem(
            source="test", content="test content", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="test content", relevance=0.5, metadata={}
        )

        items.add(item1)

        # If contract holds, item2 should be "in" the set
        assert item2 in items, (
            "Equal item not found in set (contract violation)"
        )

    def test_set_deduplication_works(self) -> None:
        """Adding equal items to a set should result in only one item.

        This is the primary use case for making ContextItem hashable:
        deduplication in context assembly.
        """
        items: set[ContextItem] = set()
        for i in range(5):
            items.add(
                ContextItem(
                    source="test",
                    content="duplicate content",
                    relevance=float(i) / 10,
                    metadata={"id": str(i)},
                )
            )

        # All items have same source/content, so only one should remain
        assert len(items) == 1, (
            f"Set should contain 1 item after deduplication, got {len(items)}"
        )

    def test_set_distinguishes_different_items(self) -> None:
        """Different items should remain separate in sets.

        This ensures the hash function doesn't cause false deduplication.
        """
        items: set[ContextItem] = set()
        prefix = "x" * 100

        # Add items with same prefix but different content
        for i in range(3):
            items.add(
                ContextItem(
                    source="test",
                    content=prefix + f"_suffix_{i}",
                    relevance=0.5,
                    metadata={},
                )
            )

        # Different content means different items
        assert len(items) == 3, (
            f"Set should contain 3 different items, got {len(items)}"
        )


class TestContextItemDictBehavior:
    """Test that dict operations work correctly with ContextItem.

    Dicts rely on hash/eq contract for key lookup.
    """

    def test_dict_key_lookup_consistent(self) -> None:
        """Equal items should work as dict keys consistently.

        If d[item1] = value, and item2 == item1, then d[item2] should
        return the same value.
        """
        d: dict[ContextItem, str] = {}
        item1 = ContextItem(
            source="test", content="test content", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="test content", relevance=0.5, metadata={}
        )

        d[item1] = "value"

        # If contract holds, item2 should find the same entry
        assert d.get(item2) == "value", (
            "Equal item cannot find dict entry (contract violation)"
        )

    def test_dict_overwrite_with_equal_key(self) -> None:
        """Using equal item as key should overwrite existing entry.

        This verifies that the dict recognizes item2 as the "same" key
        as item1 when they are equal.
        """
        d: dict[ContextItem, str] = {}
        item1 = ContextItem(
            source="test", content="test content", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test",
            content="test content",
            relevance=0.9,  # Different relevance
            metadata={"different": True},  # Different metadata
        )

        d[item1] = "first"
        d[item2] = "second"  # Should overwrite since item1 == item2

        assert len(d) == 1, f"Dict should have 1 entry, got {len(d)}"
        assert d[item1] == "second", "Value should be 'second' after overwrite"
        assert d[item2] == "second", "Value should be 'second' for equal key"


class TestContextItemPropertyBased:
    """Property-based tests using Hypothesis for broader coverage.

    These tests generate random inputs to find edge cases that
    example-based tests might miss.
    """

    @given(
        source=st.text(min_size=1, max_size=20),
        content=st.text(min_size=0, max_size=500),
        relevance=st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
    )
    @settings(max_examples=100)
    def test_contract_invariant_property(
        self, source: str, content: str, relevance: float
    ) -> None:
        """Property: equal items MUST have equal hashes.

        This test generates random source, content, and relevance values
        to verify the contract holds for any input.
        """
        item1 = ContextItem(source, content, relevance, {"id": "1"})
        item2 = ContextItem(source, content, relevance, {"id": "2"})

        # These have same source and content, so they're equal
        assert item1 == item2, "Items with same source/content must be equal"
        # Contract: equal items must have equal hashes
        assert hash(item1) == hash(item2), (
            f"Contract violation: equal items have different hashes.\n"
            f"content length={len(content)}"
        )

    @given(
        source=st.text(min_size=1, max_size=20),
        prefix=st.text(min_size=100, max_size=100),
        suffix1=st.text(min_size=1, max_size=50),
        suffix2=st.text(min_size=1, max_size=50),
    )
    @settings(max_examples=50)
    def test_prefix_collision_property(
        self, source: str, prefix: str, suffix1: str, suffix2: str
    ) -> None:
        """Property: items with same 100-char prefix but different suffixes.

        This specifically targets the BUG-028 scenario with randomized inputs.
        """
        # Skip if suffixes are the same (would make items equal)
        if suffix1 == suffix2:
            return

        item1 = ContextItem(source, prefix + suffix1, 0.5, {})
        item2 = ContextItem(source, prefix + suffix2, 0.5, {})

        # Different suffixes means different content, so not equal
        assert item1 != item2, (
            "Items with different suffixes must not be equal"
        )

        # If they somehow ARE equal (bug), contract must still hold
        if item1 == item2:
            assert hash(item1) == hash(item2), (
                "Contract violation: equal items have different hashes"
            )

    @given(
        source1=st.text(min_size=1, max_size=20),
        source2=st.text(min_size=1, max_size=20),
        content=st.text(min_size=0, max_size=200),
    )
    @settings(max_examples=50)
    def test_different_sources_are_different(
        self, source1: str, source2: str, content: str
    ) -> None:
        """Items with different sources should not be equal.

        Even with same content, different sources means different items.
        """
        if source1 == source2:
            return  # Skip when sources are the same

        item1 = ContextItem(source1, content, 0.5, {})
        item2 = ContextItem(source2, content, 0.5, {})

        assert item1 != item2, (
            "Items with different sources must not be equal"
        )

    def test_unequal_items_can_collide(self) -> None:
        """Hash collisions are allowed for unequal items.

        This documents that the contract allows hash(a) == hash(b) even when
        a != b. Only the reverse is forbidden: if a == b, hash(a) must equal hash(b).

        Note: This test doesn't force a collision, just documents the contract.
        Finding actual collisions would require brute force and isn't necessary.
        """
        # Two different items
        item1 = ContextItem(
            source="test", content="content_a", relevance=0.5, metadata={}
        )
        item2 = ContextItem(
            source="test", content="content_b", relevance=0.5, metadata={}
        )

        assert item1 != item2

        # Whether or not their hashes collide is implementation-defined
        # and doesn't violate the contract either way
        # (hash collision is allowed for unequal items)
        _ = hash(item1)  # Just verify hashable
        _ = hash(item2)  # Just verify hashable
