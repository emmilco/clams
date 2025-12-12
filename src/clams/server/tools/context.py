"""Context assembly tool for user prompt injection.

This tool queries stored values and experiences to provide relevant
context when the user submits a prompt.

Tools:
- assemble_context: Get relevant context for a user prompt
"""

from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from clams.search import Searcher
from clams.values import ValueStore

logger = structlog.get_logger()

# Type alias for async tool function
AsyncToolFn = Callable[..., Coroutine[Any, Any, dict[str, Any]]]


def get_context_tools(
    searcher: Searcher,
    value_store: ValueStore,
) -> dict[str, AsyncToolFn]:
    """Get context assembly tool implementations.

    Args:
        searcher: Searcher instance for experience queries
        value_store: ValueStore instance for value queries

    Returns:
        Dictionary mapping tool names to async implementations
    """

    async def assemble_context(
        query: str,
        context_types: list[str] | None = None,
        limit: int = 10,
        max_tokens: int = 1500,
    ) -> dict[str, Any]:
        """Assemble relevant context for a user prompt.

        Queries stored values and experiences to find relevant information
        to inject into the user's prompt.

        Args:
            query: User's prompt text
            context_types: Types to include ("values", "experiences")
            limit: Maximum items per type (default 10)
            max_tokens: Approximate token budget (default 1500)

        Returns:
            Dict with:
            - markdown: Formatted context as markdown string
            - token_count: Approximate token count
            - item_count: Total items included
            - truncated: Whether content was truncated
        """
        if context_types is None:
            context_types = ["values", "experiences"]

        sections: list[str] = []
        total_items = 0

        # Get values (distilled learnings)
        # Note: list_values doesn't take a limit arg, we slice manually
        if "values" in context_types:
            try:
                all_values = await value_store.list_values()
                values = all_values[:limit]
                if values:
                    value_lines = [f"- {v.text}" for v in values]
                    sections.append("## Learned Values\n" + "\n".join(value_lines))
                    total_items += len(values)
            except Exception as e:
                logger.warning("context.values_failed", error=str(e))

        # Get relevant experiences
        if "experiences" in context_types and query:
            try:
                experiences = await searcher.search_experiences(
                    query=query,
                    limit=min(limit, 5),  # Fewer experiences, they're verbose
                )
                if experiences:
                    exp_lines = []
                    for exp in experiences:
                        # ExperienceResult is a dataclass with direct attributes
                        exp_lines.append(
                            f"- **{exp.domain}**: "
                            f"{exp.goal} "
                            f"({exp.outcome_status})"
                        )
                    sections.append(
                        "## Relevant Experiences\n" + "\n".join(exp_lines)
                    )
                    total_items += len(experiences)
            except Exception as e:
                logger.warning("context.experiences_failed", error=str(e))

        # Build markdown
        if sections:
            markdown = "\n\n".join(sections)
        else:
            markdown = ""

        # Rough token estimate (4 chars per token)
        token_count = len(markdown) // 4

        return {
            "markdown": markdown,
            "token_count": token_count,
            "item_count": total_items,
            "truncated": token_count > max_tokens,
        }

    return {
        "assemble_context": assemble_context,
    }
