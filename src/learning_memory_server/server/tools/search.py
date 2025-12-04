"""Search tools for semantic experience search."""

from typing import Any

import structlog
from mcp.server import Server

from learning_memory_server.search import Searcher
from learning_memory_server.server.tools.enums import (
    validate_axis,
    validate_domain,
    validate_outcome_status,
)
from learning_memory_server.server.tools.errors import ValidationError

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


def register_search_tools(
    server: Server,
    searcher: Searcher,
) -> None:
    """Register search tools with MCP server.

    Args:
        server: MCP Server instance
        searcher: Search service
    """

    @server.call_tool()  # type: ignore[untyped-decorator]
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

            # This is a stub - actual implementation would:
            # 1. Generate query embedding
            # 2. Call searcher.search_experiences()
            # For now, return empty results
            results = await searcher.search_experiences(
                query_embedding=[],  # Mock embedding
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

            return {
                "results": results,
                "count": len(results),
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
