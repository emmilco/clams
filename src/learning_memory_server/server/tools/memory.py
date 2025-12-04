"""Memory tools for MCP server."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog
from mcp.server import Server

from learning_memory_server.server.errors import MCPError, ValidationError
from learning_memory_server.server.tools import ServiceContainer

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


def register_memory_tools(server: Server, services: ServiceContainer) -> None:
    """Register memory tools with MCP server.

    Args:
        server: MCP Server instance
        services: Initialized service container
    """

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def store_memory(
        content: str,
        category: str,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        """Store a new memory with semantic embedding.

        Args:
            content: Memory content (max 10,000 chars)
            category: One of: preference, fact, event, workflow, context,
                error, decision
            importance: Importance score 0.0-1.0 (default 0.5)
            tags: Optional tags for categorization

        Returns:
            Stored memory record with ID and metadata

        Raises:
            ValidationError: If inputs are invalid
            MCPError: If storage fails
        """
        logger.info("memory.store", category=category, importance=importance)

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
            embedding = await services.embedding_service.embed(content)

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

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def retrieve_memories(
        query: str,
        limit: int = 10,
        category: str | None = None,
        min_importance: float = 0.0,
    ) -> dict[str, Any]:
        """Search memories semantically.

        Args:
            query: Search query
            limit: Max results (1-100, default 10)
            category: Optional category filter
            min_importance: Minimum importance filter (0.0-1.0)

        Returns:
            Search results with scores and metadata
        """
        logger.info("memory.retrieve", query=query[:50], limit=limit)

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
            query_embedding = await services.embedding_service.embed(query)

            # Build filters
            filters = {}
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

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def list_memories(
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List memories with filters (non-semantic).

        Args:
            category: Optional category filter
            tags: Optional tag filters (ANY match)
            limit: Max results (1-200, default 50)
            offset: Pagination offset (default 0)

        Returns:
            List of memories with pagination metadata
        """
        logger.info("memory.list", category=category, limit=limit, offset=offset)

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
            filters = {}
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
            # NOTE: VectorStore.scroll() doesn't support offset parameter.
            # We fetch more results and slice them manually for pagination.
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

    @server.call_tool()  # type: ignore[no-untyped-call, misc]
    async def delete_memory(memory_id: str) -> dict[str, bool]:
        """Delete a memory by ID.

        Args:
            memory_id: Memory ID to delete

        Returns:
            Deletion status
        """
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
