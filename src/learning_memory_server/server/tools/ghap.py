"""GHAP tracking tools for MCP server."""

import asyncio
from datetime import datetime
from typing import Any

import structlog
from mcp.server import Server

from learning_memory_server.observation import (
    Domain,
    Lesson,
    ObservationCollector,
    ObservationPersister,
    OutcomeStatus,
    RootCause,
    Strategy,
)
from learning_memory_server.server.tools.enums import (
    validate_domain,
    validate_outcome_status,
    validate_root_cause_category,
    validate_strategy,
)
from learning_memory_server.server.tools.errors import (
    MCPError,
    NotFoundError,
    ValidationError,
)

logger = structlog.get_logger()


def _error_response(error_type: str, message: str) -> dict[str, Any]:
    """Create a standardized error response.

    Args:
        error_type: Type of error (validation_error, not_found, internal_error)
        message: Error message

    Returns:
        Error response dict
    """
    return {"error": {"type": error_type, "message": message}}


def register_ghap_tools(
    server: Server,
    collector: ObservationCollector,
    persister: ObservationPersister,
) -> None:
    """Register GHAP tools with MCP server.

    Args:
        server: MCP Server instance
        collector: Observation collector service
        persister: Observation persister service
    """
    # Access vector store from persister for list_ghap_entries
    vector_store = persister._vector_store

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def start_ghap(
        domain: str,
        strategy: str,
        goal: str,
        hypothesis: str,
        action: str,
        prediction: str,
    ) -> dict[str, Any]:
        """Begin tracking a new GHAP entry.

        Args:
            domain: Task domain (debugging, refactoring, feature, etc.)
            strategy: Problem-solving strategy
            goal: What meaningful change are you trying to make?
            hypothesis: What do you believe about the situation?
            action: What are you doing based on this belief?
            prediction: If your hypothesis is correct, what will you observe?

        Returns:
            GHAP entry record with id and timestamp
        """
        try:
            # Validate domain
            validate_domain(domain)

            # Validate strategy
            validate_strategy(strategy)

            # Validate text lengths
            for field, value in [
                ("goal", goal),
                ("hypothesis", hypothesis),
                ("action", action),
                ("prediction", prediction),
            ]:
                if not value or not value.strip():
                    raise ValidationError(f"Field '{field}' cannot be empty")
                if len(value) > 1000:
                    raise ValidationError(
                        f"Field '{field}' exceeds 1000 character limit "
                        f"({len(value)} chars)"
                    )

            # Check for active GHAP (warn but allow)
            current = await collector.get_current()
            if current is not None:
                logger.warning(
                    "ghap.orphaned_entry",
                    current_id=current.id,
                    message=(
                        "Starting new GHAP with active entry - "
                        "previous entry orphaned"
                    ),
                )

            # Create GHAP entry (convert strings to enums)
            entry = await collector.create_ghap(
                domain=Domain(domain),
                strategy=Strategy(strategy),
                goal=goal,
                hypothesis=hypothesis,
                action=action,
                prediction=prediction,
            )

            logger.info(
                "ghap.started",
                ghap_id=entry.id,
                domain=domain,
                strategy=strategy,
            )

            return {
                "id": entry.id,
                "domain": entry.domain.value,
                "strategy": entry.strategy.value,
                "goal": entry.goal,
                "hypothesis": entry.hypothesis,
                "action": entry.action,
                "prediction": entry.prediction,
                "created_at": entry.created_at.isoformat(),
            }

        except ValidationError as e:
            logger.warning("ghap.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "ghap.unexpected_error",
                tool="start_ghap",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def update_ghap(
        hypothesis: str | None = None,
        action: str | None = None,
        prediction: str | None = None,
        strategy: str | None = None,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Update the current GHAP entry.

        Args:
            hypothesis: Updated hypothesis
            action: Updated action
            prediction: Updated prediction
            strategy: Updated strategy
            note: Additional note (for history tracking)

        Returns:
            Success status and iteration count
        """
        try:
            # Validate strategy if provided
            if strategy is not None:
                validate_strategy(strategy)

            # Validate text lengths
            for field, value in [
                ("hypothesis", hypothesis),
                ("action", action),
                ("prediction", prediction),
            ]:
                if value is not None and len(value) > 1000:
                    raise ValidationError(
                        f"Field '{field}' exceeds 1000 character limit "
                        f"({len(value)} chars)"
                    )

            # Check if there's an active GHAP entry
            current = await collector.get_current()
            if current is None:
                raise NotFoundError(
                    "No active GHAP entry to update. Use start_ghap to begin tracking."
                )

            # Update GHAP entry (convert strategy string to enum if provided)
            updated = await collector.update_ghap(
                hypothesis=hypothesis,
                action=action,
                prediction=prediction,
                strategy=Strategy(strategy) if strategy else None,
                note=note,
            )

            logger.info(
                "ghap.updated",
                ghap_id=updated.id,
                iteration_count=updated.iteration_count,
            )

            return {
                "success": True,
                "iteration_count": updated.iteration_count,
            }

        except (ValidationError, NotFoundError) as e:
            logger.warning("ghap.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "not_found"
            )
            return _error_response(error_type, str(e))
        except Exception as e:
            logger.error(
                "ghap.unexpected_error",
                tool="update_ghap",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def resolve_ghap(
        status: str,
        result: str,
        surprise: str | None = None,
        root_cause: dict[str, str] | None = None,
        lesson: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        """Mark the current GHAP entry as resolved.

        Args:
            status: Resolution status (confirmed, falsified, abandoned)
            result: What actually happened
            surprise: What was unexpected (required for falsified)
            root_cause: Why hypothesis was wrong (required for falsified)
            lesson: What worked (recommended for confirmed/falsified)

        Returns:
            Resolved GHAP entry with id, status, confidence tier, and timestamp
        """
        try:
            # Validate status
            validate_outcome_status(status)

            # Validate text lengths
            if len(result) > 2000:
                raise ValidationError(
                    f"Field 'result' exceeds 2000 character limit ({len(result)} chars)"
                )

            if surprise is not None and len(surprise) > 2000:
                raise ValidationError(
                    f"Field 'surprise' exceeds 2000 character limit "
                    f"({len(surprise)} chars)"
                )

            # Validate falsified requirements
            if status == "falsified":
                if surprise is None or not surprise.strip():
                    raise ValidationError(
                        "Field 'surprise' is required when status is 'falsified'"
                    )
                if root_cause is None:
                    raise ValidationError(
                        "Field 'root_cause' is required when status is 'falsified'"
                    )

                # Validate root_cause structure
                if not isinstance(root_cause, dict):
                    raise ValidationError(
                        "Field 'root_cause' must be a dict with "
                        "'category' and 'description'"
                    )

                category = root_cause.get("category")
                description = root_cause.get("description")

                if not category:
                    raise ValidationError(
                        "Field 'root_cause.category' is required"
                    )
                if not description:
                    raise ValidationError(
                        "Field 'root_cause.description' is required"
                    )

                validate_root_cause_category(category)

                if len(description) > 2000:
                    raise ValidationError(
                        f"Field 'root_cause.description' exceeds 2000 character limit "
                        f"({len(description)} chars)"
                    )

            # Validate lesson structure if provided
            if lesson is not None:
                if not isinstance(lesson, dict):
                    raise ValidationError(
                        "Field 'lesson' must be a dict with 'what_worked' "
                        "and optional 'takeaway'"
                    )

                what_worked = lesson.get("what_worked")
                if not what_worked:
                    raise ValidationError(
                        "Field 'lesson.what_worked' is required when lesson is provided"
                    )

                if len(what_worked) > 2000:
                    raise ValidationError(
                        f"Field 'lesson.what_worked' exceeds 2000 character limit "
                        f"({len(what_worked)} chars)"
                    )

                takeaway = lesson.get("takeaway")
                if takeaway is not None and len(takeaway) > 2000:
                    raise ValidationError(
                        f"Field 'lesson.takeaway' exceeds 2000 character limit "
                        f"({len(takeaway)} chars)"
                    )

            # Check if there's an active GHAP entry
            current = await collector.get_current()
            if current is None:
                raise NotFoundError("No active GHAP entry to resolve")

            # Convert root_cause dict to RootCause model if provided
            root_cause_model = None
            if root_cause:
                root_cause_model = RootCause(
                    category=root_cause["category"],
                    description=root_cause["description"],
                )

            # Convert lesson dict to Lesson model if provided
            lesson_model = None
            if lesson:
                # Validation above ensures what_worked exists and is non-empty
                lesson_model = Lesson(
                    what_worked=lesson["what_worked"],  # type: ignore[arg-type]
                    takeaway=lesson.get("takeaway"),
                )

            # Mark resolved locally (always succeeds)
            resolved = await collector.resolve_ghap(
                status=OutcomeStatus(status),
                result=result,
                surprise=surprise,
                root_cause=root_cause_model,
                lesson=lesson_model,
            )

            # Persist to VectorStore with retry
            max_retries = 3
            backoff = 1.0  # seconds

            for attempt in range(max_retries):
                try:
                    await persister.persist(resolved)
                    logger.info(
                        "ghap.persisted",
                        ghap_id=resolved.id,
                        attempt=attempt + 1,
                    )
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        logger.warning(
                            "ghap.persist_retry",
                            ghap_id=resolved.id,
                            attempt=attempt + 1,
                            backoff_seconds=backoff,
                            error=str(e),
                        )
                        await asyncio.sleep(backoff)
                        backoff *= 2  # Exponential backoff: 1s, 2s, 4s
                    else:
                        # Final attempt failed
                        logger.error(
                            "ghap.persist_failed",
                            ghap_id=resolved.id,
                            attempts=max_retries,
                            error=str(e),
                        )
                        raise MCPError(
                            f"Failed to persist GHAP entry after "
                            f"{max_retries} attempts. Local resolution saved, "
                            f"but embedding/storage failed. Error: {e}"
                        )

            confidence_tier_value = (
                resolved.confidence_tier.value if resolved.confidence_tier else None
            )
            resolved_at_value = (
                resolved.outcome.captured_at.isoformat() if resolved.outcome else None
            )
            return {
                "id": resolved.id,
                "status": resolved.outcome.status.value if resolved.outcome else status,
                "confidence_tier": confidence_tier_value,
                "resolved_at": resolved_at_value,
            }

        except (ValidationError, NotFoundError) as e:
            logger.warning("ghap.error", error=str(e))
            error_type = (
                "validation_error"
                if isinstance(e, ValidationError)
                else "not_found"
            )
            return _error_response(error_type, str(e))
        except Exception as e:
            logger.error(
                "ghap.unexpected_error",
                tool="resolve_ghap",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def get_active_ghap() -> dict[str, Any]:
        """Get the current active GHAP entry.

        Returns:
            Current GHAP entry or empty dict if no active entry
        """
        try:
            current = await collector.get_current()

            if current is None:
                return {
                    "id": None,
                    "domain": None,
                    "strategy": None,
                    "goal": None,
                    "hypothesis": None,
                    "action": None,
                    "prediction": None,
                    "iteration_count": None,
                    "created_at": None,
                    "has_active": False,
                }

            return {
                "id": current.id,
                "domain": current.domain.value,
                "strategy": current.strategy.value,
                "goal": current.goal,
                "hypothesis": current.hypothesis,
                "action": current.action,
                "prediction": current.prediction,
                "iteration_count": current.iteration_count,
                "created_at": current.created_at.isoformat(),
                "has_active": True,
            }

        except Exception as e:
            logger.error(
                "ghap.unexpected_error",
                tool="get_active_ghap",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def list_ghap_entries(
        limit: int = 20,
        domain: str | None = None,
        outcome: str | None = None,
        since: str | None = None,
    ) -> dict[str, Any]:
        """List recent GHAP entries with filters.

        Args:
            limit: Maximum results (default 20, max 100)
            domain: Filter by domain
            outcome: Filter by outcome status
            since: Filter by creation date (ISO 8601 format)

        Returns:
            List of GHAP entries matching filters
        """
        try:
            # Validate limit
            if limit < 1 or limit > 100:
                raise ValidationError(
                    f"Limit must be between 1 and 100 (got {limit})"
                )

            # Validate domain if provided
            if domain is not None:
                validate_domain(domain)

            # Validate outcome if provided
            if outcome is not None:
                validate_outcome_status(outcome)

            # Validate since date if provided
            since_dt = None
            if since is not None:
                try:
                    since_dt = datetime.fromisoformat(since)
                except ValueError:
                    raise ValidationError(
                        f"Invalid date format for 'since': {since}. "
                        "Expected ISO 8601 format (e.g., '2024-01-15T10:30:45+00:00')"
                    )

            # Build filters
            filters: dict[str, Any] = {}
            if domain is not None:
                filters["domain"] = domain
            if outcome is not None:
                filters["outcome_status"] = outcome
            if since_dt is not None:
                filters["captured_at"] = {"$gte": since_dt.timestamp()}

            # Query ghap_full collection
            results = await vector_store.scroll(
                collection="ghap_full",
                limit=limit,
                filters=filters if filters else None,
                with_vectors=False,  # Don't need embeddings for listing
            )

            # Format results
            entries = []
            for r in results:
                created_at = (
                    datetime.fromtimestamp(r.payload["created_at"]).isoformat()
                    if "created_at" in r.payload
                    else None
                )
                captured_at = (
                    datetime.fromtimestamp(r.payload["captured_at"]).isoformat()
                    if "captured_at" in r.payload
                    else None
                )
                entries.append(
                    {
                        "id": r.id,
                        "domain": r.payload.get("domain"),
                        "strategy": r.payload.get("strategy"),
                        "outcome_status": r.payload.get("outcome_status"),
                        "confidence_tier": r.payload.get("confidence_tier"),
                        "iteration_count": r.payload.get("iteration_count"),
                        "created_at": created_at,
                        "captured_at": captured_at,
                    }
                )

            logger.info("ghap.entries_listed", count=len(entries), filters=filters)

            return {
                "results": entries,
                "count": len(entries),
            }

        except ValidationError as e:
            logger.warning("ghap.validation_error", error=str(e))
            return _error_response("validation_error", str(e))
        except Exception as e:
            logger.error(
                "ghap.unexpected_error",
                tool="list_ghap_entries",
                error=str(e),
                exc_info=True,
            )
            return _error_response("internal_error", "Internal server error")
