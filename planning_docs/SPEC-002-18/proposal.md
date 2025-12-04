# Technical Proposal: ContextAssembler

## Problem Statement

The Learning Memory Server provides multiple data sources (memories, code, experiences, values, commits) that need to be queried, filtered, formatted, and combined into a coherent context for injection into Claude Code sessions. Currently:

1. **No unified assembly** - Callers must manually query each source via Searcher
2. **No token management** - No logic to distribute token budget across sources
3. **No formatting** - Raw result objects need manual conversion to markdown
4. **No deduplication** - Same content from multiple sources appears redundantly
5. **No ranking across sources** - Items from different sources can't be compared
6. **No premortem support** - No specialized queries for failure warnings

This creates friction for higher-level components (MCP tools, hooks) and results in inconsistent context formatting.

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                     MCP Tools / Hooks                            │
│                                                                  │
│  • Request context by query + types                             │
│  • Receive formatted markdown ready for injection               │
│  • No token counting or formatting logic                        │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ContextAssembler                            │
│                                                                  │
│  ┌─────────────┐  ┌──────────────┐  ┌─────────────────┐        │
│  │ Query       │  │ Token Budget │  │ Deduplication   │        │
│  │ Coordinator │  │ Distribution │  │ & Ranking       │        │
│  └─────────────┘  └──────────────┘  └─────────────────┘        │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │ Markdown Formatter                                   │       │
│  └──────────────────────────────────────────────────────┘       │
└───────────────────────────┬──────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Searcher                                │
│                                                                  │
│  • search_memories()                                            │
│  • search_code()                                                │
│  • search_experiences()                                         │
│  • search_values()                                              │
│  • search_commits()                                             │
└─────────────────────────────────────────────────────────────────┘
```

The ContextAssembler acts as an **orchestrator** that:
1. Queries multiple sources in parallel via Searcher
2. Applies per-source and per-item token budgets
3. Deduplicates content across sources
4. Ranks and selects items within budget
5. Formats results as markdown with metadata
6. Provides specialized premortem queries

### Module Structure

```
context/
├── __init__.py          # Public exports
├── assembler.py         # ContextAssembler class
├── models.py            # ContextItem, FormattedContext dataclasses
├── formatting.py        # Markdown formatting logic
├── deduplication.py     # Content deduplication algorithms
└── tokens.py            # Token estimation and budget management
```

**`__init__.py` exports:**
```python
"""Context assembly and formatting for agent injection."""

from .assembler import ContextAssembler
from .models import (
    ContextItem,
    FormattedContext,
    ContextAssemblyError,
    InvalidContextTypeError,
)

__all__ = [
    "ContextAssembler",
    "ContextItem",
    "FormattedContext",
    "ContextAssemblyError",
    "InvalidContextTypeError",
]
```

### Key Design Decisions

#### 1. Data Models

```python
# models.py

from dataclasses import dataclass
from typing import Any


@dataclass
class ContextItem:
    """A single piece of context from any source."""

    source: str              # "memory", "code", "experience", "value", "commit"
    content: str             # Formatted content for display
    relevance: float         # Similarity score (0.0-1.0)
    metadata: dict[str, Any] # Source-specific metadata

    def __hash__(self) -> int:
        """Make hashable for set operations (deduplication)."""
        return hash((self.source, self.content[:100]))  # First 100 chars for perf

    def __eq__(self, other: object) -> bool:
        """Compare for equality (deduplication)."""
        if not isinstance(other, ContextItem):
            return False
        return self.source == other.source and self.content == other.content


@dataclass
class FormattedContext:
    """Complete formatted context ready for injection."""

    markdown: str                      # Formatted markdown text
    items: list[ContextItem]           # Individual items (for inspection)
    token_count: int                   # Approximate token count
    sources_used: dict[str, int]       # Count by source type
    budget_exceeded: bool = False      # True if max_tokens was exceeded
    truncated_items: list[str] = None  # IDs of items that were truncated

    def __post_init__(self) -> None:
        """Initialize mutable default."""
        if self.truncated_items is None:
            self.truncated_items = []


class ContextAssemblyError(Exception):
    """Base exception for context assembly."""
    pass


class InvalidContextTypeError(ContextAssemblyError):
    """Raised when invalid context type requested."""

    def __init__(self, invalid_type: str, valid_types: list[str]):
        self.invalid_type = invalid_type
        self.valid_types = valid_types
        super().__init__(
            f"Invalid context type '{invalid_type}'. "
            f"Valid types: {', '.join(valid_types)}"
        )
