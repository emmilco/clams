"""Persister for resolved GHAP entries with multi-axis embeddings."""

import re
from typing import Any

import structlog

from ..embedding.base import EmbeddingService
from ..storage.base import VectorStore
from .models import GHAPEntry, OutcomeStatus

# Template definitions for each axis
TEMPLATE_FULL = """Goal: {goal}
Hypothesis: {hypothesis}
Action: {action}
Prediction: {prediction}
Outcome: {outcome_status} - {outcome_result}
[Surprise: {surprise}]
[Lesson: {lesson_what_worked}]"""

TEMPLATE_STRATEGY = """Strategy: {strategy}
Applied to: {goal}
Outcome: {outcome_status} after {iteration_count} iteration(s)
[What worked: {lesson_what_worked}]"""

TEMPLATE_SURPRISE = """Expected: {prediction}
Actual: {outcome_result}
Surprise: {surprise}
Root cause: {root_cause_category} - {root_cause_description}"""

TEMPLATE_ROOT_CAUSE = """Category: {root_cause_category}
Description: {root_cause_description}
Context: {domain} - {strategy}
Original hypothesis: {hypothesis}"""


class ObservationPersister:
    """Persists resolved GHAP entries to vector store with multi-axis embeddings."""

    def __init__(
        self,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
        collection_prefix: str = "ghap",
    ) -> None:
        """Initialize the persister.

        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector database for storage
            collection_prefix: Prefix for collection names (default: "ghap")
        """
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._collection_prefix = collection_prefix
        self._logger = structlog.get_logger(__name__)

    async def persist(self, entry: GHAPEntry) -> None:
        """Persist a single resolved GHAP entry.

        Creates embeddings for all applicable axes and stores them.

        Args:
            entry: Resolved GHAP entry to persist

        Raises:
            ValueError: If entry is not resolved (no outcome)
        """
        # 1. Validation
        if entry.outcome is None:
            raise ValueError("Entry must be resolved (outcome must be set)")

        # 2. Extract metadata (shared across all axes)
        metadata = self._build_metadata(entry)

        # 3. Determine which axes to embed
        axes_to_embed = self._determine_axes(entry)

        # 4. For each axis: render template, embed, upsert
        for axis, template in axes_to_embed.items():
            # Render text
            text = self._render_template(template, entry)

            # Generate embedding
            vector = await self._embedding_service.embed(text)

            # Build axis-specific metadata (may add fields like root_cause_category)
            axis_metadata = self._build_axis_metadata(entry, axis, metadata)

            # Store in collection
            collection_name = f"{self._collection_prefix}_{axis}"
            await self._vector_store.upsert(
                collection=collection_name,
                id=entry.id,  # Same ID across all axes for cross-referencing
                vector=vector,
                payload=axis_metadata,
            )

            self._logger.info(
                "axis_persisted",
                ghap_id=entry.id,
                axis=axis,
                collection=collection_name,
            )

    async def persist_batch(self, entries: list[GHAPEntry]) -> None:
        """Persist multiple resolved GHAP entries.

        Args:
            entries: List of resolved entries to persist

        Raises:
            ValueError: If any entry is not resolved
        """
        # 1. Validate all entries have outcomes
        for entry in entries:
            if entry.outcome is None:
                raise ValueError(
                    f"Entry {entry.id} must be resolved (outcome must be set)"
                )

        # 2. Process entries sequentially
        for entry in entries:
            await self.persist(entry)

        self._logger.info("batch_persisted", count=len(entries))

    async def ensure_collections(self) -> None:
        """Ensure all axis collections exist.

        Creates collections if they don't exist. Safe to call multiple times.

        Note: VectorStore.create_collection() raises ValueError if collection
        already exists (InMemoryVectorStore). QdrantVectorStore raises
        UnexpectedResponse with status 409. Both cases are handled here.
        """
        axes = ["full", "strategy", "surprise", "root_cause"]
        dimension = self._embedding_service.dimension  # 768 for Nomic

        for axis in axes:
            collection_name = f"{self._collection_prefix}_{axis}"
            try:
                await self._vector_store.create_collection(
                    name=collection_name,
                    dimension=dimension,
                    distance="cosine",
                )
                self._logger.info(
                    "collection_created",
                    collection=collection_name,
                    dimension=dimension,
                )
            except Exception as e:
                # Collection already exists - this is expected and safe
                # InMemoryVectorStore raises ValueError
                # QdrantVectorStore raises UnexpectedResponse with 409
                error_msg = str(e).lower()
                if "already exists" in error_msg or "409" in str(e):
                    self._logger.debug(
                        "collection_already_exists",
                        collection=collection_name,
                        error=str(e),
                    )
                else:
                    raise

    def _render_template(self, template: str, entry: GHAPEntry) -> str:
        """Render a template with optional fields.

        Templates contain:
        - {field_name} for required fields
        - [text with {field_name}] for optional fields

        Optional sections are removed if the field is None or empty.

        Limitations:
        - Does not support nested brackets (e.g., [[inner]]).
        - Nested brackets will fail gracefully by not matching the pattern.
        - Current templates don't require nesting, so this is acceptable.

        Args:
            template: Template string with {field} and [optional {field}] syntax
            entry: GHAPEntry to extract fields from

        Returns:
            Rendered text string

        Raises:
            ValueError: If a required field is missing
        """
        # Extract all fields for this entry
        fields = self._extract_fields(entry)

        # Step 1: Extract optional sections (marked with [brackets])
        # Pattern: [any text with {field_name} placeholders]
        optional_pattern = re.compile(r"\[([^\[\]]+)\]")

        def process_optional(match: re.Match[str]) -> str:
            section = match.group(1)

            # Extract field names from this section using {field_name} pattern
            field_pattern = re.compile(r"\{(\w+)\}")
            field_names = field_pattern.findall(section)

            # Check if all fields exist and are non-None/non-empty
            for field_name in field_names:
                if field_name not in fields or not fields[field_name]:
                    # Field is missing or empty, remove entire section
                    return ""

            # All fields present, render the section (without brackets)
            return section

        # Step 2: Process all optional sections
        rendered = optional_pattern.sub(process_optional, template)

        # Step 3: Render remaining template with all required fields
        # Use str.format() to replace {field_name} placeholders
        try:
            return rendered.format(**fields)
        except KeyError as e:
            # Missing required field
            raise ValueError(f"Template rendering failed: missing field {e}")

    def _extract_fields(self, entry: GHAPEntry) -> dict[str, str]:
        """Extract all fields from entry for template rendering.

        Args:
            entry: GHAPEntry to extract fields from

        Returns:
            Dictionary mapping field names to string values
        """
        fields = {
            "goal": entry.goal,
            "hypothesis": entry.hypothesis,
            "action": entry.action,
            "prediction": entry.prediction,
            # domain and strategy are non-Optional fields in GHAPEntry model,
            # so .value access is safe (no None check needed)
            "domain": entry.domain.value,
            "strategy": entry.strategy.value,
            "iteration_count": str(entry.iteration_count),
            "outcome_status": entry.outcome.status.value,  # type: ignore[union-attr]
            "outcome_result": entry.outcome.result,  # type: ignore[union-attr]
        }

        # Optional fields
        if entry.surprise:
            fields["surprise"] = entry.surprise
        if entry.lesson:
            if entry.lesson.what_worked:
                fields["lesson_what_worked"] = entry.lesson.what_worked
            if entry.lesson.takeaway:
                fields["lesson_takeaway"] = entry.lesson.takeaway
        if entry.root_cause:
            fields["root_cause_category"] = entry.root_cause.category
            fields["root_cause_description"] = entry.root_cause.description

        return fields

    def _determine_axes(self, entry: GHAPEntry) -> dict[str, str]:
        """Determine which axes to embed based on entry state.

        Edge case handling:
        - If root_cause exists but surprise is None, skip both surprise and
          root_cause axes (root_cause axis template requires surprise text).
          This is logged as a warning since it indicates incomplete data.

        Args:
            entry: GHAPEntry to determine axes for

        Returns:
            Dictionary mapping axis names to template strings
        """
        axes = {
            "full": TEMPLATE_FULL,
            "strategy": TEMPLATE_STRATEGY,
        }

        # Only add surprise and root_cause axes for falsified entries
        if entry.outcome and entry.outcome.status == OutcomeStatus.FALSIFIED:
            if entry.surprise:  # Must have surprise text
                axes["surprise"] = TEMPLATE_SURPRISE
                if entry.root_cause:  # Must have root_cause object
                    axes["root_cause"] = TEMPLATE_ROOT_CAUSE
            elif entry.root_cause:
                # Root cause exists but no surprise text - skip both axes
                # This is a data quality issue that should be logged
                self._logger.warning(
                    "root_cause_without_surprise",
                    ghap_id=entry.id,
                    note="Skipping root_cause axis (requires surprise text)",
                )

        return axes

    def _build_metadata(self, entry: GHAPEntry) -> dict[str, Any]:
        """Build base metadata payload (shared across all axes).

        Args:
            entry: GHAPEntry to extract metadata from

        Returns:
            Dictionary of metadata fields
        """
        return {
            "ghap_id": entry.id,
            "session_id": entry.session_id,
            # Store created_at as ISO format string for datetime.fromisoformat()
            "created_at": entry.created_at.isoformat(),
            "captured_at": entry.outcome.captured_at.timestamp(),  # type: ignore[union-attr]
            "domain": entry.domain.value,
            "strategy": entry.strategy.value,
            "outcome_status": entry.outcome.status.value,  # type: ignore[union-attr]
            "confidence_tier": entry.confidence_tier.value
            if entry.confidence_tier
            else None,
            "iteration_count": entry.iteration_count,
        }

    def _build_axis_metadata(
        self, entry: GHAPEntry, axis: str, base_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Add axis-specific metadata fields.

        Args:
            entry: GHAPEntry to extract metadata from
            axis: Axis name (full, strategy, surprise, root_cause)
            base_metadata: Base metadata dictionary to extend

        Returns:
            Metadata dictionary with axis-specific fields added
        """
        metadata = base_metadata.copy()

        # Add axis identifier
        metadata["axis"] = axis

        # Add GHAP content fields (required by ExperienceResult.from_search_result)
        metadata["goal"] = entry.goal
        metadata["hypothesis"] = entry.hypothesis
        metadata["action"] = entry.action
        metadata["prediction"] = entry.prediction
        metadata["outcome_result"] = entry.outcome.result  # type: ignore[union-attr]

        # Add optional fields (if present)
        if entry.surprise:
            metadata["surprise"] = entry.surprise

        if entry.root_cause:
            # Store as dict for nested dataclass reconstruction
            metadata["root_cause"] = {
                "category": entry.root_cause.category,
                "description": entry.root_cause.description,
            }

        if entry.lesson:
            # Store as dict for nested dataclass reconstruction
            metadata["lesson"] = {
                "what_worked": entry.lesson.what_worked,
                "takeaway": entry.lesson.takeaway,
            }

        return metadata
