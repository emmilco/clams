"""Search tools for semantic experience search."""

from typing import Any

import structlog
from mcp.server import Server

from clams.search import Searcher
from clams.server.tools.enums import (
    validate_axis,
    validate_domain,
    validate_outcome_status,
)
from clams.server.tools.errors import ValidationError

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


def get_search_tools(searcher: Searcher) -> dict[str, Any]:
    """Get search tool implementations for the dispatcher.

    Args:
        searcher: Search service

    Returns:
        Dictionary mapping tool names to their implementations
    """

    async def search_experiences(
        query: str,
        axis: str = "full",
        domain: str | None = None,
        outcome: str | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:
        """Search experiences semantically across axes.

        Args:
            query: Search query
            axis: Axis to search (default: full)
            domain: Filter by domain (optional)
            outcome: Filter by outcome status (optional)
            limit: Maximum results (default 10, max 50)

        Returns:
            List of matching experiences with scores
        """
        try:
            # Handle empty query
            if not query or not query.strip():
                return {
                    "results": [],
                    "count": 0,
                }

            # Validate axis
            validate_axis(axis)

            # Validate domain if provided
            if domain is not None:
                validate_domain(domain)

            # Validate outcome if provided
            if outcome is not None:
                validate_outcome_status(outcome)

            # Validate limit
            if limit < 1 or limit > 50:
                raise ValidationError(
                    f"Limit must be between 1 and 50 (got {limit})"
                )

            # Call searcher (it generates embeddings internally)
            results = await searcher.search_experiences(
                query=query,
                axis=axis,
                domain=domain,
                outcome=outcome,
                limit=limit,
            )

            logger.info(
                "search.experiences_searched",
                query=query,
                axis=axis,
                count=len(results),
            )

            # BUG-021: Convert ExperienceResult dataclasses to dicts for JSON serialization
            formatted = [
                {
                    "id": r.id,
                    "ghap_id": r.ghap_id,
                    "axis": r.axis,
                    "domain": r.domain,
                    "strategy": r.strategy,
                    "goal": r.goal,
                    "hypothesis": r.hypothesis,
                    "action": r.action,
                    "prediction": r.prediction,
                    "outcome_status": r.outcome_status,
                    "outcome_result": r.outcome_result,
                    "surprise": r.surprise,
                    "root_cause": (
                        {
                            "category": r.root_cause.category,
                            "description": r.root_cause.description,
                        }
                        if r.root_cause
                        else None
                    ),
                    "lesson": (
                        {
                            "what_worked": r.lesson.what_worked,
                            "takeaway": r.lesson.takeaway,
                        }
                        if r.lesson
                        else None
                    ),
                    "confidence_tier": r.confidence_tier,
                    "iteration_count": r.iteration_count,
                    "score": r.score,
                    "created_at": r.created_at.isoformat(),
                }
                for r in results
            ]

            return {
                "results": formatted,
                "count": len(formatted),
            }

        except ValidationError as e:
            logger.warning("search.validation_error", error=str(e))
            return {"error": {"type": "validation_error", "message": str(e)}}
        except Exception as e:
            logger.error(
                "search.unexpected_error",
                tool="search_experiences",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    return {
        "search_experiences": search_experiences,
    }


def register_search_tools(
    server: Server,
    searcher: Searcher,
) -> None:
    """Register search tools with MCP server.

    DEPRECATED: This function is kept for backwards compatibility with tests.
    The new dispatcher pattern uses get_search_tools() instead.
    """
    # No-op - tools are now registered via the central dispatcher
    pass
