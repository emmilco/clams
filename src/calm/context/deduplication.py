"""Content deduplication algorithms for context assembly."""

import difflib

from calm.config import settings

from .models import ContextItem

SIMILARITY_THRESHOLD = settings.context.similarity_threshold
MAX_FUZZY_CONTENT_LENGTH = settings.context.max_fuzzy_content_length


def deduplicate_items(items: list[ContextItem]) -> list[ContextItem]:
    """Deduplicate context items across sources."""
    if not items:
        return []

    seen: dict[str, ContextItem] = {}

    for item in items:
        key = _get_dedup_key(item)

        if key in seen:
            if item.relevance > seen[key].relevance:
                seen[key] = item
        else:
            fuzzy_dup = _find_fuzzy_duplicate(item, list(seen.values()))
            if fuzzy_dup:
                fuzzy_key = _get_dedup_key(fuzzy_dup)
                if item.relevance > fuzzy_dup.relevance:
                    del seen[fuzzy_key]
                    seen[key] = item
            else:
                seen[key] = item

    return sorted(seen.values(), key=lambda x: x.relevance, reverse=True)


def _get_dedup_key(item: ContextItem) -> str:
    """Generate deduplication key for item."""
    ghap_id = item.metadata.get("ghap_id")
    if ghap_id:
        return f"ghap:{ghap_id}"

    file_path = item.metadata.get("file_path")
    if file_path:
        return f"file:{file_path}"

    sha = item.metadata.get("sha")
    if sha:
        return f"commit:{sha}"

    mem_id = item.metadata.get("id")
    if mem_id:
        return f"memory:{mem_id}"

    return f"content:{hash(item.content)}"


def _find_fuzzy_duplicate(
    item: ContextItem,
    candidates: list[ContextItem],
) -> ContextItem | None:
    """Find fuzzy text duplicate in candidate list."""
    if len(item.content) > MAX_FUZZY_CONTENT_LENGTH:
        return None

    item_len = len(item.content)
    min_len = int(item_len * 0.8)
    max_len = int(item_len * 1.2)

    for candidate in candidates:
        candidate_len = len(candidate.content)

        if candidate_len < min_len or candidate_len > max_len:
            continue

        if candidate_len > MAX_FUZZY_CONTENT_LENGTH:
            continue

        similarity = difflib.SequenceMatcher(
            None, item.content, candidate.content
        ).ratio()

        if similarity >= SIMILARITY_THRESHOLD:
            return candidate

    return None
