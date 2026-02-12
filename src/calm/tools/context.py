"""Context assembly tool for user prompt injection in CALM MCP server.

This tool queries stored values and experiences to provide relevant
context when the user submits a prompt.
"""

from collections.abc import Callable, Coroutine
from typing import Any

import structlog

from calm.embedding.base import EmbeddingService
from calm.storage.base import VectorStore

from .validation import ValidationError, validate_query_string

logger = structlog.get_logger()

# Type alias for async tool function
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# Valid context types
VALID_CONTEXT_TYPES = ["values", "experiences", "memories", "code", "commits"]


def _error_response(error_type: str, message: str) -> dict[str, Any]:
    """Create a standardized error response."""
    return {"error": {"type": error_type, "message": message}}


def validate_context_types(context_types: list[str]) -> None:
    """Validate context types for assemble_context.

    Args:
        context_types: List of context type strings

    Raises:
        ValidationError: If any context type is invalid
    """
    invalid = [t for t in context_types if t not in VALID_CONTEXT_TYPES]
    if invalid:
        raise ValidationError(
            f"Invalid context types: {invalid}. "
            f"Valid options: {', '.join(VALID_CONTEXT_TYPES)}"
        )


def validate_limit_range(
    value: int,
    min_val: int,
    max_val: int,
    param_name: str = "limit",
) -> None:
    """Validate integer is within allowed range.

    Args:
        value: Value to validate
        min_val: Minimum allowed value (inclusive)
        max_val: Maximum allowed value (inclusive)
        param_name: Parameter name for error message

    Raises:
        ValidationError: If value is out of range
    """
    if not min_val <= value <= max_val:
        raise ValidationError(
            f"{param_name.capitalize()} {value} out of range. "
            f"Must be between {min_val} and {max_val}."
        )


def get_context_tools(
    vector_store: VectorStore,
    semantic_embedder: EmbeddingService,
    context_assembler: Any = None,
) -> dict[str, ToolFunc]:
    """Get context assembly tool implementations.

    Args:
        vector_store: Initialized vector store
        semantic_embedder: Initialized semantic embedding service

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
        try:
            # Validate parameters
            if context_types is not None:
                validate_context_types(context_types)
            else:
                context_types = ["values", "experiences"]

            validate_limit_range(limit, min_val=1, max_val=50, param_name="limit")
            validate_limit_range(
                max_tokens, min_val=100, max_val=10000, param_name="max_tokens"
            )

            # Validate query length
            validate_query_string(query)

            # Empty query returns empty result gracefully (not error)
            if not query.strip():
                return {
                    "markdown": "",
                    "token_count": 0,
                    "item_count": 0,
                    "truncated": False,
                }

            # If context assembler is available, delegate to it
            if context_assembler is not None:
                try:
                    result = await context_assembler.assemble_context(
                        query=query,
                        context_types=context_types,
                        limit=limit,
                        max_tokens=max_tokens,
                    )
                    return {
                        "markdown": result.markdown,
                        "token_count": result.token_count,
                        "item_count": len(result.items),
                        "truncated": result.budget_exceeded,
                        "sources_used": result.sources_used,
                    }
                except Exception as e:
                    logger.warning("context.assembler_failed", error=str(e))
                    # Fall through to inline implementation

            sections: list[str] = []
            total_items = 0

            # Get values (distilled learnings)
            if "values" in context_types:
                try:
                    # Query values collection
                    results = await vector_store.scroll(
                        collection="values",
                        limit=limit,
                        filters=None,
                        with_vectors=False,
                    )

                    if results:
                        value_lines = [
                            f"- {r.payload.get('text', '')}" for r in results
                        ]
                        sections.append("## Learned Values\n" + "\n".join(value_lines))
                        total_items += len(results)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "not found" not in error_msg and "404" not in str(e):
                        logger.warning("context.values_failed", error=str(e))

            # Get relevant experiences
            if "experiences" in context_types and query:
                try:
                    # Generate query embedding
                    query_embedding = await semantic_embedder.embed(query)

                    # Search experiences (fewer, they're verbose)
                    exp_limit = min(limit, 5)

                    results = await vector_store.search(
                        collection="ghap_full",
                        query=query_embedding,
                        limit=exp_limit,
                        filters=None,
                    )

                    if results:
                        exp_lines = []
                        for r in results:
                            domain = r.payload.get("domain", "unknown")
                            goal = r.payload.get("goal", "")
                            outcome = r.payload.get("outcome_status", "unknown")
                            exp_lines.append(f"- **{domain}**: {goal} ({outcome})")

                        sections.append(
                            "## Relevant Experiences\n" + "\n".join(exp_lines)
                        )
                        total_items += len(results)
                except Exception as e:
                    error_msg = str(e).lower()
                    if "not found" not in error_msg and "404" not in str(e):
                        logger.warning("context.experiences_failed", error=str(e))

            # Build markdown
            markdown = "\n\n".join(sections) if sections else ""

            # Rough token estimate (4 chars per token)
            token_count = len(markdown) // 4

            return {
                "markdown": markdown,
                "token_count": token_count,
                "item_count": total_items,
                "truncated": token_count > max_tokens,
            }

        except ValidationError as e:
            logger.warning("context.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error("context.assemble_failed", error=str(e), exc_info=True)
            return _error_response("internal_error", f"Failed to assemble context: {e}")

    return {
        "assemble_context": assemble_context,
    }
