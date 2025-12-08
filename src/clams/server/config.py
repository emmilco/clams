"""Server configuration using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Configuration for the CLAMS server.

    All settings can be overridden via environment variables with CLAMS_ prefix.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_")

    # Storage paths
    storage_path: str = "~/.learning-memory"
    sqlite_path: str = "~/.learning-memory/metadata.db"
    journal_path: str = ".claude/journal"

    # Qdrant configuration
    qdrant_url: str = "http://localhost:6333"

    # Embedding configuration
    embedding_model: str = "nomic-ai/nomic-embed-text-v1.5"
    embedding_dimension: int = 768

    # Clustering configuration
    hdbscan_min_cluster_size: int = 5
    hdbscan_min_samples: int = 3

    # GHAP collection configuration
    ghap_check_frequency: int = 10

    # Git repository path (optional, auto-detected from CWD if not set)
    repo_path: str | None = None

    # Logging configuration
    log_level: str = "INFO"
    log_format: str = "json"  # "json" or "console"
