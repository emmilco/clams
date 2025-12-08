"""Learning tools for clustering and value formation."""

from typing import Any

import structlog
from mcp.server import Server

from clams.clustering import ExperienceClusterer
from clams.server.tools.enums import validate_axis
from clams.server.tools.errors import (
    InsufficientDataError,
    NotFoundError,
    ValidationError,
)
from clams.values import ValueStore

logger = structlog.get_logger()


def _error_response(error_type: str, message: str) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_type: Type of error
        message: Error message

    Returns:
        Error response dict
    """
    return {"error": {"type": error_type, "message": message}}


def get_learning_tools(
    experience_clusterer: ExperienceClusterer,
    value_store: ValueStore,
) -> dict[str, Any]:
    """Get learning tool implementations for the dispatcher.

    Args:
        experience_clusterer: Experience clustering service
        value_store: Value storage service

    Returns:
        Dictionary mapping tool names to their implementations
    """
    # Access vector store for get_cluster_members and list_values
    vector_store = experience_clusterer.vector_store

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

            # Check if enough experiences exist for clustering
            experience_count = await experience_clusterer.count_experiences(axis)
            if experience_count < 20:
                raise InsufficientDataError(
                    f"Not enough experiences for clustering. "
                    f"Found {experience_count}, need at least 20."
                )

            # Perform clustering
            clusters = await experience_clusterer.cluster_axis(axis)

            # Map to output format
            cluster_list = []
            noise_count = 0

            for cluster_info in clusters:
                if cluster_info.label == -1:
                    noise_count = cluster_info.size
                else:
                    cluster_list.append(
                        {
                            "cluster_id": cluster_info.label,
                            "label": cluster_info.label,
                            "size": cluster_info.size,
                            "avg_weight": cluster_info.avg_weight,
                        }
                    )

            # Sort by size descending
            cluster_list.sort(key=lambda x: x["size"], reverse=True)

            logger.info(
                "learning.clusters_retrieved",
                axis=axis,
                count=len(cluster_list),
                noise_count=noise_count,
            )

            return {
                "axis": axis,
                "clusters": cluster_list,
                "count": len(cluster_list),
                "noise_count": noise_count,
            }

        except (ValidationError, InsufficientDataError, NotFoundError) as e:
            logger.warning("learning.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "insufficient_data"
                if isinstance(e, InsufficientDataError)
                else "not_found"
            )
            return {"error": {"type": error_type, "message": str(e)}}
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
            cluster_id: Cluster ID (format: "cluster_{axis}_{label}")
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
            if limit < 1 or limit > 100:
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
                )

            # Query appropriate axis collection
            collection = f"ghap_{axis}"

            # Cluster label is stored in payload metadata
            results = await vector_store.scroll(
                collection=collection,
                limit=limit,
                filters={"cluster_label": label},
                with_vectors=False,
            )

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

        except (ValidationError, NotFoundError) as e:
            logger.warning("learning.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "not_found"
            )
            return {"error": {"type": error_type, "message": str(e)}}
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

            # Validate the value candidate against the cluster
            validation_result = await value_store.validate_value_candidate(
                text=text,
                cluster_id=cluster_id,
            )

            logger.info(
                "learning.value_validated",
                cluster_id=cluster_id,
                valid=validation_result.valid,
                similarity=validation_result.similarity,
            )

            return {
                "valid": validation_result.valid,
                "similarity": validation_result.similarity,
                "cluster_id": cluster_id,
            }

        except (ValidationError, NotFoundError) as e:
            logger.warning("learning.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "not_found"
            )
            return {"error": {"type": error_type, "message": str(e)}}
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

            # Store the value (validates internally)
            value_record = await value_store.store_value(
                text=text,
                cluster_id=cluster_id,
                axis=axis,
            )

            logger.info(
                "learning.value_stored",
                value_id=value_record.id,
                cluster_id=cluster_id,
                axis=axis,
            )

            return {
                "id": value_record.id,
                "text": value_record.text,
                "cluster_id": cluster_id,
                "axis": axis,
                "created_at": value_record.created_at,
            }

        except (ValidationError, NotFoundError) as e:
            logger.warning("learning.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "not_found"
            )
            return {"error": {"type": error_type, "message": str(e)}}
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
            # Validate axis if provided
            if axis is not None:
                validate_axis(axis)

            # Validate limit
            if limit < 1 or limit > 100:
                raise ValidationError(
                    f"Limit must be between 1 and 100 (got {limit})"
                )

            # Build filters
            filters = None
            if axis is not None:
                filters = {"axis": axis}

            # Query values collection
            results = await vector_store.scroll(
                collection="values",
                limit=limit,
                filters=filters,
                with_vectors=False,
            )

            # Format results
            from datetime import datetime

            values = []
            for r in results:
                validated_at = (
                    datetime.fromtimestamp(r.payload["validated_at"]).isoformat()
                    if "validated_at" in r.payload
                    else None
                )
                values.append(
                    {
                        "id": r.id,
                        "text": r.payload["text"],
                        "cluster_id": r.payload["cluster_id"],
                        "axis": r.payload["axis"],
                        "validated_at": validated_at,
                        "distance_to_centroid": r.payload.get("distance_to_centroid"),
                    }
                )

            logger.info("learning.values_listed", count=len(values), axis=axis)

            return {
                "results": values,
                "count": len(values),
            }

        except ValidationError as e:
            logger.warning("learning.validation_error", error=str(e))
            return {"error": {"type": "validation_error", "message": str(e)}}
        except Exception as e:
            logger.error(
                "learning.unexpected_error",
                tool="list_values",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    return {
        "get_clusters": get_clusters,
        "get_cluster_members": get_cluster_members,
        "validate_value": validate_value,
        "store_value": store_value,
        "list_values": list_values,
    }


def register_learning_tools(
    server: Server,
    experience_clusterer: ExperienceClusterer,
    value_store: ValueStore,
) -> None:
    """Register learning tools with MCP server.

    DEPRECATED: This function is kept for backwards compatibility with tests.
    The new dispatcher pattern uses get_learning_tools() instead.
    """
    # No-op - tools are now registered via the central dispatcher
    pass