```

**Rationale**:
- **Simple dataclasses** - Easy to construct, serialize, and test
- **Hashable ContextItem** - Enables set-based deduplication
- **Metadata dict** - Flexible for source-specific data without coupling
- **Budget tracking** - FormattedContext knows if budget was exceeded
- **Truncation tracking** - Caller can see which items were truncated

#### 2. Token Estimation

```python
# tokens.py

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
```

**Rationale**:
- **Simple heuristic** - No external tokenizer dependency
- **Conservative** - 4 chars/token slightly overestimates, prevents overflow
- **Fast** - O(1) for estimation, O(n) for truncation
- **Good enough** - Within 20% accuracy is acceptable per spec

**Trade-off**: Not as accurate as tiktoken, but avoids dependency and complexity. If accuracy becomes critical, we can swap the implementation without changing the interface.

#### 3. Token Budget Distribution

```python
# tokens.py

# Source weights for budget distribution
SOURCE_WEIGHTS = {
    "memories": 1,      # Typically short, concise
    "code": 2,          # Code blocks are verbose
    "experiences": 3,   # Rich, multi-field GHAP entries
    "values": 1,        # Single-statement principles
    "commits": 2,       # Multi-line messages + file lists
}

# Maximum fraction of source budget any single item can consume
MAX_ITEM_FRACTION = 0.25


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

    Example:
        >>> distribute_budget(["memories", "code", "experiences"], 1000)
        {
            "memories": 166,    # 1/6 of budget
            "code": 333,        # 2/6 of budget
            "experiences": 500  # 3/6 of budget
        }
    """
    total_weight = sum(SOURCE_WEIGHTS[t] for t in context_types)
    return {
        source: int((SOURCE_WEIGHTS[source] / total_weight) * max_tokens)
        for source in context_types
    }


def cap_item_tokens(
    content: str,
    source_budget: int,
    item_metadata: dict[str, Any],
) -> tuple[str, bool]:
    """
    Cap item content to per-item token limit.

    No single item can exceed 25% of its source budget.
    This ensures diversity - multiple items per source, not one verbose result.

    Args:
        content: Item content to potentially truncate
        source_budget: Total token budget for this source
        item_metadata: Metadata for truncation note

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
    source = item_metadata.get("source", "")
    if source == "code":
        note = (
            f"\n\n*(truncated, see full at "
            f"{item_metadata.get('file_path', 'unknown')}:"
            f"{item_metadata.get('start_line', '?')})*"
        )
    elif source == "experience":
        note = f"\n\n*(truncated, full experience ID: {item_metadata.get('id', 'unknown')})*"
    else:
        note = "\n\n*(truncated)*"

    return truncated + "..." + note, True
```

**Rationale**:
- **Weighted distribution** - Allocates more budget to richer content types
- **Per-item cap** - Prevents one verbose item from crowding out others
- **Truncation notes** - User knows where to find full content
- **Tunable weights** - Easy to adjust based on empirical usage

#### 4. Deduplication Strategy

```python
# deduplication.py

import difflib
from typing import Any


