"""CALM Configuration Module.

Provides centralized configuration for all CALM components.
All settings support environment variable overrides with CALM_ prefix.
"""

from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class IndexerSettings(BaseModel):
    """Settings for code indexing."""

    embedding_batch_size: int = Field(
        default=100,
        description="Number of embeddings to generate per batch",
    )


class ContextSettings(BaseModel):
    """Settings for context assembly."""

    source_weights: dict[str, int] = Field(
        default={
            "memories": 1,
            "code": 2,
            "experiences": 3,
            "values": 1,
            "commits": 2,
        },
        description="Token budget weights per source type",
    )
    similarity_threshold: float = Field(
        default=0.90,
        description="Minimum similarity for fuzzy deduplication",
    )
    max_item_fraction: float = Field(
        default=0.25,
        description="Max fraction of source budget for a single item",
    )
    max_fuzzy_content_length: int = Field(
        default=1000,
        description="Max content length for fuzzy deduplication",
    )


class ToolSettings(BaseModel):
    """Settings for tool constraints."""

    snippet_max_length: int = Field(
        default=5000,
        description="Maximum code snippet length for find_similar_code",
    )

# Default paths
CALM_HOME = Path.home() / ".calm"
CALM_DB = CALM_HOME / "metadata.db"
CALM_CONFIG = CALM_HOME / "config.yaml"

# Default config.yaml content
DEFAULT_CONFIG = """\
# CALM Configuration
# See https://github.com/anthropics/calm for documentation

# Server settings
server:
  host: 127.0.0.1
  port: 6335
  log_level: info

# Embedding settings
embedding:
  code_model: sentence-transformers/all-MiniLM-L6-v2
  semantic_model: nomic-ai/nomic-embed-text-v1.5

# Qdrant settings
qdrant:
  url: http://localhost:6333
"""


class CalmSettings(BaseSettings):
    """CALM server configuration.

    All settings can be overridden via environment variables with CALM_ prefix.
    For example, CALM_SERVER_PORT=8080 sets server_port to 8080.
    """

    model_config = SettingsConfigDict(
        env_prefix="CALM_",
        env_nested_delimiter="__",
    )

    # Paths
    home: Path = Field(
        default=CALM_HOME,
        description="Base directory for CALM data storage",
    )
    db_path: Path = Field(
        default=CALM_DB,
        description="Path to SQLite metadata database",
    )

    # Server settings
    server_host: str = Field(
        default="127.0.0.1",
        description="HTTP server host",
    )
    server_port: int = Field(
        default=6335,
        description="HTTP server port",
    )
    log_level: str = Field(
        default="info",
        description="Logging level (debug, info, warning, error)",
    )

    # PID and log files
    pid_file: Path = Field(
        default_factory=lambda: CALM_HOME / "server.pid",
        description="Path to server PID file",
    )
    log_file: Path = Field(
        default_factory=lambda: CALM_HOME / "server.log",
        description="Path to server log file",
    )

    # Qdrant settings
    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="Qdrant vector database URL",
    )

    # Embedding model settings
    code_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Model for code embeddings",
    )
    semantic_model: str = Field(
        default="nomic-ai/nomic-embed-text-v1.5",
        description="Model for semantic embeddings",
    )

    @property
    def workflows_dir(self) -> Path:
        """Directory for workflow definitions."""
        return self.home / "workflows"

    @property
    def roles_dir(self) -> Path:
        """Directory for role files."""
        return self.home / "roles"

    @property
    def sessions_dir(self) -> Path:
        """Directory for session logs."""
        return self.home / "sessions"

    @property
    def calm_dir(self) -> Path:
        """Alias for home directory (for compatibility)."""
        return self.home

    @property
    def journal_dir(self) -> Path:
        """Directory for GHAP journal files."""
        return self.home / "journal"

    @property
    def skills_dir(self) -> Path:
        """Directory for skill templates."""
        return self.home / "skills"

    # Memory tool settings
    memory_content_max_length: int = Field(
        default=10000,
        description="Maximum length for memory content",
    )

    # Nested settings
    indexer: IndexerSettings = Field(default_factory=IndexerSettings)
    context: ContextSettings = Field(default_factory=ContextSettings)
    tool: ToolSettings = Field(default_factory=ToolSettings)


# Module-level singleton
settings = CalmSettings()
