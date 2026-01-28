"""Content deduplication algorithms for context assembly."""

import difflib

from clams.config import settings

from .models import ContextItem

# Module-level aliases for backwards compatibility
# These now reference the central configuration
SIMILARITY_THRESHOLD = settings.context.similarity_threshold
MAX_FUZZY_CONTENT_LENGTH = settings.context.max_fuzzy_content_length


def deduplicate_items(items: list[ContextItem]) -> list[ContextItem]:
    """
    Deduplicate context items across sources.

    Deduplication rules:
    1. Same GHAP ID in experiences and values
    2. Same file path in code and commits
    3. Fuzzy text match (>90% similarity)

    When duplicates found, keep item with highest relevance score.

    Args:
        items: List of context items (possibly with duplicates)

    Returns:
        Deduplicated list, sorted by relevance (descending)
    """
    if not items:
        return []

    # Group items by potential duplicate keys
    seen: dict[str, ContextItem] = {}

    for item in items:
        key = _get_dedup_key(item)

        if key in seen:
            # Duplicate found - keep higher relevance
            if item.relevance > seen[key].relevance:
                seen[key] = item
        else:
            # Check for fuzzy text duplicates
            fuzzy_dup = _find_fuzzy_duplicate(item, list(seen.values()))
            if fuzzy_dup:
                # Replace if higher relevance
                fuzzy_key = _get_dedup_key(fuzzy_dup)
                if item.relevance > fuzzy_dup.relevance:
                    del seen[fuzzy_key]
                    seen[key] = item
            else:
                seen[key] = item

    # Return sorted by relevance
    return sorted(seen.values(), key=lambda x: x.relevance, reverse=True)


def _get_dedup_key(item: ContextItem) -> str:
    """
    Generate deduplication key for item.

    Returns unique key based on source-specific identifiers.
    """
    # GHAP ID for experiences and values
    ghap_id = item.metadata.get("ghap_id")
    if ghap_id:
        return f"ghap:{ghap_id}"

    # File path for code and commits
    file_path = item.metadata.get("file_path")
    if file_path:
        return f"file:{file_path}"

    # Commit SHA
    sha = item.metadata.get("sha")
    if sha:
        return f"commit:{sha}"

    # Memory ID
    mem_id = item.metadata.get("id")
    if mem_id:
        return f"memory:{mem_id}"

    # Fallback: content hash
    return f"content:{hash(item.content)}"


def _find_fuzzy_duplicate(
    item: ContextItem,
    candidates: list[ContextItem],
) -> ContextItem | None:
    """
    Find fuzzy text duplicate in candidate list.

    Uses difflib.SequenceMatcher for fast fuzzy matching.
    Performance optimization: only fuzzy-matches content under 1000 chars
    to avoid O(n²) slowdown on large text blocks.

    Args:
        item: Item to check for duplicates
        candidates: List of items to compare against

    Returns:
        Duplicate item if found, None otherwise
    """
    # Performance pre-filter: skip fuzzy matching for very long content
    if len(item.content) > MAX_FUZZY_CONTENT_LENGTH:
        return None

    # Also pre-filter candidates by length (no match if length differs by >20%)
    item_len = len(item.content)
    min_len = int(item_len * 0.8)
    max_len = int(item_len * 1.2)

    for candidate in candidates:
        candidate_len = len(candidate.content)

        # Skip if length difference is too large (can't be >90% similar)
        if candidate_len < min_len or candidate_len > max_len:
            continue

        # Skip fuzzy matching on very long candidates
        if candidate_len > MAX_FUZZY_CONTENT_LENGTH:
            continue

        similarity = difflib.SequenceMatcher(
            None, item.content, candidate.content
        ).ratio()

        if similarity >= SIMILARITY_THRESHOLD:
            return candidate

    return None
