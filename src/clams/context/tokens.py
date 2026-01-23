"""Token estimation and budget management for context assembly."""

from typing import Any

# Source weights for budget distribution
SOURCE_WEIGHTS = {
    "memories": 1,  # Typically short, concise
    "code": 2,  # Code blocks are verbose
    "experiences": 3,  # Rich, multi-field GHAP entries
    "values": 1,  # Single-statement principles
    "commits": 2,  # Multi-line messages + file lists
}

# Maximum fraction of source budget any single item can consume
MAX_ITEM_FRACTION = 0.25


def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Uses conservative heuristic: 4 characters per token.
    This is slightly conservative for English text (typical: 4.5 chars/token)
    but accounts for markdown formatting overhead.

    Args:
        text: Text to estimate tokens for

    Returns:
        Estimated token count
    """
    return len(text) // 4


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate text to approximately fit within token budget.

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed

    Returns:
        Truncated text (may end mid-sentence)
    """
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text

    # Truncate and try to break at newline or sentence boundary
    truncated = text[:max_chars]

    # Try to break at last newline
    last_newline = truncated.rfind("\n")
    if last_newline > max_chars * 0.8:  # At least 80% of target
        return truncated[:last_newline]

    # Otherwise just truncate
    return truncated


def distribute_budget(
    context_types: list[str],
    max_tokens: int,
) -> dict[str, int]:
    """
    Distribute token budget across requested context types.

    Uses weighted distribution based on source richness:
    - Experiences (weight 3): Rich GHAP narratives
    - Code/Commits (weight 2): Verbose content
    - Memories/Values (weight 1): Concise items

    Args:
        context_types: List of source types to query
        max_tokens: Total token budget

    Returns:
        Dict mapping source type to token budget

    Raises:
        ValueError: If any context_type is not in SOURCE_WEIGHTS
        ValueError: If max_tokens is not positive or exceeds maximum

    Example:
        >>> distribute_budget(["memories", "code", "experiences"], 1000)
        {
            "memories": 166,    # 1/6 of budget
            "code": 333,        # 2/6 of budget
            "experiences": 500  # 3/6 of budget
        }
    """
    invalid = [t for t in context_types if t not in SOURCE_WEIGHTS]
    if invalid:
        raise ValueError(
            f"Invalid context types: {invalid}. Valid: {list(SOURCE_WEIGHTS.keys())}"
        )

    # Validate max_tokens
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
    """
    Cap item content to per-item token limit.

    No single item can exceed 25% of its source budget.
    This ensures diversity - multiple items per source, not one verbose result.

    Args:
        content: Item content to potentially truncate
        source_budget: Total token budget for this source
        item_metadata: Metadata for truncation note
        item_source: Source type (e.g., "code", "experience")
            for context-aware truncation notes

    Returns:
        Tuple of (possibly_truncated_content, was_truncated)
    """
    max_item_tokens = int(source_budget * MAX_ITEM_FRACTION)
    item_tokens = estimate_tokens(content)

    if item_tokens <= max_item_tokens:
        return content, False

    # Truncate content to fit within cap
    truncated = truncate_to_tokens(content, max_item_tokens)

    # Add truncation note with location reference
    # Note: item_source is passed separately because it's a ContextItem
    # attribute, not in metadata dict
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
