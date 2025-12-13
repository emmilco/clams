"""Memory tools for MCP server."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from mcp.server import Server

from clams.server.errors import MCPError, ValidationError
from clams.server.tools import ServiceContainer

logger = structlog.get_logger()

# Valid memory categories
VALID_CATEGORIES = {
    "preference",
    "fact",
    "event",
    "workflow",
    "context",
    "error",
    "decision",
}

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# Track whether collection has been ensured (lazy initialization)
_memories_collection_ensured = False


async def _ensure_memories_collection(services: ServiceContainer) -> None:
    """Ensure memories collection exists (lazy initialization).

    Creates the collection on first use. Uses module-level caching to avoid
    repeated creation attempts within a process.
    """
    global _memories_collection_ensured
    if _memories_collection_ensured:
        return

    try:
        await services.vector_store.create_collection(
            name="memories",
            dimension=services.semantic_embedder.dimension,
            distance="cosine",
        )
        logger.info("collection_created", name="memories")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "409" in str(e):
            logger.debug("collection_exists", name="memories")
        else:
            raise

    _memories_collection_ensured = True


def get_memory_tools(services: ServiceContainer) -> dict[str, ToolFunc]:
    """Get memory tool implementations for the dispatcher.

    Args:
        services: Initialized service container

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def store_memory(
        content: str,
        category: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a new memory with semantic embedding."""
        logger.info("memory.store", category=category, importance=importance)

        # Ensure collection exists (lazy initialization)
        await _ensure_memories_collection(services)

        # Validate category
        if category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # Validate content length (no silent truncation per spec)
        max_length = 10_000
        if len(content) > max_length:
            raise ValidationError(
                f"Content too long ({len(content)} chars). "
                f"Maximum allowed is {max_length} characters."
            )

        # Validate importance range (no silent clamping per spec)
        if not 0.0 <= importance <= 1.0:
            raise ValidationError(
                f"Importance {importance} out of range. "
                f"Must be between 0.0 and 1.0."
            )

        tags = tags or []

        try:
            # Generate ID and timestamp
            memory_id = str(uuid4())
            created_at = datetime.now(UTC)

            # Generate embedding
            embedding = await services.semantic_embedder.embed(content)

            # Store in vector store
            payload = {
                "id": memory_id,
                "content": content,
                "category": category,
                "importance": importance,
                "tags": tags,
                "created_at": created_at.isoformat(),
            }

            await services.vector_store.upsert(
                collection="memories",
                id=memory_id,
                vector=embedding,
                payload=payload,
            )

            logger.info("memory.stored", memory_id=memory_id, category=category)

            return payload

        except Exception as e:
            logger.error("memory.store_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to store memory: {e}") from e

    async def retrieve_memories(
        query: str,
        limit: int = 10,
        category: str | None = None,
        min_importance: float = 0.0,
    ) -> dict[str, Any]:
        """Search memories semantically."""
        logger.info("memory.retrieve", query=query[:50], limit=limit)

        # Ensure collection exists (lazy initialization)
        await _ensure_memories_collection(services)

        # Validate category
        if category and category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # Validate limit
        if not 1 <= limit <= 100:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 100."
            )

        # Handle empty query
        if not query.strip():
            return {"results": [], "count": 0}

        try:
            # Generate query embedding
            query_embedding = await services.semantic_embedder.embed(query)

            # Build filters
            filters: dict[str, Any] = {}
            if category:
                filters["category"] = category
            if min_importance > 0.0:
                filters["importance"] = {"$gte": min_importance}

            # Search
            results = await services.vector_store.search(
                collection="memories",
                query=query_embedding,
                limit=limit,
                filters=filters if filters else None,
            )

            # Format results
            formatted = [
                {
                    **result.payload,
                    "score": result.score,
                }
                for result in results
            ]

            logger.info("memory.retrieved", count=len(formatted))

            return {"results": formatted, "count": len(formatted)}

        except Exception as e:
            logger.error("memory.retrieve_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to retrieve memories: {e}") from e

    async def list_memories(
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List memories with filters (non-semantic)."""
        logger.info("memory.list", category=category, limit=limit, offset=offset)

        # Ensure collection exists (lazy initialization)
        await _ensure_memories_collection(services)

        # Validate category
        if category and category not in VALID_CATEGORIES:
            raise ValidationError(
                f"Invalid category '{category}'. "
                f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # Validate offset
        if offset < 0:
            raise ValidationError(f"Offset {offset} must be >= 0.")

        # Validate limit
        if not 1 <= limit <= 200:
            raise ValidationError(
                f"Limit {limit} out of range. Must be between 1 and 200."
            )

        try:
            # Build filters
            filters: dict[str, Any] = {}
            if category:
                filters["category"] = category
            if tags:
                # $in matches ANY of the provided tags
                filters["tags"] = {"$in": tags}

            # Get count first
            total = await services.vector_store.count(
                collection="memories",
                filters=filters if filters else None,
            )

            # Scroll through results
            fetch_limit = offset + limit
            results = await services.vector_store.scroll(
                collection="memories",
                limit=fetch_limit,
                filters=filters if filters else None,
                with_vectors=False,
            )

            # Apply pagination manually
            results = results[offset : offset + limit]

            # Sort by created_at descending
            sorted_results = sorted(
                results,
                key=lambda x: x.payload.get("created_at", ""),
                reverse=True,
            )

            formatted = [r.payload for r in sorted_results]

            logger.info("memory.listed", count=len(formatted), total=total)

            return {
                "results": formatted,
                "count": len(formatted),
                "total": total,
            }

        except Exception as e:
            logger.error("memory.list_failed", error=str(e), exc_info=True)
            raise MCPError(f"Failed to list memories: {e}") from e

    async def delete_memory(memory_id: str) -> dict[str, bool]:
        """Delete a memory by ID."""
        logger.info("memory.delete", memory_id=memory_id)

        try:
            await services.vector_store.delete(
                collection="memories",
                id=memory_id,
            )

            logger.info("memory.deleted", memory_id=memory_id)

            return {"deleted": True}

        except Exception as e:
            logger.warning("memory.delete_failed", memory_id=memory_id, error=str(e))
            return {"deleted": False}

    return {
        "store_memory": store_memory,
        "retrieve_memories": retrieve_memories,
        "list_memories": list_memories,
        "delete_memory": delete_memory,
    }


def register_memory_tools(server: Server, services: ServiceContainer) -> None:
    """Register memory tools with MCP server.

    DEPRECATED: This function is kept for backwards compatibility with tests.
    The new dispatcher pattern uses get_memory_tools() instead.
    """
    # No-op - tools are now registered via the central dispatcher
    pass
