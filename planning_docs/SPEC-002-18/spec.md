# SPEC-002-18: ContextAssembler

## Overview

The ContextAssembler module gathers and formats relevant context from multiple sources for injection into Claude Code sessions. It pulls from memories, code, experiences, values, and git history to provide context that helps agents work more effectively.

This module is the final piece of the Learning Memory Server's context delivery system, sitting at the top of the stack and coordinating queries across all other modules.

## Dependencies

### Completed
- SPEC-002-02: EmbeddingService
- SPEC-002-03: VectorStore
- SPEC-002-09: Searcher (unified query interface)

### Required
- Python 3.12
- structlog (logging)

## Interface

```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class ContextItem:
    """A single piece of context from any source."""
    source: str              # "memory", "code", "experience", "value", "commit"
    content: str             # Formatted content for display
    relevance: float         # Similarity score (0.0-1.0)
    metadata: dict           # Source-specific metadata

@dataclass
class FormattedContext:
    """Complete formatted context ready for injection."""
    markdown: str            # Formatted markdown text
    items: List[ContextItem] # Individual items (for inspection)
    token_count: int         # Approximate token count
    sources_used: dict       # Count by source type

class ContextAssembler:
    """Assemble context from multiple sources for agent injection."""

    def __init__(self, searcher: Searcher):
        """
        Initialize assembler with searcher.

        Args:
            searcher: Searcher instance for querying all sources
        """
        pass

    async def assemble_context(
        self,
        query: str,
        context_types: List[str],
        limit: int = 20,
        max_tokens: int = 2000,
    ) -> FormattedContext:
        """
        Assemble context from specified sources.

        Args:
            query: Natural language query describing what context is needed
            context_types: List of source types to query, from:
                           - "memories": Facts, preferences, decisions
                           - "code": Semantically similar code units
                           - "experiences": Past GHAP entries (full axis)
                           - "values": Emergent values from clustering
                           - "commits": Relevant git history
            limit: Maximum items to retrieve per source (default: 20)
            max_tokens: Soft limit on total token count (default: 2000)

        Returns:
            FormattedContext with markdown text and metadata

        Notes:
            - Results are deduplicated across sources
            - Items ranked by relevance within source
            - Token budget distributed across sources
            - Exceeding max_tokens is allowed if necessary for quality
        """
        pass

    async def get_premortem_context(
        self,
        domain: str,
        strategy: str | None = None,
        limit: int = 10,
        max_tokens: int = 1500,
    ) -> FormattedContext:
        """
        Get premortem warnings for a domain (and optionally strategy).

        Intended to be called via hook when a test/build fails for the first time,
        surfacing past failures and common pitfalls before the agent starts debugging.

        Retrieves past failures, common surprises, and frequent root causes
        for the specified domain to help agent anticipate issues.

        Args:
            domain: Domain enum value (e.g., "debugging", "feature")
            strategy: Optional strategy enum value (e.g., "systematic-elimination").
                      If provided, also queries strategy-specific experiences.
            limit: Maximum items per category (default: 10)
            max_tokens: Soft limit on total tokens (default: 1500)

        Returns:
            FormattedContext with premortem warnings

        Queries (Experience Axes Explained):
            Experience data is indexed on four axes for different access patterns:
            - **full axis**: Complete GHAP narratives, filtered by domain and outcome
            - **strategy axis**: Strategy-specific performance patterns (if strategy provided)
            - **surprise axis**: Unexpected outcomes that violated predictions
            - **root_cause axis**: Why hypotheses failed (common failure modes)

            This method queries:
            - Experiences (full axis) filtered by domain, outcome="falsified"
            - Experiences (strategy axis) filtered by strategy (if provided)
            - Experiences (surprise axis) filtered by domain
            - Experiences (root_cause axis) filtered by domain
            - Values associated with domain (and strategy if provided)
        """
        pass
```

## Context Sources

The ContextAssembler queries these sources via Searcher:

### 1. Memories
Query: `searcher.search_memories(query, limit)`

**Content**: Facts, preferences, decisions, error messages

**Format**:
```markdown
**Memory**: {content}
*Category: {category}, Importance: {importance}*
```

**Metadata**:
```python
{
    "id": str,
    "category": str,
    "importance": float,
    "created_at": str,
}
```

