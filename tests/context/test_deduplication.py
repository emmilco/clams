"""Tests for deduplication algorithms."""

from clams.context.deduplication import deduplicate_items
from clams.context.models import ContextItem


def test_deduplicate_items_empty() -> None:
    """Test deduplication with empty list."""
    result = deduplicate_items([])
    assert result == []


def test_deduplicate_items_no_duplicates() -> None:
    """Test deduplication when no duplicates exist."""
    items = [
        ContextItem("memory", "content1", 0.9, {"id": "mem_1"}),
        ContextItem("memory", "content2", 0.8, {"id": "mem_2"}),
    ]
    result = deduplicate_items(items)
    assert len(result) == 2


def test_deduplicate_items_by_ghap_id() -> None:
    """Test deduplication using GHAP ID."""
    item1 = ContextItem(
        source="experience",
        content="Test experience",
        relevance=0.8,
        metadata={"ghap_id": "ghap_123", "id": "exp_1"},
    )
    item2 = ContextItem(
        source="value",
        content="Test value",
        relevance=0.9,
        metadata={"ghap_id": "ghap_123", "id": "val_1"},
    )

    result = deduplicate_items([item1, item2])

    assert len(result) == 1
    assert result[0].relevance == 0.9  # Kept higher score
    assert result[0].source == "value"


def test_deduplicate_items_by_file_path() -> None:
    """Test deduplication using file path."""
    item1 = ContextItem(
        source="code",
        content="Code snippet",
        relevance=0.7,
        metadata={"file_path": "foo.py", "id": "code_1"},
    )
    item2 = ContextItem(
        source="commit",
        content="Commit message",
        relevance=0.9,
        metadata={"file_path": "foo.py", "id": "commit_1"},
    )

    result = deduplicate_items([item1, item2])

    assert len(result) == 1
    assert result[0].relevance == 0.9  # Kept higher score
    assert result[0].source == "commit"


def test_deduplicate_items_by_sha() -> None:
    """Test deduplication using commit SHA."""
    item1 = ContextItem(
        source="commit",
        content="Commit 1",
        relevance=0.8,
        metadata={"sha": "abc123", "id": "commit_1"},
    )
    item2 = ContextItem(
        source="commit",
        content="Commit 2",
        relevance=0.6,
        metadata={"sha": "abc123", "id": "commit_2"},
    )

    result = deduplicate_items([item1, item2])

    assert len(result) == 1
    assert result[0].relevance == 0.8  # Kept higher score


def test_deduplicate_items_by_memory_id() -> None:
    """Test deduplication using memory ID."""
    item1 = ContextItem(
        source="memory",
        content="Memory 1",
        relevance=0.9,
        metadata={"id": "mem_1"},
    )
    item2 = ContextItem(
        source="memory",
        content="Memory 2",
        relevance=0.7,
        metadata={"id": "mem_1"},
    )

    result = deduplicate_items([item1, item2])

    assert len(result) == 1
    assert result[0].relevance == 0.9


def test_deduplicate_items_fuzzy_match() -> None:
    """Test fuzzy deduplication on similar content."""
    # Two items with >90% similar content
    content1 = "This is a test sentence for fuzzy matching algorithms."
    # Only diff is punctuation
    content2 = "This is a test sentence for fuzzy matching algorithms!"

    item1 = ContextItem(
        source="memory", content=content1, relevance=0.8, metadata={"id": "mem_1"}
    )
    item2 = ContextItem(
        source="memory", content=content2, relevance=0.9, metadata={"id": "mem_2"}
    )

    result = deduplicate_items([item1, item2])

    # Should detect as duplicates and keep higher relevance
    assert len(result) == 1
    assert result[0].relevance == 0.9


def test_deduplicate_items_fuzzy_no_match() -> None:
    """Test fuzzy matching doesn't trigger on different content."""
    item1 = ContextItem(
        source="memory",
        content="This is completely different content",
        relevance=0.8,
        metadata={"id": "mem_1"},
    )
    item2 = ContextItem(
        source="memory",
        content="Something totally unrelated here",
        relevance=0.9,
        metadata={"id": "mem_2"},
    )

    result = deduplicate_items([item1, item2])

    assert len(result) == 2  # Both kept


def test_deduplicate_items_sorted_by_relevance() -> None:
    """Test that results are sorted by relevance."""
    items = [
        ContextItem("memory", "content1", 0.5, {"id": "mem_1"}),
        ContextItem("memory", "content2", 0.9, {"id": "mem_2"}),
        ContextItem("memory", "content3", 0.7, {"id": "mem_3"}),
    ]

    result = deduplicate_items(items)

    assert len(result) == 3
    assert result[0].relevance == 0.9
    assert result[1].relevance == 0.7
    assert result[2].relevance == 0.5


def test_deduplicate_items_skips_long_content() -> None:
    """Test that very long content skips fuzzy matching."""
    # Create content > 1000 chars
    long_content1 = "a" * 1100
    long_content2 = "a" * 1100

    item1 = ContextItem(
        source="memory",
        content=long_content1,
        relevance=0.8,
        metadata={"id": "mem_1"},
    )
    item2 = ContextItem(
        source="memory",
        content=long_content2,
        relevance=0.9,
        metadata={"id": "mem_2"},
    )

    result = deduplicate_items([item1, item2])

    # Should keep both since fuzzy matching is skipped for long content
    # (they have different IDs so won't match on that)
    assert len(result) == 2
