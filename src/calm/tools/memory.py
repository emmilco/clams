"""Memory tools for MCP server."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from calm.config import settings
from calm.embedding.base import EmbeddingService
from calm.search.searcher import (
    VALID_SEARCH_MODES,
    _hybrid_search,
    _keyword_search,
    _semantic_search,
)
from calm.storage.base import VectorStore

from .validation import (
    ValidationError,
    validate_importance_range,
    validate_query_string,
    validate_tags,
    validate_uuid,
)

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


def _error_response(error_type: str, message: str) -> dict[str, Any]:
    """Create a standardized error response."""
    return {"error": {"type": error_type, "message": message}}


async def _ensure_memories_collection(
    vector_store: VectorStore, semantic_embedder: EmbeddingService
) -> None:
    """Ensure memories collection exists (lazy initialization).

    Creates the collection on first use. Uses module-level caching to avoid
    repeated creation attempts within a process.
    """
    global _memories_collection_ensured
    if _memories_collection_ensured:
        return

    try:
        await vector_store.create_collection(
            name="memories",
            dimension=semantic_embedder.dimension,
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


def get_memory_tools(
    vector_store: VectorStore, semantic_embedder: EmbeddingService
) -> dict[str, ToolFunc]:
    """Get memory tool implementations for the dispatcher.

    Args:
        vector_store: Initialized vector store
        semantic_embedder: Initialized semantic embedding service

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

        try:
            # Ensure collection exists (lazy initialization)
            await _ensure_memories_collection(vector_store, semantic_embedder)

            # Validate category
            if category not in VALID_CATEGORIES:
                raise ValidationError(
                    f"Invalid category '{category}'. "
                    f"Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
                )

            # Validate content length (no silent truncation per spec)
            max_length = settings.memory_content_max_length
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

            # Validate tags array
            validate_tags(tags, max_count=20, max_length=50)

            tags = tags or []

            # Generate ID and timestamp
            memory_id = str(uuid4())
            created_at = datetime.now(UTC)

            # Generate embedding
            embedding = await semantic_embedder.embed(content)

            # Store in vector store
            payload = {
                "id": memory_id,
                "content": content,
                "category": category,
                "importance": importance,
                "tags": tags,
                "created_at": created_at.isoformat(),
            }

            await vector_store.upsert(
                collection="memories",
                id=memory_id,
                vector=embedding,
                payload=payload,
            )

            logger.info("memory.stored", memory_id=memory_id, category=category)

            # Return confirmation without content (token-efficient)
            # Content is only needed on retrieval, not store confirmation
            return {
                "id": memory_id,
                "status": "stored",
                "category": category,
                "importance": importance,
                "created_at": created_at.isoformat(),
            }

        except ValidationError as e:
            logger.warning("memory.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error("memory.store_failed", error=str(e), exc_info=True)
            return _error_response("internal_error", f"Failed to store memory: {e}")

    async def retrieve_memories(
        query: str,
        limit: int = 10,
        category: str | None = None,
        min_importance: float = 0.0,
        search_mode: str = "semantic",
    ) -> dict[str, Any]:
        """Search memories semantically, by keyword, or hybrid."""
        logger.info("memory.retrieve", query=query[:50], limit=limit)

        try:
            # Ensure collection exists (lazy initialization)
            await _ensure_memories_collection(vector_store, semantic_embedder)

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

            # Validate min_importance range
            validate_importance_range(min_importance, "min_importance")

            # Validate query length
            validate_query_string(query)

            # Validate search mode
            if search_mode not in VALID_SEARCH_MODES:
                valid = ", ".join(f"'{m}'" for m in VALID_SEARCH_MODES)
                raise ValidationError(
                    f"Invalid search_mode '{search_mode}'. Must be one of: {valid}"
                )

            # Handle empty query
            if not query.strip():
                return {"results": [], "count": 0}

            # Build filters
            filters: dict[str, Any] = {}
            if category:
                filters["category"] = category
            if min_importance > 0.0:
                filters["importance"] = {"$gte": min_importance}

            # Dispatch search based on mode
            collection = "memories"
            text_fields = ["content"]

            if search_mode == "keyword":
                results = await _keyword_search(
                    vector_store, collection, query, limit,
                    filters if filters else None, text_fields,
                )
            elif search_mode == "hybrid":
                results = await _hybrid_search(
                    semantic_embedder, vector_store, collection, query, limit,
                    filters if filters else None, text_fields,
                )
            else:
                results = await _semantic_search(
                    semantic_embedder, vector_store, collection, query, limit,
                    filters if filters else None,
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

        except ValidationError as e:
            logger.warning("memory.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error("memory.retrieve_failed", error=str(e), exc_info=True)
            return _error_response(
                "internal_error", f"Failed to retrieve memories: {e}"
            )

    async def list_memories(
        category: str | None = None,
        tags: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        """List memories with filters (non-semantic)."""
        logger.info("memory.list", category=category, limit=limit, offset=offset)

        try:
            # Ensure collection exists (lazy initialization)
            await _ensure_memories_collection(vector_store, semantic_embedder)

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

            # Validate tags array
            validate_tags(tags, max_count=20, max_length=50)

            # Build filters
            filters: dict[str, Any] = {}
            if category:
                filters["category"] = category
            if tags:
                # $in matches ANY of the provided tags
                filters["tags"] = {"$in": tags}

            # Get count first
            total = await vector_store.count(
                collection="memories",
                filters=filters if filters else None,
            )

            # Scroll through results
            fetch_limit = offset + limit
            results = await vector_store.scroll(
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

            # Return metadata only (no content) for token efficiency
            # List is for browsing/filtering, not semantic search context
            formatted = [
                {
                    "id": r.id,  # Use SearchResult.id, not payload
                    "category": r.payload.get("category", "unknown"),
                    "importance": r.payload.get("importance", 0.5),
                    "tags": r.payload.get("tags", []),
                    "created_at": r.payload.get("created_at", ""),
                }
                for r in sorted_results
            ]

            logger.info("memory.listed", count=len(formatted), total=total)

            return {
                "results": formatted,
                "count": len(formatted),
                "total": total,
            }

        except ValidationError as e:
            logger.warning("memory.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error("memory.list_failed", error=str(e), exc_info=True)
            return _error_response("internal_error", f"Failed to list memories: {e}")

    async def delete_memory(memory_id: str) -> dict[str, Any]:
        """Delete a memory by ID."""
        logger.info("memory.delete", memory_id=memory_id)

        try:
            # Validate UUID format
            validate_uuid(memory_id, "memory_id")
        except ValidationError as e:
            logger.warning("memory.validation_error", error=str(e))
            return _error_response("validation_error", str(e))

        try:
            await vector_store.delete(
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