### 2. Code
Query: `searcher.search_code(query, limit)`

**Content**: Semantic code units (functions, classes, methods)

**Format**:
```markdown
**{unit_type}** `{name}` in `{file_path}:{start_line}`
```python
{signature}
{docstring if present}
```
```

**Metadata**:
```python
{
    "file_path": str,
    "start_line": int,
    "end_line": int,
    "language": str,
    "qualified_name": str,
}
```

### 3. Experiences (Full Axis)
Query: `searcher.search_experiences(query, axis="full", limit)`

**Content**: Complete GHAP narratives

**Format**:
```markdown
**Experience**: {domain} | {strategy}
- **Goal**: {goal}
- **Hypothesis**: {hypothesis}
- **Action**: {action}
- **Prediction**: {prediction}
- **Outcome**: {outcome_status} - {outcome_result}
{if surprise: - **Surprise**: {surprise}}
{if lesson: - **Lesson**: {lesson.what_worked}}
```

**Metadata**:
```python
{
    "id": str,
    "domain": str,
    "strategy": str,
    "outcome_status": str,
    "confidence_tier": str,
    "iteration_count": int,
}
```

### 4. Values
Query: `searcher.search_values(query, limit)`

**Content**: Emergent values from experience clustering

**Format**:
```markdown
**Value** ({axis}, cluster size: {cluster_size}):
{text}
```

**Metadata**:
```python
{
    "id": str,
    "axis": str,
    "cluster_id": str,
    "cluster_size": int,
    "similarity_to_centroid": float,
}
```

### 5. Commits
Query: `searcher.search_commits(query, limit)`

**Content**: Git commit history

**Format**:
```markdown
**Commit** `{sha[:7]}` by {author} on {timestamp}
{message}
*Files: {files_changed[0]}, {files_changed[1]}, ...*
```

**Metadata**:
```python
{
    "sha": str,
    "author": str,
    "timestamp": str,
    "files_changed": List[str],
    "insertions": int,
    "deletions": int,
}
```

## Ranking and Selection

### Per-Source Ranking

Results from each source are already ranked by Searcher (semantic similarity). The ContextAssembler respects this ranking but may adjust based on:

1. **Confidence weighting** (experiences): Gold > Silver > Bronze > Abandoned
2. **Importance weighting** (memories): Higher importance scores get boost
3. **Recency bonus** (commits, experiences): Recent items get small boost

### Cross-Source Deduplication

Deduplicate when content appears in multiple sources:
- Same GHAP ID in experiences and values
- Same file path in code and commits
- Same text content (fuzzy match with 90% similarity)

When duplicates found, keep the item from the source with highest relevance score.

### Token Budget Distribution

Distribute token budget across requested sources:

```python
# Adjust based on source richness
WEIGHT = {
    "experiences": 3,  # Rich, multi-field content
    "code": 2,         # Code blocks are verbose
    "commits": 2,      # Multi-line messages
    "values": 1,       # Concise single statements
    "memories": 1,     # Typically short
}

# Weighted distribution
total_weight = sum(WEIGHT[t] for t in context_types)
tokens_per_source = {
    t: (WEIGHT[t] / total_weight) * max_tokens
    for t in context_types
}
```

### Per-Item Cap and Truncation

To prevent a single long item from crowding out other results:

```python
# No single item can exceed 25% of its source budget
MAX_ITEM_FRACTION = 0.25

def cap_item(item: ContextItem, source_budget: int) -> ContextItem:
    """
    Truncate item if it exceeds per-item cap.

    Args:
        item: The context item to potentially truncate
        source_budget: Total token budget for this source

    Returns:
        Original item if within cap, or truncated copy with note
    """
    max_item_tokens = int(source_budget * MAX_ITEM_FRACTION)
    item_tokens = estimate_tokens(item.content)

    if item_tokens <= max_item_tokens:
        return item

    # Truncate content to fit within cap
    truncated_content = truncate_to_tokens(item.content, max_item_tokens)

    # Add truncation note with location reference
    if item.source == "code":
        note = f"\n\n*(truncated, see full at {item.metadata['file_path']}:{item.metadata['start_line']})*"
    elif item.source == "experience":
        note = f"\n\n*(truncated, full experience ID: {item.metadata['id']})*"
    else:
        note = "\n\n*(truncated)*"

    return ContextItem(
        source=item.source,
        content=truncated_content + "..." + note,
        relevance=item.relevance,
        metadata=item.metadata,
    )
```

