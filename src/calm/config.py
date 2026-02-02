"""CALM Configuration Module.

Provides centralized configuration for all CALM components.
All settings support environment variable overrides with CALM_ prefix.
"""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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


# Module-level singleton
settings = CalmSettings()
