"""CLAMS Configuration Module.

This module provides centralized configuration for all CLAMS components.
All settings support environment variable overrides with CLAMS_ prefix.

Consolidates scattered constants from:
- context/tokens.py: MAX_ITEM_FRACTION, SOURCE_WEIGHTS
- context/deduplication.py: SIMILARITY_THRESHOLD, MAX_FUZZY_CONTENT_LENGTH
- server/tools/validation.py: PROJECT_ID_MAX_LENGTH
- indexers/indexer.py: EMBEDDING_BATCH_SIZE
- server/tools/session.py: CLAMS_DIR, JOURNAL_DIR
- server/http.py: DEFAULT_PID_FILE, DEFAULT_LOG_FILE
- server/tools/code.py: max_length (snippet)
- server/tools/memory.py: max_length (memory content)

Usage:
    from clams.config import settings

    # Access server settings
    print(settings.server.http_port)

    # Access context settings
    print(settings.context.max_item_fraction)

    # Access tool settings
    print(settings.tools.snippet_max_length)

Reference: SPEC-029 - Create Canonical Configuration Module
"""

from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Re-export for backwards compatibility
from clams.server.config import ServerSettings

__all__ = [
    "Settings",
    "ServerSettings",
    "ContextSettings",
    "IndexerSettings",
    "ToolSettings",
    "PathSettings",
    "settings",
]


class ContextSettings(BaseSettings):
    """Configuration for context assembly and deduplication.

    These settings control how context is assembled for LLM prompts,
    including token budget distribution and deduplication behavior.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_CONTEXT__")

    # Token management (from context/tokens.py)
    max_item_fraction: float = Field(
        default=0.25,
        description="Maximum fraction of source budget any single item can consume",
    )

    # Source weights for budget distribution (from context/tokens.py)
    source_weight_memories: int = Field(
        default=1,
        description="Weight for memories in token budget distribution",
    )
    source_weight_code: int = Field(
        default=2,
        description="Weight for code in token budget distribution",
    )
    source_weight_experiences: int = Field(
        default=3,
        description="Weight for experiences (GHAP) in token budget distribution",
    )
    source_weight_values: int = Field(
        default=1,
        description="Weight for values in token budget distribution",
    )
    source_weight_commits: int = Field(
        default=2,
        description="Weight for commits in token budget distribution",
    )

    # Deduplication (from context/deduplication.py)
    similarity_threshold: float = Field(
        default=0.90,
        description="Similarity threshold for fuzzy matching (0.90 = 90%)",
    )
    max_fuzzy_content_length: int = Field(
        default=1000,
        description="Max content length for fuzzy matching (performance optimization)",
    )

    @property
    def source_weights(self) -> dict[str, int]:
        """Get source weights as a dictionary for backwards compatibility.

        Returns:
            Dictionary mapping source names to their weights
        """
        return {
            "memories": self.source_weight_memories,
            "code": self.source_weight_code,
            "experiences": self.source_weight_experiences,
            "values": self.source_weight_values,
            "commits": self.source_weight_commits,
        }


class IndexerSettings(BaseSettings):
    """Configuration for code and commit indexing.

    Controls batch sizes and other indexing parameters.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_INDEXER__")

    embedding_batch_size: int = Field(
        default=100,
        description="Number of items to embed in a single batch",
    )


class ToolSettings(BaseSettings):
    """Configuration for MCP tool parameters.

    Defines limits for tool inputs like snippet lengths and content sizes.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_TOOLS__")

    # Validation limits (from server/tools/validation.py)
    project_id_max_length: int = Field(
        default=100,
        description="Maximum length for project identifiers",
    )

    # Content length limits (from server/tools/code.py, memory.py)
    snippet_max_length: int = Field(
        default=5_000,
        description="Maximum length for code snippets in find_similar_code",
    )
    memory_content_max_length: int = Field(
        default=10_000,
        description="Maximum length for memory content in store_memory",
    )


class PathSettings(BaseSettings):
    """Configuration for file and directory paths.

    Provides Path objects for common CLAMS directories.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_PATHS__")

    clams_dir: Path = Field(
        default_factory=lambda: Path.home() / ".clams",
        description="Base directory for CLAMS data storage",
    )
    journal_dir: Path = Field(
        default_factory=lambda: Path.home() / ".clams" / "journal",
        description="Directory for session journal files",
    )


class Settings(BaseSettings):
    """Root settings class that composes all configuration sections.

    This is the main entry point for accessing CLAMS configuration.
    Use the module-level `settings` singleton for convenience.

    Example:
        from clams.config import settings

        # Access nested settings
        settings.server.http_port
        settings.context.max_item_fraction
        settings.tools.snippet_max_length
        settings.paths.clams_dir
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_")

    server: ServerSettings = Field(default_factory=ServerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    tools: ToolSettings = Field(default_factory=ToolSettings)
    paths: PathSettings = Field(default_factory=PathSettings)

    def model_post_init(self, context: Any) -> None:
        """Validate settings after initialization."""
        # Ensure context settings are valid
        if not 0.0 < self.context.max_item_fraction <= 1.0:
            raise ValueError(
                f"max_item_fraction must be between 0 and 1, "
                f"got {self.context.max_item_fraction}"
            )
        if not 0.0 < self.context.similarity_threshold <= 1.0:
            raise ValueError(
                f"similarity_threshold must be between 0 and 1, "
                f"got {self.context.similarity_threshold}"
            )


# Module-level singleton instance
settings = Settings()