# Similarity threshold for fuzzy matching (90%)
SIMILARITY_THRESHOLD = 0.90


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

    Args:
        item: Item to check for duplicates
        candidates: List of items to compare against

    Returns:
        Duplicate item if found, None otherwise
    """
    for candidate in candidates:
        similarity = difflib.SequenceMatcher(
            None, item.content, candidate.content
        ).ratio()

        if similarity >= SIMILARITY_THRESHOLD:
            return candidate

    return None
```

**Rationale**:
- **Multiple strategies** - ID-based (exact) and fuzzy text matching
- **Relevance preservation** - Always keeps highest-scoring duplicate
- **Fast fuzzy matching** - difflib is stdlib and fast enough for this use
- **Source-aware** - Uses appropriate keys for each source type

**Trade-off**: Fuzzy matching is O(n²) but acceptable for small result sets (typically <100 items). Could optimize with locality-sensitive hashing if needed.

#### 5. Markdown Formatting

```python
# formatting.py

from typing import Any


def format_memory(metadata: dict[str, Any]) -> str:
    """
    Format memory item as markdown.

    Format:
        **Memory**: {content}
        *Category: {category}, Importance: {importance}*
    """
    content = metadata["content"]
    category = metadata["category"]
    importance = metadata.get("importance", 0.0)

    return (
        f"**Memory**: {content}\n"
        f"*Category: {category}, Importance: {importance:.2f}*"
    )


def format_code(metadata: dict[str, Any]) -> str:
    """
    Format code item as markdown.

    Format:
        **{unit_type}** `{name}` in `{file_path}:{start_line}`
        ```python
        {signature}
        {docstring if present}
        ```
    """
    unit_type = metadata["unit_type"].capitalize()
    name = metadata["qualified_name"]
    file_path = metadata["file_path"]
    start_line = metadata["start_line"]
    language = metadata.get("language", "python")
    code = metadata.get("code", "")
    docstring = metadata.get("docstring")

    result = f"**{unit_type}** `{name}` in `{file_path}:{start_line}`\n"
    result += f"```{language}\n{code}\n"
    if docstring:
        result += f'"""{docstring}"""\n'
    result += "```"

    return result


def format_experience(metadata: dict[str, Any]) -> str:
    """
    Format experience item as markdown.

    Format:
        **Experience**: {domain} | {strategy}
        - **Goal**: {goal}
        - **Hypothesis**: {hypothesis}
        - **Action**: {action}
        - **Prediction**: {prediction}
        - **Outcome**: {outcome_status} - {outcome_result}
        {if surprise: - **Surprise**: {surprise}}
        {if lesson: - **Lesson**: {lesson.what_worked}}
    """
    domain = metadata["domain"]
    strategy = metadata["strategy"]
    goal = metadata["goal"]
    hypothesis = metadata["hypothesis"]
    action = metadata["action"]
    prediction = metadata["prediction"]
    outcome_status = metadata["outcome_status"]
    outcome_result = metadata["outcome_result"]
    surprise = metadata.get("surprise")
    lesson = metadata.get("lesson")

    result = f"**Experience**: {domain} | {strategy}\n"
    result += f"- **Goal**: {goal}\n"
    result += f"- **Hypothesis**: {hypothesis}\n"
    result += f"- **Action**: {action}\n"
    result += f"- **Prediction**: {prediction}\n"
    result += f"- **Outcome**: {outcome_status} - {outcome_result}\n"

    if surprise:
        result += f"- **Surprise**: {surprise}\n"

    if lesson:
        what_worked = lesson.get("what_worked", "")
        result += f"- **Lesson**: {what_worked}\n"

    return result


def format_value(metadata: dict[str, Any]) -> str:
    """
    Format value item as markdown.

    Format:
        **Value** ({axis}, cluster size: {cluster_size}):
        {text}
    """
    axis = metadata["axis"]
    cluster_size = metadata.get("cluster_size", 0)
    text = metadata["text"]

    return f"**Value** ({axis}, cluster size: {cluster_size}):\n{text}"


def format_commit(metadata: dict[str, Any]) -> str:
    """
    Format commit item as markdown.

    Format:
        **Commit** `{sha[:7]}` by {author} on {timestamp}
        {message}
        *Files: {files_changed[0]}, {files_changed[1]}, ...*
    """
    sha = metadata["sha"][:7]
    author = metadata["author"]
    timestamp = metadata.get("committed_at", "unknown")
    message = metadata["message"]
    files = metadata.get("files_changed", [])

    result = f"**Commit** `{sha}` by {author} on {timestamp}\n"
    result += f"{message}\n"

    if files:
        # Show first 3 files
        file_list = ", ".join(files[:3])
        if len(files) > 3:
            file_list += f", ... ({len(files) - 3} more)"
        result += f"*Files: {file_list}*"

    return result


def assemble_markdown(
    items_by_source: dict[str, list[ContextItem]],
    premortem: bool = False,
    domain: str | None = None,
    strategy: str | None = None,
) -> str:
    """
    Assemble final markdown output from items.

    Args:
        items_by_source: Items grouped by source type
        premortem: If True, use premortem format
        domain: Domain for premortem header (if premortem=True)
        strategy: Strategy for premortem header (if premortem=True)

    Returns:
        Formatted markdown string
    """
    if premortem:
        return _assemble_premortem_markdown(items_by_source, domain, strategy)
    else:
        return _assemble_standard_markdown(items_by_source)


def _assemble_standard_markdown(
    items_by_source: dict[str, list[ContextItem]],
) -> str:
    """
    Standard context format.

    Format:
        # Context

        ## Memories
        {memory items}

        ## Code
        {code items}

        ... (for each non-empty source)

        ---
        *{total_items} items from {sources_count} sources*
    """
    sections = ["# Context\n"]

    source_titles = {
        "memories": "Memories",
        "code": "Code",
        "experiences": "Experiences",
        "values": "Values",
        "commits": "Commits",
    }

    total_items = 0
    sources_count = 0

    for source, items in items_by_source.items():
        if not items:
            continue

        title = source_titles.get(source, source.capitalize())
        sections.append(f"\n## {title}\n")

        for item in items:
            sections.append(f"\n{item.content}\n")
            total_items += 1

        sources_count += 1

    # Footer
    sections.append(f"\n---\n*{total_items} items from {sources_count} sources*")

    return "\n".join(sections)


def _assemble_premortem_markdown(
    items_by_source: dict[str, list[ContextItem]],
    domain: str | None,
    strategy: str | None,
) -> str:
    """
    Premortem context format.

    Format:
        # Premortem: {domain}{" with " + strategy if strategy else ""}

        ## Common Failures
        {falsified experiences}

        ## Strategy Performance (if strategy provided)
        {strategy-specific experiences}

        ## Unexpected Outcomes
        {surprises}

        ## Root Causes to Watch
        {root causes}

        ## Relevant Principles
        {values}

        ---
        *Based on {count} past experiences*
    """
    header = f"# Premortem: {domain or 'Unknown Domain'}"
    if strategy:
        header += f" with {strategy}"

    sections = [header + "\n"]

    # Map experience types to sections
    section_mapping = {
        "full": "Common Failures",
        "strategy": "Strategy Performance",
        "surprise": "Unexpected Outcomes",
        "root_cause": "Root Causes to Watch",
    }

    # Process experiences by axis
    exp_items = items_by_source.get("experiences", [])
    experience_count = 0

    for axis, title in section_mapping.items():
        axis_items = [
            item for item in exp_items
            if item.metadata.get("axis") == axis
        ]

        if axis_items:
            sections.append(f"\n## {title}\n")
            for item in axis_items:
                sections.append(f"\n{item.content}\n")
                experience_count += 1

    # Values section
    value_items = items_by_source.get("values", [])
    if value_items:
        sections.append("\n## Relevant Principles\n")
        for item in value_items:
            sections.append(f"\n{item.content}\n")

    # Footer
    sections.append(f"\n---\n*Based on {experience_count} past experiences*")

    return "\n".join(sections)
```

**Rationale**:
- **Source-specific formatting** - Each source has optimal display format
- **Consistent structure** - All formats follow similar patterns
- **Markdown-native** - Renders well in Claude Code interface
- **Metadata preservation** - Important context (file paths, timestamps) included
- **Empty handling** - Omits sections with no results

#### 6. ContextAssembler Implementation

```python
# assembler.py

import asyncio
import structlog
from typing import Any

from ..search import Searcher
from .models import ContextItem, FormattedContext, InvalidContextTypeError
from .tokens import distribute_budget, cap_item_tokens, estimate_tokens
from .deduplication import deduplicate_items
from .formatting import (
    format_memory,
    format_code,
    format_experience,
    format_value,
    format_commit,
    assemble_markdown,
)

logger = structlog.get_logger()

# Valid context types
VALID_CONTEXT_TYPES = {"memories", "code", "experiences", "values", "commits"}


class ContextAssembler:
    """Assemble context from multiple sources for agent injection."""

    def __init__(self, searcher: Searcher):
        """
        Initialize assembler with searcher.

        Args:
            searcher: Searcher instance for querying all sources
        """
        self._searcher = searcher
        self._logger = logger.bind(component="context_assembler")

    async def assemble_context(
        self,
        query: str,
        context_types: list[str],
        limit: int = 20,
        max_tokens: int = 2000,
    ) -> FormattedContext:
        """
        Assemble context from specified sources.

        Queries all requested sources in parallel, deduplicates results,
        applies token budgets, and formats as markdown.

        Args:
            query: Natural language query describing what context is needed
            context_types: List of source types to query
            limit: Maximum items to retrieve per source (default: 20)
            max_tokens: Soft limit on total token count (default: 2000)

        Returns:
            FormattedContext with markdown text and metadata

        Raises:
            InvalidContextTypeError: If invalid context type requested
        """
        # Validate context types
        invalid = [t for t in context_types if t not in VALID_CONTEXT_TYPES]
        if invalid:
            raise InvalidContextTypeError(
                invalid[0],
                list(VALID_CONTEXT_TYPES),
            )

        self._logger.info(
            "assembling_context",
            query=query,
            context_types=context_types,
            limit=limit,
            max_tokens=max_tokens,
        )

        # Query all sources in parallel
        items_by_source = await self._query_sources(
            query, context_types, limit
        )

        # Deduplicate across sources
        all_items = []
        for items in items_by_source.values():
            all_items.extend(items)

        deduplicated = deduplicate_items(all_items)

        self._logger.info(
            "deduplication_complete",
            original_count=len(all_items),
            deduplicated_count=len(deduplicated),
        )

        # Distribute token budget
        token_budget = distribute_budget(context_types, max_tokens)

        # Select items within budget
        selected_by_source, truncated_ids = self._select_items(
            deduplicated, token_budget
        )

        # Format as markdown
        markdown = assemble_markdown(selected_by_source)
        token_count = estimate_tokens(markdown)

        # Build response
        all_selected = []
        sources_used = {}
        for source, items in selected_by_source.items():
            all_selected.extend(items)
            sources_used[source] = len(items)

        budget_exceeded = token_count > max_tokens

        if budget_exceeded:
            self._logger.warning(
                "token_budget_exceeded",
                budget=max_tokens,
                actual=token_count,
            )

        return FormattedContext(
            markdown=markdown,
            items=all_selected,
            token_count=token_count,
            sources_used=sources_used,
            budget_exceeded=budget_exceeded,
            truncated_items=truncated_ids,
        )

    async def get_premortem_context(
        self,
        domain: str,
        strategy: str | None = None,
        limit: int = 10,
        max_tokens: int = 1500,
    ) -> FormattedContext:
        """
        Get premortem warnings for a domain (and optionally strategy).

        Retrieves past failures, common surprises, and frequent root causes
        for the specified domain to help agent anticipate issues.

        Args:
            domain: Domain enum value (e.g., "debugging", "feature")
            strategy: Optional strategy enum value (e.g., "systematic-elimination")
            limit: Maximum items per category (default: 10)
            max_tokens: Soft limit on total tokens (default: 1500)

        Returns:
            FormattedContext with premortem warnings
        """
        self._logger.info(
            "assembling_premortem",
            domain=domain,
            strategy=strategy,
            limit=limit,
        )

        # Query all experience axes + values in parallel
        tasks = [
            # Full axis: failures in domain
            self._searcher.search_experiences(
                query=f"failures and issues in {domain}",
                axis="full",
                domain=domain,
                outcome="falsified",
                limit=limit,
            ),
            # Surprise axis: unexpected outcomes
            self._searcher.search_experiences(
                query=f"unexpected outcomes in {domain}",
                axis="surprise",
                domain=domain,
                limit=limit,
            ),
            # Root cause axis: why things fail
            self._searcher.search_experiences(
                query=f"why hypotheses fail in {domain}",
                axis="root_cause",
                domain=domain,
                limit=limit,
            ),
            # Values: principles for domain
            self._searcher.search_values(
                query=f"principles for {domain}" + (
                    f" using {strategy}" if strategy else ""
                ),
                limit=5,
            ),
        ]

        # Add strategy-specific query if strategy provided
        if strategy:
            tasks.insert(
                1,
                self._searcher.search_experiences(
                    query=f"outcomes using {strategy} strategy",
                    axis="strategy",
                    strategy=strategy,
                    limit=limit,
                ),
            )

        # Execute queries
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self._logger.error("premortem_query_failed", error=str(e))
            raise

        # Process results (handle partial failures)
        exp_full = results[0] if not isinstance(results[0], Exception) else []
        idx = 1

        if strategy:
            exp_strategy = results[idx] if not isinstance(results[idx], Exception) else []
            idx += 1
        else:
            exp_strategy = []

        exp_surprise = results[idx] if not isinstance(results[idx], Exception) else []
        exp_root_cause = results[idx + 1] if not isinstance(results[idx + 1], Exception) else []
        values = results[idx + 2] if not isinstance(results[idx + 2], Exception) else []

        # Convert to ContextItems
        items: list[ContextItem] = []

        for result in exp_full:
            items.append(self._experience_to_item(result))

        for result in exp_strategy:
            items.append(self._experience_to_item(result))

        for result in exp_surprise:
            items.append(self._experience_to_item(result))

        for result in exp_root_cause:
            items.append(self._experience_to_item(result))

        for result in values:
            items.append(self._value_to_item(result))

        # Group by source for formatting
        items_by_source = {
            "experiences": [i for i in items if i.source == "experience"],
            "values": [i for i in items if i.source == "value"],
        }

        # Format as premortem markdown
        markdown = assemble_markdown(
            items_by_source,
            premortem=True,
            domain=domain,
            strategy=strategy,
        )
        token_count = estimate_tokens(markdown)

        sources_used = {
            "experiences": len(items_by_source["experiences"]),
            "values": len(items_by_source["values"]),
        }

        return FormattedContext(
            markdown=markdown,
            items=items,
            token_count=token_count,
            sources_used=sources_used,
            budget_exceeded=token_count > max_tokens,
        )

    async def _query_sources(
        self,
        query: str,
        context_types: list[str],
        limit: int,
    ) -> dict[str, list[ContextItem]]:
        """
        Query all requested sources in parallel.

        Args:
            query: Search query
            context_types: Sources to query
            limit: Max results per source

        Returns:
            Dict mapping source type to ContextItems
        """
        tasks = []
        source_order = []

        for source in context_types:
            if source == "memories":
                tasks.append(self._searcher.search_memories(query, limit=limit))
                source_order.append("memories")
            elif source == "code":
                tasks.append(self._searcher.search_code(query, limit=limit))
                source_order.append("code")
            elif source == "experiences":
                tasks.append(
                    self._searcher.search_experiences(query, axis="full", limit=limit)
                )
                source_order.append("experiences")
            elif source == "values":
                tasks.append(self._searcher.search_values(query, limit=5))
                source_order.append("values")
            elif source == "commits":
                tasks.append(self._searcher.search_commits(query, limit=limit))
                source_order.append("commits")

        # Execute all queries in parallel
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            self._logger.error("source_query_failed", error=str(e))
            raise

        # Convert results to ContextItems
        items_by_source: dict[str, list[ContextItem]] = {}

        for source, result in zip(source_order, results):
            if isinstance(result, Exception):
                self._logger.warning(
                    "source_query_partial_failure",
                    source=source,
                    error=str(result),
                )
                items_by_source[source] = []
                continue

            items = self._convert_results(source, result)
            items_by_source[source] = items

        return items_by_source

    def _convert_results(
        self,
        source: str,
        results: list[Any],
    ) -> list[ContextItem]:
        """
        Convert search results to ContextItems.

        Args:
            source: Source type
            results: List of typed result objects

        Returns:
            List of ContextItems
        """
        items = []

        for result in results:
            if source == "memories":
                content = format_memory(result.__dict__)
            elif source == "code":
                content = format_code(result.__dict__)
            elif source == "experiences":
                content = format_experience(result.__dict__)
            elif source == "values":
                content = format_value(result.__dict__)
            elif source == "commits":
                content = format_commit(result.__dict__)
            else:
                self._logger.warning("unknown_source_type", source=source)
                continue

            items.append(
                ContextItem(
                    source=source.rstrip("s"),  # "memories" -> "memory"
                    content=content,
                    relevance=result.score,
                    metadata=result.__dict__,
                )
            )

        return items

    def _experience_to_item(self, result: Any) -> ContextItem:
        """Convert ExperienceResult to ContextItem."""
        content = format_experience(result.__dict__)
        return ContextItem(
            source="experience",
            content=content,
            relevance=result.score,
            metadata=result.__dict__,
        )

    def _value_to_item(self, result: Any) -> ContextItem:
        """Convert ValueResult to ContextItem."""
        content = format_value(result.__dict__)
        return ContextItem(
            source="value",
            content=content,
            relevance=result.score,
            metadata=result.__dict__,
        )

    def _select_items(
        self,
        items: list[ContextItem],
        token_budget: dict[str, int],
    ) -> tuple[dict[str, list[ContextItem]], list[str]]:
        """
        Select items within token budget.

        Applies per-source and per-item token limits, truncating as needed.

        Args:
            items: Deduplicated items (all sources)
            token_budget: Token budget per source

        Returns:
            Tuple of (items_by_source, truncated_item_ids)
        """
        # Group items by source
        by_source: dict[str, list[ContextItem]] = {}
        for item in items:
            source = item.source + "s"  # "memory" -> "memories"
            if source not in by_source:
                by_source[source] = []
            by_source[source].append(item)

        # Select items for each source within budget
        selected: dict[str, list[ContextItem]] = {}
        truncated_ids: list[str] = []

        for source, source_items in by_source.items():
            budget = token_budget.get(source, 0)
            if budget == 0:
                continue

            selected[source] = []
            used_tokens = 0

            # Sort by relevance (already sorted from deduplication)
            for item in source_items:
                # Apply per-item cap
                capped_content, was_truncated = cap_item_tokens(
                    item.content, budget, item.metadata
                )

                if was_truncated:
                    truncated_ids.append(item.metadata.get("id", "unknown"))

                item_tokens = estimate_tokens(capped_content)

                # Check if item fits in remaining budget
                if used_tokens + item_tokens > budget:
                    # No more room in budget for this source
                    break

                # Add item with possibly capped content
                selected_item = ContextItem(
                    source=item.source,
                    content=capped_content,
                    relevance=item.relevance,
                    metadata=item.metadata,
                )
                selected[source].append(selected_item)
                used_tokens += item_tokens

            self._logger.debug(
                "source_budget_used",
                source=source,
                budget=budget,
                used=used_tokens,
                items_selected=len(selected[source]),
            )

        return selected, truncated_ids
```

**Rationale**:
- **Parallel queries** - All sources queried concurrently via asyncio.gather
- **Partial failure handling** - One source failing doesn't crash entire assembly
- **Stateless** - No cached state, safe for concurrent use
- **Structured logging** - All operations logged with structlog for debugging
- **Type safety** - Clear interfaces, typed parameters and returns

### Testing Strategy

#### Unit Tests

```python
# tests/context/test_assembler.py

@pytest.mark.asyncio
async def test_assemble_single_source(mock_searcher):
    """Test assembly with single source."""
    assembler = ContextAssembler(mock_searcher)

    mock_searcher.search_memories.return_value = [
        MemoryResult(
            id="mem_1",
            category="preference",
            content="Use async/await",
            score=0.95,
            tags=[],
            created_at=datetime.now(UTC),
            verified_at=None,
            verification_status=None,
        )
    ]

    result = await assembler.assemble_context(
        query="coding preferences",
        context_types=["memories"],
        max_tokens=1000,
    )

    assert len(result.items) == 1
    assert "Memory" in result.markdown
    assert result.token_count > 0


@pytest.mark.asyncio
async def test_token_budget_distribution():
    """Test token budget is distributed by weight."""
    budget = distribute_budget(["memories", "code", "experiences"], 1000)

    # Weights: memories=1, code=2, experiences=3
    # Total weight: 6
    assert budget["memories"] == 166  # 1/6
    assert budget["code"] == 333      # 2/6
    assert budget["experiences"] == 500  # 3/6


def test_deduplication_by_ghap_id():
    """Test deduplication using GHAP ID."""
    item1 = ContextItem(
        source="experience",
        content="Test 1",
        relevance=0.8,
        metadata={"ghap_id": "ghap_123"},
    )
    item2 = ContextItem(
        source="value",
        content="Test 2",
        relevance=0.9,
        metadata={"ghap_id": "ghap_123"},
    )

    deduplicated = deduplicate_items([item1, item2])

    assert len(deduplicated) == 1
    assert deduplicated[0].relevance == 0.9  # Kept higher score


@pytest.mark.asyncio
async def test_premortem_context(mock_searcher):
    """Test premortem context generation."""
    assembler = ContextAssembler(mock_searcher)

    # Mock experience results
    mock_searcher.search_experiences.return_value = [
        ExperienceResult(
            id="exp_1",
            ghap_id="ghap_1",
            axis="full",
            domain="debugging",
            strategy="systematic-elimination",
            goal="Fix bug",
            hypothesis="It's a null pointer",
            action="Added null check",
            prediction="Bug fixed",
            outcome_status="falsified",
            outcome_result="Still failing",
            surprise="Different root cause",
            root_cause=None,
            lesson=None,
            confidence_tier="gold",
            iteration_count=3,
            score=0.9,
            created_at=datetime.now(UTC),
        )
    ]

    mock_searcher.search_values.return_value = []

    result = await assembler.get_premortem_context(
        domain="debugging",
        strategy="systematic-elimination",
    )

    assert "Premortem: debugging" in result.markdown
    assert "systematic-elimination" in result.markdown
```

#### Integration Tests

```python
# tests/context/test_integration.py

@pytest.mark.asyncio
async def test_end_to_end_assembly(
    qdrant_container,
    embedding_service,
    vector_store,
):
    """Test full assembly with real data."""
    # Setup: Index test data
    await setup_test_data(vector_store, embedding_service)

    searcher = Searcher(embedding_service, vector_store)
    assembler = ContextAssembler(searcher)

    # Assemble context
    result = await assembler.assemble_context(
        query="authentication implementation",
        context_types=["memories", "code", "experiences"],
        max_tokens=2000,
    )

    # Verify structure
    assert result.markdown.startswith("# Context")
    assert len(result.items) > 0
    assert result.token_count > 0
    assert len(result.sources_used) > 0

    # Verify markdown renders correctly
    assert "##" in result.markdown  # Has sections
    assert "**" in result.markdown  # Has bold formatting
```

### Performance Considerations

#### Query Parallelization

All source queries execute concurrently using `asyncio.gather`, reducing total latency:

```
Sequential: 5 sources × 100ms = 500ms
Parallel:   max(100ms across all) = ~100ms
```

#### Optimization Strategies

1. **Batch embedding** - Searcher may batch embed similar queries
2. **Limit result counts** - Request only what's needed (default 20)
3. **Early truncation** - Apply per-item caps before final assembly
4. **Fuzzy match optimization** - Only check items from same source type

#### Target Performance

| Operation | Target | Notes |
|-----------|--------|-------|
| assemble_context() | <1s | 5 parallel queries + processing |
| get_premortem_context() | <1.5s | More complex filtering |
| Token estimation | <10ms | Simple char count |
| Deduplication | <50ms | O(n²) fuzzy match, small n |
| Formatting | <100ms | String building |

### Alternatives Considered

#### 1. Context Caching

**Alternative**: Cache assembled contexts by query hash.

**Pros**:
- Faster repeated queries
- Reduced Searcher load

**Cons**:
- Stale results
- Cache invalidation complexity
- Memory overhead

**Decision**: Rejected for v1. Keep stateless. Add in v2 if latency is an issue.

#### 2. Tiktoken for Token Counting

**Alternative**: Use tiktoken library for accurate token counting.

**Pros**:
- Accurate token counts
- Matches Claude's tokenization

**Cons**:
- External dependency
- Slower than heuristic
- Overkill for budget estimation

**Decision**: Rejected. Simple heuristic is fast and "good enough" (within 20%).

#### 3. Streaming Assembly

**Alternative**: Stream markdown output as items arrive.

**Pros**:
- Lower latency to first byte
- Better UX for slow queries

**Cons**:
- Complex implementation
- Harder to apply global deduplication
- Token budget harder to enforce

**Decision**: Rejected for v1. Simplicity over marginal UX improvement.

## Implementation Plan

### Phase 1: Foundation (Est: 2 hours)

- [ ] Create module structure (`context/` package)
- [ ] Implement data models (ContextItem, FormattedContext)
- [ ] Implement custom exceptions
- [ ] Add basic tests for models

### Phase 2: Token Management (Est: 2 hours)

- [ ] Implement token estimation
- [ ] Implement budget distribution
- [ ] Implement per-item capping and truncation
- [ ] Unit tests for token module

### Phase 3: Deduplication (Est: 2 hours)

- [ ] Implement dedup key generation
- [ ] Implement fuzzy matching
- [ ] Implement deduplication algorithm
- [ ] Unit tests for deduplication

### Phase 4: Formatting (Est: 3 hours)

- [ ] Implement source-specific formatters
- [ ] Implement standard markdown assembly
- [ ] Implement premortem markdown assembly
- [ ] Unit tests for formatting

### Phase 5: ContextAssembler (Est: 4 hours)

- [ ] Implement assemble_context()
- [ ] Implement get_premortem_context()
- [ ] Implement parallel query coordination
- [ ] Implement item selection logic
- [ ] Error handling and logging

### Phase 6: Testing (Est: 3 hours)

- [ ] Unit tests with mocks
- [ ] Integration tests with real dependencies
- [ ] Error case tests
- [ ] Performance validation

### Phase 7: Documentation & Polish (Est: 1 hour)

- [ ] Docstrings for all public APIs
- [ ] Update `__init__.py` exports
- [ ] Usage examples
- [ ] Type hint verification

**Total Estimate**: ~17 hours

## Success Criteria

Implementation is complete when:

1. All acceptance criteria from spec met
2. Test coverage ≥ 90%
3. All tests pass in isolation and in suite
4. Code passes `ruff` linting
5. Code passes `mypy --strict` type checking
6. Docstrings present for all public APIs
7. Integration tests with real Searcher pass
8. Performance targets met (<1s assemble, <1.5s premortem)
9. Token estimation within 20% of actual

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Token estimation inaccurate | Budget violations | Medium | Conservative heuristic, 20% tolerance |
| Fuzzy dedup too slow | Poor performance | Low | Small result sets, optimize if needed |
| Searcher partial failures | Missing context | Medium | Graceful degradation, log warnings |
| Markdown rendering issues | Poor UX | Low | Test with real Claude Code interface |
| Complex state management | Bugs | Low | Keep stateless, immutable data |

## Conclusion

This proposal implements a robust context assembly system that:
- **Simplifies caller code** - Single call returns formatted context
- **Manages token budgets** - Intelligent distribution and capping
- **Provides type safety** - Clear data models and interfaces
- **Handles failures gracefully** - Partial results on source failures
- **Optimizes performance** - Parallel queries, efficient algorithms
- **Enables specialized queries** - Premortem for failure warnings

The design prioritizes **reliability** and **performance** while keeping the implementation testable and maintainable. The ContextAssembler provides the final piece of the Learning Memory Server's context delivery pipeline.
