"""Learning tools for clustering and value formation in CALM MCP server."""

from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import structlog

from calm.embedding.base import EmbeddingService
from calm.search.searcher import (
    VALID_SEARCH_MODES,
    _hybrid_search,
    _keyword_search,
    _semantic_search,
)
from calm.storage.base import VectorStore

from .enums import validate_domain, validate_outcome_status
from .validation import ValidationError, validate_query_string

logger = structlog.get_logger()

# Type alias for tool functions
ToolFunc = Callable[..., Coroutine[Any, Any, dict[str, Any]]]

# Valid experience axes
VALID_AXES = ["full", "strategy", "surprise", "root_cause"]

# Track collection initialization
_values_collection_ensured = False


def validate_axis(axis: str) -> None:
    """Validate clustering axis value.

    Args:
        axis: Axis value to validate

    Raises:
        ValidationError: If axis is invalid
    """
    if axis not in VALID_AXES:
        raise ValidationError(
            f"Invalid axis '{axis}'. Valid options: {', '.join(VALID_AXES)}"
        )


def _error_response(error_type: str, message: str) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_type: Type of error
        message: Error message

    Returns:
        Error response dict
    """
    return {"error": {"type": error_type, "message": message}}


async def _ensure_values_collection(
    vector_store: VectorStore, semantic_embedder: EmbeddingService
) -> None:
    """Ensure values collection exists (lazy initialization)."""
    global _values_collection_ensured
    if _values_collection_ensured:
        return

    try:
        await vector_store.create_collection(
            name="values",
            dimension=semantic_embedder.dimension,
            distance="cosine",
        )
        logger.info("collection_created", name="values")
    except Exception as e:
        error_msg = str(e).lower()
        if "already exists" in error_msg or "409" in str(e):
            logger.debug("collection_exists", name="values")
        else:
            raise

    _values_collection_ensured = True


def get_learning_tools(
    vector_store: VectorStore,
    semantic_embedder: EmbeddingService,
    experience_clusterer: Any = None,
    value_store: Any = None,
) -> dict[str, ToolFunc]:
    """Get learning tool implementations for the dispatcher.

    Args:
        vector_store: Initialized vector store
        semantic_embedder: Initialized semantic embedding service

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def search_experiences(
        query: str,
        axis: str = "full",
        domain: str | None = None,
        outcome: str | None = None,
        limit: int = 10,
        search_mode: str = "semantic",
    ) -> dict[str, Any]:
        """Search experiences semantically, by keyword, or hybrid.

        Args:
            query: Search query
            axis: Axis to search (default: full)
            domain: Filter by domain (optional)
            outcome: Filter by outcome status (optional)
            limit: Maximum results (default 10, max 50)
            search_mode: Search mode - "semantic", "keyword", or "hybrid"
                         (default "semantic")

        Returns:
            List of matching experiences with scores
        """
        try:
            # Validate query length
            validate_query_string(query)

            # Handle empty query
            if not query or not query.strip():
                return {"results": [], "count": 0}

            # Validate axis
            validate_axis(axis)

            # Validate search mode
            if search_mode not in VALID_SEARCH_MODES:
                valid = ", ".join(f"'{m}'" for m in VALID_SEARCH_MODES)
                raise ValidationError(
                    f"Invalid search_mode '{search_mode}'. Must be one of: {valid}"
                )

            # Validate domain if provided
            if domain is not None:
                validate_domain(domain)

            # Validate outcome if provided
            if outcome is not None:
                validate_outcome_status(outcome)

            # Validate limit
            if not 1 <= limit <= 50:
                raise ValidationError(
                    f"Limit must be between 1 and 50 (got {limit})"
                )

            # Determine collection name based on axis
            collection = f"ghap_{axis}"

            # Build filters
            filters: dict[str, Any] = {}
            if domain:
                filters["domain"] = domain
            if outcome:
                filters["outcome_status"] = outcome

            text_fields = [
                "goal", "hypothesis", "action", "prediction", "outcome_result",
            ]
            if axis == "surprise":
                text_fields.append("surprise")

            try:
                # Dispatch search based on mode
                if search_mode == "keyword":
                    results = await _keyword_search(
                        vector_store, collection, query, limit,
                        filters if filters else None, text_fields,
                    )
                elif search_mode == "hybrid":
                    results = await _hybrid_search(
                        semantic_embedder, vector_store, collection,
                        query, limit,
                        filters if filters else None, text_fields,
                    )
                else:
                    results = await _semantic_search(
                        semantic_embedder, vector_store, collection,
                        query, limit,
                        filters if filters else None,
                    )
            except Exception as search_error:
                # Handle missing collection gracefully
                error_msg = str(search_error).lower()
                if "not found" in error_msg or "404" in str(search_error):
                    logger.info(
                        "learning.collection_not_found",
                        collection=collection,
                    )
                    return {"results": [], "count": 0}
                raise

            # Format results
            formatted = []
            for r in results:
                created_at = r.payload.get("created_at")
                if isinstance(created_at, str):
                    pass  # Already ISO format
                elif isinstance(created_at, (int, float)):
                    created_at = datetime.fromtimestamp(created_at).isoformat()
                else:
                    created_at = None

                formatted.append(
                    {
                        "id": r.id,
                        "ghap_id": r.payload.get("ghap_id", r.id),
                        "axis": axis,
                        "domain": r.payload.get("domain"),
                        "strategy": r.payload.get("strategy"),
                        "goal": r.payload.get("goal"),
                        "hypothesis": r.payload.get("hypothesis"),
                        "action": r.payload.get("action"),
                        "prediction": r.payload.get("prediction"),
                        "outcome_status": r.payload.get("outcome_status"),
                        "outcome_result": r.payload.get("outcome_result"),
                        "surprise": r.payload.get("surprise"),
                        "root_cause": r.payload.get("root_cause"),
                        "lesson": r.payload.get("lesson"),
                        "confidence_tier": r.payload.get("confidence_tier"),
                        "iteration_count": r.payload.get("iteration_count"),
                        "score": r.score,
                        "created_at": created_at,
                    }
                )

            logger.info(
                "learning.experiences_searched",
                query=query[:50],
                axis=axis,
                count=len(formatted),
            )

            return {"results": formatted, "count": len(formatted)}

        except ValidationError as e:
            logger.warning("learning.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="search_experiences",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    async def get_clusters(axis: str) -> dict[str, Any]:
        """Get cluster information for a given axis.

        Args:
            axis: Axis to cluster (full, strategy, surprise, root_cause)

        Returns:
            Cluster information including sizes and noise count
        """
        try:
            # Validate axis
            validate_axis(axis)

            if experience_clusterer is None or value_store is None:
                return {
                    "status": "not_available",
                    "message": (
                        "Clustering not initialized."
                        " Restart server with real services."
                    ),
                    "axis": axis,
                }

            try:
                clusters = await value_store.get_clusters(axis)
            except ValueError as e:
                return {
                    "status": "error",
                    "message": str(e),
                    "axis": axis,
                }

            formatted = [
                {
                    "cluster_id": c.cluster_id,
                    "axis": c.axis,
                    "label": c.label,
                    "size": c.size,
                    "avg_weight": c.avg_weight,
                    "member_count": len(c.member_ids),
                }
                for c in clusters
            ]

            noise_count = sum(1 for c in clusters if c.label == -1)

            return {
                "clusters": formatted,
                "count": len(formatted),
                "noise_count": noise_count,
                "axis": axis,
            }

        except ValidationError as e:
            logger.warning("learning.error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="get_clusters",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    async def get_cluster_members(
        cluster_id: str,
        limit: int = 50,
    ) -> dict[str, Any]:
        """Get experiences in a specific cluster.

        Args:
            cluster_id: Cluster ID (format: 'axis_label', e.g., 'full_0')
            limit: Maximum results (default 50, max 100)

        Returns:
            List of experiences in the cluster
        """
        try:
            # Validate cluster_id format
            if not cluster_id or "_" not in cluster_id:
                raise ValidationError(
                    f"Invalid cluster_id format: {cluster_id}. "
                    "Expected format: 'axis_label' (e.g., 'full_0', 'strategy_2')"
                )

            # Validate limit
            if not 1 <= limit <= 100:
                raise ValidationError(
                    f"Limit must be between 1 and 100 (got {limit})"
                )

            # Parse axis from cluster_id
            parts = cluster_id.rsplit("_", 1)
            if len(parts) != 2:
                raise ValidationError(
                    f"Invalid cluster_id format: {cluster_id}. "
                    "Expected format: 'axis_label'"
                )

            axis = parts[0]
            validate_axis(axis)

            # Parse cluster label
            try:
                label = int(parts[1])
            except ValueError:
                raise ValidationError(
                    f"Invalid cluster label in cluster_id: {cluster_id}. "
                    "Label must be an integer"
                ) from None

            # Query appropriate axis collection
            collection = f"ghap_{axis}"

            try:
                # Cluster label is stored in payload metadata
                results = await vector_store.scroll(
                    collection=collection,
                    limit=limit,
                    filters={"cluster_label": label},
                    with_vectors=False,
                )
            except Exception as scroll_error:
                error_msg = str(scroll_error).lower()
                if "not found" in error_msg or "404" in str(scroll_error):
                    logger.info(
                        "learning.collection_not_found",
                        collection=collection,
                    )
                    return {
                        "cluster_id": cluster_id,
                        "axis": axis,
                        "members": [],
                        "count": 0,
                    }
                raise

            # Format members
            members = [
                {
                    "id": r.id,
                    "domain": r.payload.get("domain"),
                    "strategy": r.payload.get("strategy"),
                    "outcome_status": r.payload.get("outcome_status"),
                    "confidence_tier": r.payload.get("confidence_tier"),
                    "cluster_label": r.payload.get("cluster_label"),
                }
                for r in results
            ]

            logger.info(
                "learning.cluster_members_retrieved",
                cluster_id=cluster_id,
                axis=axis,
                label=label,
                count=len(members),
            )

            return {
                "cluster_id": cluster_id,
                "axis": axis,
                "members": members,
                "count": len(members),
            }

        except ValidationError as e:
            logger.warning("learning.error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="get_cluster_members",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    async def validate_value(
        text: str,
        cluster_id: str,
    ) -> dict[str, Any]:
        """Validate a proposed value statement against a cluster centroid.

        Args:
            text: Proposed value statement (max 500 chars)
            cluster_id: Target cluster ID

        Returns:
            Validation result with similarity metrics
        """
        try:
            # Validate text
            if not text or not text.strip():
                raise ValidationError("Field 'text' cannot be empty")

            if len(text) > 500:
                raise ValidationError(
                    f"Field 'text' exceeds 500 character limit ({len(text)} chars)"
                )

            # Validate cluster_id format
            if not cluster_id or "_" not in cluster_id:
                raise ValidationError(
                    f"Invalid cluster_id format: {cluster_id}. "
                    "Expected format: 'axis_label'"
                )

            # Parse axis from cluster_id
            parts = cluster_id.rsplit("_", 1)
            if len(parts) != 2:
                raise ValidationError(
                    f"Invalid cluster_id format: {cluster_id}. "
                    "Expected format: 'axis_label'"
                )

            axis = parts[0]
            validate_axis(axis)

            if value_store is None:
                return {
                    "status": "not_available",
                    "message": (
                        "Value store not initialized."
                        " Restart server with real services."
                    ),
                }

            try:
                validation = await value_store.validate_value_candidate(
                    text, cluster_id
                )
            except ValueError as e:
                return {
                    "valid": False,
                    "cluster_id": cluster_id,
                    "reason": str(e),
                }

            result: dict[str, Any] = {
                "valid": validation.valid,
                "cluster_id": cluster_id,
            }

            if validation.valid:
                result["similarity"] = validation.similarity
            else:
                result["reason"] = validation.reason

            if validation.candidate_distance is not None:
                result["metrics"] = {
                    "candidate_distance": validation.candidate_distance,
                    "mean_distance": validation.mean_distance,
                    "std_distance": validation.std_distance,
                    "threshold": validation.threshold,
                }

            return result

        except ValidationError as e:
            logger.warning("learning.error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="validate_value",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    async def store_value(
        text: str,
        cluster_id: str,
        axis: str,
    ) -> dict[str, Any]:
        """Store a validated value statement.

        Args:
            text: Value statement (max 500 chars)
            cluster_id: Associated cluster ID
            axis: Axis (full, strategy, surprise, root_cause)

        Returns:
            Stored value record with id and timestamp
        """
        try:
            # Ensure collection exists
            await _ensure_values_collection(vector_store, semantic_embedder)

            # Validate text
            if not text or not text.strip():
                raise ValidationError("Field 'text' cannot be empty")

            if len(text) > 500:
                raise ValidationError(
                    f"Field 'text' exceeds 500 character limit ({len(text)} chars)"
                )

            # Validate cluster_id format
            if not cluster_id or "_" not in cluster_id:
                raise ValidationError(
                    f"Invalid cluster_id format: {cluster_id}. "
                    "Expected format: 'axis_label'"
                )

            # Validate axis
            validate_axis(axis)

            # Generate ID and timestamp
            value_id = str(uuid4())
            created_at = datetime.now(UTC)

            # Generate embedding
            embedding = await semantic_embedder.embed(text)

            # Store in vector store
            payload = {
                "id": value_id,
                "text": text,
                "cluster_id": cluster_id,
                "axis": axis,
                "validated_at": created_at.timestamp(),
                "created_at": created_at.isoformat(),
            }

            await vector_store.upsert(
                collection="values",
                id=value_id,
                vector=embedding,
                payload=payload,
            )

            logger.info(
                "learning.value_stored",
                value_id=value_id,
                cluster_id=cluster_id,
                axis=axis,
            )

            return {
                "id": value_id,
                "text": text,
                "cluster_id": cluster_id,
                "axis": axis,
                "created_at": created_at.isoformat(),
            }

        except ValidationError as e:
            logger.warning("learning.error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="store_value",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    async def list_values(
        axis: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        """List stored values with optional axis filter.

        Args:
            axis: Filter by axis (optional)
            limit: Maximum results (default 20, max 100)

        Returns:
            List of stored values
        """
        try:
            # Ensure collection exists
            await _ensure_values_collection(vector_store, semantic_embedder)

            # Validate axis if provided
            if axis is not None:
                validate_axis(axis)

            # Validate limit
            if not 1 <= limit <= 100:
                raise ValidationError(
                    f"Limit must be between 1 and 100 (got {limit})"
                )

            # Build filters
            filters = {"axis": axis} if axis else None

            try:
                # Query values collection
                results = await vector_store.scroll(
                    collection="values",
                    limit=limit,
                    filters=filters,
                    with_vectors=False,
                )
            except Exception as scroll_error:
                error_msg = str(scroll_error).lower()
                if "not found" in error_msg or "404" in str(scroll_error):
                    logger.info("learning.values_collection_empty")
                    return {"results": [], "count": 0}
                raise

            # Format results
            values = []
            for r in results:
                validated_at = r.payload.get("validated_at")
                if isinstance(validated_at, (int, float)):
                    validated_at = datetime.fromtimestamp(validated_at).isoformat()

                values.append(
                    {
                        "id": r.id,
                        "text": r.payload.get("text", ""),
                        "cluster_id": r.payload.get("cluster_id", ""),
                        "axis": r.payload.get("axis", ""),
                        "validated_at": validated_at,
                        "distance_to_centroid": r.payload.get("distance_to_centroid"),
                    }
                )

            logger.info("learning.values_listed", count=len(values), axis=axis)

            return {"results": values, "count": len(values)}

        except ValidationError as e:
            logger.warning("learning.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="list_values",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    return {
        "search_experiences": search_experiences,
        "get_clusters": get_clusters,
        "get_cluster_members": get_cluster_members,
        "validate_value": validate_value,
        "store_value": store_value,
        "list_values": list_values,
    }
