"""Server configuration using pydantic-settings.

This module provides the canonical source for all CLAMS configuration values.
Configuration can be overridden via environment variables with CLAMS_ prefix.

Reference: BUG-033 (server command issues), BUG-037 (timeout issues)
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Configuration for the CLAMS server.

    All settings can be overridden via environment variables with CLAMS_ prefix.
    For example, CLAMS_LOG_LEVEL=DEBUG will override the log_level setting.

    This class is the canonical source for all configuration values used by
    both the Python server and shell hooks. Use export_for_shell() to generate
    a shell-sourceable config file.
    """

    model_config = SettingsConfigDict(env_prefix="CLAMS_")

    # =========================================================================
    # Storage paths
    # =========================================================================

    storage_path: str = Field(
        default="~/.clams",
        description="Base directory for CLAMS data storage",
    )

    sqlite_path: str = Field(
        default="~/.clams/metadata.db",
        description="Path to SQLite metadata database",
    )

    journal_path: str = Field(
        default=".claude/journal",
        description="Path to journal directory for session tracking",
    )

    # =========================================================================
    # Server configuration
    # =========================================================================

    server_command: str = Field(
        default=".venv/bin/clams-server",
        description=(
            "Command to start the CLAMS server. This should be the path to "
            "the installed clams-server binary. The path is relative to the "
            "repository root. See BUG-033 for why this must use the venv binary."
        ),
    )

    http_host: str = Field(
        default="127.0.0.1",
        description="Host address for HTTP server mode",
    )

    http_port: int = Field(
        default=6334,
        description="Port for HTTP server mode (used by hooks)",
    )

    pid_file: str = Field(
        default="~/.clams/server.pid",
        description="Path to server PID file for daemon management",
    )

    log_file: str = Field(
        default="~/.clams/server.log",
        description="Path to server log file for daemon mode",
    )

    # =========================================================================
    # Timeout configuration
    # =========================================================================

    verification_timeout: int = Field(
        default=15,
        description=(
            "Timeout in seconds for server verification during installation. "
            "Must account for heavy imports like PyTorch. See BUG-037."
        ),
    )

    http_call_timeout: int = Field(
        default=5,
        description="Timeout in seconds for HTTP calls from hooks to server",
    )

    qdrant_timeout: float = Field(
        default=5.0,
        description="Timeout in seconds for Qdrant operations",
    )

    # =========================================================================
    # Qdrant configuration
    # =========================================================================

    qdrant_url: str = Field(
        default="http://localhost:6333",
        description="URL for Qdrant vector database",
    )

    # =========================================================================
    # Embedding configuration
    # =========================================================================

    embedding_model: str = Field(
        default="nomic-ai/nomic-embed-text-v1.5",
        description="Default embedding model for semantic search",
    )

    embedding_dimension: int = Field(
        default=768,
        description="Dimension of embedding vectors",
    )

    code_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Embedding model optimized for code search",
    )

    semantic_model: str = Field(
        default="nomic-ai/nomic-embed-text-v1.5",
        description="Embedding model for semantic/natural language search",
    )

    # =========================================================================
    # Clustering configuration (HDBSCAN)
    # =========================================================================

    hdbscan_min_cluster_size: int = Field(
        default=5,
        description=(
            "Minimum cluster size for HDBSCAN clustering. "
            "Higher values produce fewer, larger clusters."
        ),
    )

    hdbscan_min_samples: int = Field(
        default=3,
        description=(
            "Minimum samples for HDBSCAN core points. "
            "Higher values make clustering more conservative."
        ),
    )

    # =========================================================================
    # GHAP configuration
    # =========================================================================

    ghap_check_frequency: int = Field(
        default=10,
        description="Number of tool calls between GHAP check-in reminders",
    )

    # =========================================================================
    # Git configuration
    # =========================================================================

    repo_path: str | None = Field(
        default=None,
        description=(
            "Git repository path. Optional - auto-detected from CWD if not set."
        ),
    )

    # =========================================================================
    # Logging configuration
    # =========================================================================

    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
    )

    log_format: str = Field(
        default="json",
        description=(
            'Logging format: "json" for structured logs, '
            '"console" for human-readable'
        ),
    )

    # =========================================================================
    # Methods
    # =========================================================================

    def export_for_shell(self, path: Path | str) -> None:
        """Export configuration as a shell-sourceable file.

        Creates a file that can be sourced by bash scripts to access
        configuration values as environment variables. Paths containing
        ~ are expanded to absolute paths.

        Args:
            path: Path to write the config file (e.g., ~/.clams/config.env)

        Example:
            >>> settings = ServerSettings()
            >>> settings.export_for_shell(Path.home() / ".clams" / "config.env")

            Then in bash:
            >>> source ~/.clams/config.env
            >>> echo $CLAMS_SERVER_COMMAND
            .venv/bin/clams-server
        """
        # Import here to avoid circular dependency
        from clams.search.collections import CollectionName

        if isinstance(path, str):
            path = Path(path)

        # Ensure parent directory exists
        path.parent.mkdir(parents=True, exist_ok=True)

        lines = [
            "# CLAMS Configuration (auto-generated)",
            "# Source this file in shell scripts: source ~/.clams/config.env",
            "",
            "# Server configuration",
            f"CLAMS_SERVER_COMMAND={self.server_command}",
            f"CLAMS_HTTP_HOST={self.http_host}",
            f"CLAMS_HTTP_PORT={self.http_port}",
            f"CLAMS_PID_FILE={Path(self.pid_file).expanduser()}",
            f"CLAMS_LOG_FILE={Path(self.log_file).expanduser()}",
            "",
            "# Timeouts (seconds)",
            f"CLAMS_VERIFICATION_TIMEOUT={self.verification_timeout}",
            f"CLAMS_HTTP_CALL_TIMEOUT={self.http_call_timeout}",
            f"CLAMS_QDRANT_TIMEOUT={self.qdrant_timeout}",
            "",
            "# Storage paths (expanded)",
            f"CLAMS_STORAGE_PATH={Path(self.storage_path).expanduser()}",
            f"CLAMS_SQLITE_PATH={Path(self.sqlite_path).expanduser()}",
            f"CLAMS_JOURNAL_PATH={self.journal_path}",
            "",
            "# Qdrant configuration",
            f"CLAMS_QDRANT_URL={self.qdrant_url}",
            "",
            "# Collection names (from CollectionName class)",
            f"CLAMS_COLLECTION_MEMORIES={CollectionName.MEMORIES}",
            f"CLAMS_COLLECTION_CODE={CollectionName.CODE}",
            f"CLAMS_COLLECTION_COMMITS={CollectionName.COMMITS}",
            f"CLAMS_COLLECTION_VALUES={CollectionName.VALUES}",
            f"CLAMS_COLLECTION_GHAP_FULL={CollectionName.EXPERIENCES_FULL}",
            f"CLAMS_COLLECTION_GHAP_STRATEGY={CollectionName.EXPERIENCES_STRATEGY}",
            f"CLAMS_COLLECTION_GHAP_SURPRISE={CollectionName.EXPERIENCES_SURPRISE}",
            f"CLAMS_COLLECTION_GHAP_ROOT_CAUSE={CollectionName.EXPERIENCES_ROOT_CAUSE}",
            "",
            "# Clustering configuration",
            f"CLAMS_HDBSCAN_MIN_CLUSTER_SIZE={self.hdbscan_min_cluster_size}",
            f"CLAMS_HDBSCAN_MIN_SAMPLES={self.hdbscan_min_samples}",
            "",
            "# GHAP configuration",
            f"CLAMS_GHAP_CHECK_FREQUENCY={self.ghap_check_frequency}",
            "",
            "# Logging configuration",
            f"CLAMS_LOG_LEVEL={self.log_level}",
            f"CLAMS_LOG_FORMAT={self.log_format}",
            "",
        ]

        with open(path, "w") as f:
            f.write("\n".join(lines))

    def get_config_env_path(self) -> Path:
        """Get the default path for the config.env file.

        Returns:
            Path to ~/.clams/config.env
        """
        return Path(self.storage_path).expanduser() / "config.env"