This ensures:
- **Diversity**: Multiple items per source, not one verbose result
- **Relevance preserved**: Most relevant part of each item shown
- **Discoverability**: Truncation note tells agent where to find full content

### Selection Algorithm

```python
async def _select_items(
    self,
    items_by_source: dict[str, List[ContextItem]],
    token_budget: dict[str, int],
) -> List[ContextItem]:
    """
    Select items within token budget.

    Algorithm:
    1. For each source, estimate tokens for each item
    2. Select top items within budget for that source
    3. If any source under budget, redistribute to others
    4. Deduplicate across sources
    5. Sort by relevance score (global)
    """
    pass
```

## Output Format

### Markdown Structure

```markdown
# Context

## Memories
{memory items, up to budget}

## Code
{code items, up to budget}

## Experiences
{experience items, up to budget}

## Values
{value items, up to budget}

## Commits
{commit items, up to budget}

---
*{total_items} items from {sources_count} sources*
```

### Empty Source Handling

If a source returns no results, omit that section entirely (don't show empty headers).

### Truncation

If content exceeds max_tokens:
1. Warn via log (structlog)
2. Include all selected items anyway (soft limit)
3. Note in FormattedContext that limit was exceeded

### Token Estimation

Use simple heuristic for token counting:
```python
def estimate_tokens(text: str) -> int:
    """
    Estimate token count for text.

    Heuristic: ~4 characters per token (conservative for English).
    """
    return len(text) // 4
```

## Premortem Context

The `get_premortem_context()` method provides warnings before risky actions:

### Query Strategy

```python
# Query experiences on full axis with domain filter
full_exps = await searcher.search_experiences(
    query=f"failures and issues in {domain}",
    axis="full",
    domain=domain,
    outcome="falsified",
    limit=limit,
)

# Query experiences on strategy axis (only if strategy provided)
strategy_exps = []
if strategy:
    strategy_exps = await searcher.search_experiences(
        query=f"outcomes using {strategy} strategy",
        axis="strategy",
        strategy=strategy,
        limit=limit,
    )

# Query surprises for domain
surprises = await searcher.search_experiences(
    query=f"unexpected outcomes in {domain}",
    axis="surprise",
    domain=domain,
    limit=limit,
)

# Query root causes for domain
root_causes = await searcher.search_experiences(
    query=f"why hypotheses fail in {domain}",
    axis="root_cause",
    domain=domain,
    limit=limit,
)

# Query relevant values
value_query = f"principles for {domain}" + (f" using {strategy}" if strategy else "")
values = await searcher.search_values(
    query=value_query,
    limit=5,
)
```

### Premortem Format

```markdown
# Premortem: {domain}{" with " + strategy if strategy else ""}

## Common Failures
{falsified experiences from full axis}

{if strategy:}
## Strategy Performance
{experiences from strategy axis, highlighting failures}
{end if}

## Unexpected Outcomes
{experiences from surprise axis}

## Root Causes to Watch
{experiences from root_cause axis}

## Relevant Principles
{values matching domain/strategy}

---
*Based on {count} past experiences*
```

## Error Handling

```python
class ContextAssemblyError(Exception):
    """Base exception for context assembly."""
    pass

class InvalidContextTypeError(ContextAssemblyError):
    """Raised when invalid context type requested."""
    pass
```

**Error cases**:
1. Invalid context type in `context_types` → Raise InvalidContextTypeError
2. Searcher returns error → Log warning, skip that source, continue
3. Empty results from all sources → Return empty FormattedContext (not an error)
4. Network timeout to vector store → Log error, return partial results

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_assemble_single_source(mock_searcher):
    """Test assembly with single source."""
    # Mock searcher to return fake memories
    # Verify formatted output structure
    # Check token count estimation

@pytest.mark.asyncio
async def test_assemble_multiple_sources(mock_searcher):
    """Test assembly combining multiple sources."""
    # Mock all sources
    # Verify deduplication
    # Check token budget distribution

@pytest.mark.asyncio
async def test_token_budget_enforcement(mock_searcher):
    """Test token budget limits item selection."""
    # Mock source with many results
    # Verify items truncated to budget
    # Check highest-ranked items selected

@pytest.mark.asyncio
async def test_deduplication(mock_searcher):
    """Test deduplication across sources."""
    # Mock duplicate items in different sources
    # Verify only one kept
    # Check highest-relevance source wins

@pytest.mark.asyncio
async def test_empty_sources(mock_searcher):
    """Test handling when sources return no results."""
    # Mock empty results
    # Verify no empty sections in markdown
    # Check graceful handling

@pytest.mark.asyncio
async def test_premortem_context(mock_searcher):
    """Test premortem context generation."""
    # Mock experiences with domain/strategy filters
    # Verify queries use correct filters
    # Check premortem format

def test_invalid_context_type():
    """Test error on invalid context type."""
    # Should raise InvalidContextTypeError

@pytest.mark.asyncio
async def test_partial_failure(mock_searcher):
    """Test handling when one source fails."""
    # Mock one source to raise exception
    # Verify others still queried
    # Check partial results returned
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_end_to_end_assembly(
    qdrant_container,
    embedding_service,
    vector_store,
):
    """Test full assembly with real data."""
    # Setup: Index real data in all collections
    # Query for mixed context
    # Verify markdown format
    # Check all sources present
    # Validate token counts

@pytest.mark.asyncio
async def test_premortem_with_real_data(
    qdrant_container,
    embedding_service,
    vector_store,
):
    """Test premortem with real experience data."""
    # Setup: Index experiences with various domains/strategies
    # Query premortem for specific domain/strategy
    # Verify filtered results
    # Check premortem structure
```

## Performance Requirements

| Operation | Target | Notes |
|-----------|--------|-------|
| assemble_context() | <1s | Parallel queries to all sources |
| get_premortem_context() | <1.5s | More complex filtering |
| Token estimation | <10ms | Simple heuristic |
| Deduplication | <50ms | In-memory comparison |
| Formatting | <100ms | Markdown string building |

## Acceptance Criteria

### Functional
1. ✅ assemble_context() queries all requested sources
2. ✅ Results ranked by relevance within each source
3. ✅ Deduplication works across sources
4. ✅ Token budget distributed proportionally
5. ✅ Markdown output formatted correctly
6. ✅ Empty sources omitted from output
7. ✅ Invalid context type raises InvalidContextTypeError
8. ✅ get_premortem_context() filters by domain/strategy
9. ✅ Premortem queries all relevant axes (full, strategy, surprise, root_cause)
10. ✅ FormattedContext includes all metadata fields

### Quality
1. ✅ Token estimation within 20% of actual
2. ✅ Deduplication catches >90% of duplicates
3. ✅ Markdown renders correctly in Claude Code
4. ✅ Error messages are clear and actionable
5. ✅ Partial failures don't crash assembly
6. ✅ Type hints for all public APIs
7. ✅ Docstrings for all classes and methods
8. ✅ Structured logging via structlog

### Performance
1. ✅ Assembly completes in <1s with 5 sources
2. ✅ Premortem completes in <1.5s
3. ✅ Token budget distribution is fair
4. ✅ Memory usage <50MB per assembly

### Testing
1. ✅ Unit test coverage ≥ 90%
2. ✅ Integration tests with real Qdrant
3. ✅ All error cases tested
4. ✅ Type checking passes (mypy --strict)
5. ✅ Linting passes (ruff)

## Out of Scope

- Automatic context injection via hooks (future)
- Light/rich context modes (future enhancement)
- Interactive context refinement (future)
- Context caching (implement later if needed)
- Multi-query context (one query per call)
- Custom formatting templates
- Context versioning
- Analytics on context usage

## Notes

- All async operations use `await` consistently
- Logging via `structlog` following existing codebase patterns
- Token budget is soft limit (may exceed for quality)
- Deduplication uses fuzzy matching (90% threshold)
- Premortem is specialized use case of general assembly
- Source weights are tunable but have sensible defaults
- Empty results from all sources is not an error
- Formatting is optimized for Claude Code markdown rendering
