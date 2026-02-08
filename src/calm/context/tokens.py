"""Token estimation and budget management for context assembly."""

from typing import Any

from calm.config import settings

SOURCE_WEIGHTS = settings.context.source_weights
MAX_ITEM_FRACTION = settings.context.max_item_fraction


def estimate_tokens(text: str) -> int:
    """Estimate token count (4 chars per token heuristic)."""
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to approximately fit within token budget."""
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]

    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.8:
        return truncated[:last_newline]

    return truncated


def distribute_budget(
    context_types: list[str],
    max_tokens: int,
) -> dict[str, int]:
    """Distribute token budget across requested context types."""
    invalid = [t for t in context_types if t not in SOURCE_WEIGHTS]
    if invalid:
        raise ValueError(
            f"Invalid context types: {invalid}. Valid: {list(SOURCE_WEIGHTS.keys())}"
        )

    if max_tokens < 1:
        raise ValueError(f"max_tokens must be positive, got {max_tokens}")
    if max_tokens > 100000:
        raise ValueError(f"max_tokens {max_tokens} exceeds maximum of 100000")

    total_weight = sum(SOURCE_WEIGHTS[t] for t in context_types)
    return {
        source: int((SOURCE_WEIGHTS[source] / total_weight) * max_tokens)
        for source in context_types
    }


def cap_item_tokens(
    content: str,
    source_budget: int,
    item_metadata: dict[str, Any],
    item_source: str | None = None,
) -> tuple[str, bool]:
    """Cap item content to per-item token limit (25% of source budget)."""
    max_item_tokens = int(source_budget * MAX_ITEM_FRACTION)
    item_tokens = estimate_tokens(content)

    if item_tokens <= max_item_tokens:
        return content, False

    truncated = truncate_to_tokens(content, max_item_tokens)

    if item_source == "code":
        note = (
            f"\n\n*(truncated, see full at "
            f"{item_metadata.get('file_path', 'unknown')}:"
            f"{item_metadata.get('start_line', '?')})*"
        )
    elif item_source == "experience":
        exp_id = item_metadata.get('id', 'unknown')
        note = f"\n\n*(truncated, full experience ID: {exp_id})*"
    else:
        note = "\n\n*(truncated)*"

    return truncated + "..." + note, True
