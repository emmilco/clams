"""Observation collection and persistence for GHAP entries."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ObservationCollector:
    """Collects and manages GHAP entries in local JSON files."""

    def __init__(self, journal_path: str) -> None:
        """Initialize the observation collector.

        Args:
            journal_path: Path to the journal directory
        """
        self.journal_path = Path(journal_path)
        self.journal_path.mkdir(parents=True, exist_ok=True)
        self.current_file = self.journal_path / "current.json"

    async def create_ghap(
        self,
        domain: str,
        strategy: str,
        goal: str,
        hypothesis: str,
        action: str,
        prediction: str,
    ) -> dict[str, Any]:
        """Create a new GHAP entry.

        Args:
            domain: Task domain
            strategy: Problem-solving strategy
            goal: What meaningful change are you trying to make?
            hypothesis: What do you believe about the situation?
            action: What are you doing based on this belief?
            prediction: If your hypothesis is correct, what will you observe?

        Returns:
            GHAP entry record
        """
        ghap_id = f"ghap_{datetime.now(UTC).timestamp()}"
        created_at = datetime.now(UTC).isoformat()

        entry = {
            "id": ghap_id,
            "domain": domain,
            "strategy": strategy,
            "goal": goal,
            "hypothesis": hypothesis,
            "action": action,
            "prediction": prediction,
            "iteration_count": 1,
            "created_at": created_at,
            "status": "active",
        }

        # Save to current.json
        with open(self.current_file, "w") as f:
            json.dump(entry, f, indent=2)

        return entry

    async def get_current(self) -> dict[str, Any] | None:
        """Get the current active GHAP entry.

        Returns:
            Current GHAP entry or None if no active entry
        """
        if not self.current_file.exists():
            return None

        with open(self.current_file) as f:
            entry: dict[str, Any] = json.load(f)

        if entry.get("status") == "active":
            return entry

        return None

    async def update_ghap(
        self,
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
            note: Additional note

        Returns:
            Updated entry with iteration count

        Raises:
            ValueError: If no active GHAP entry exists
        """
        current = await self.get_current()
        if current is None:
            raise ValueError("No active GHAP entry to update")

        # Update fields if provided
        if hypothesis is not None:
            current["hypothesis"] = hypothesis
        if action is not None:
            current["action"] = action
        if prediction is not None:
            current["prediction"] = prediction
        if strategy is not None:
            current["strategy"] = strategy

        # Increment iteration count
        current["iteration_count"] = current.get("iteration_count", 1) + 1

        # Save updated entry
        with open(self.current_file, "w") as f:
            json.dump(current, f, indent=2)

        return current

    async def resolve_ghap(
        self,
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
            surprise: What was unexpected (for falsified)
            root_cause: Why hypothesis was wrong (for falsified)
            lesson: What worked (for confirmed/falsified)

        Returns:
            Resolved GHAP entry with confidence tier

        Raises:
            ValueError: If no active GHAP entry exists
        """
        current = await self.get_current()
        if current is None:
            raise ValueError("No active GHAP entry to resolve")

        # Mark as resolved
        current["status"] = status
        current["outcome_status"] = status
        current["outcome_result"] = result
        current["resolved_at"] = datetime.now(UTC).isoformat()

        if surprise is not None:
            current["surprise"] = surprise
        if root_cause is not None:
            current["root_cause"] = root_cause
        if lesson is not None:
            current["lesson"] = lesson

        # Assign confidence tier based on status
        if status == "confirmed":
            current["confidence_tier"] = "gold"
        elif status == "falsified":
            current["confidence_tier"] = "silver"
        else:  # abandoned
            current["confidence_tier"] = "abandoned"

        # Save resolved entry
        with open(self.current_file, "w") as f:
            json.dump(current, f, indent=2)

        return current


class ObservationPersister:
    """Persists GHAP entries to vector store with embeddings."""

    def __init__(self, embedding_service: Any, vector_store: Any) -> None:
        """Initialize the observation persister.

        Args:
            embedding_service: Service for generating embeddings
            vector_store: Vector database for storage
        """
        self.embedding_service = embedding_service
        self.vector_store = vector_store

    async def persist(self, entry: dict[str, Any]) -> None:
        """Persist a resolved GHAP entry to vector store.

        Args:
            entry: Resolved GHAP entry to persist
        """
        # This is a stub - actual implementation would generate embeddings
        # and store in vector database
        pass
