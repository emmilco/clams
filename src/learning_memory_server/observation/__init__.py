"""Observation collection module for GHAP state tracking."""

from typing import Any

from .collector import ObservationCollector
from .exceptions import (
    GHAPAlreadyActiveError,
    GHAPError,
    JournalCorruptedError,
    NoActiveGHAPError,
)
from .models import (
    ConfidenceTier,
    Domain,
    GHAPEntry,
    HistoryEntry,
    Lesson,
    Outcome,
    OutcomeStatus,
    RootCause,
    Strategy,
)


class ObservationPersister:
    """Persists GHAP entries to vector store with embeddings.

    This is a stub implementation that will be completed by SPEC-002-14.
    """

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

        Note:
            This is a stub - actual implementation in SPEC-002-14.
        """
        pass


__all__ = [
    "ObservationCollector",
    "ObservationPersister",
    "Domain",
    "Strategy",
    "OutcomeStatus",
    "ConfidenceTier",
    "RootCause",
    "Lesson",
    "HistoryEntry",
    "Outcome",
    "GHAPEntry",
    "GHAPError",
    "GHAPAlreadyActiveError",
    "NoActiveGHAPError",
    "JournalCorruptedError",
]
