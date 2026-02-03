"""CALM Install Module.

Provides installation functionality for fresh CALM installations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Literal


class InstallStep(str, Enum):
    """Installation steps for progress tracking."""

    CHECK_DEPS = "check_dependencies"
    CREATE_DIRS = "create_directories"
    COPY_TEMPLATES = "copy_templates"
    INIT_DATABASE = "init_database"
    START_QDRANT = "start_qdrant"
    REGISTER_MCP = "register_mcp_server"
    REGISTER_HOOKS = "register_hooks"
    START_SERVER = "start_server"
    VERIFY = "verify_installation"


@dataclass
class InstallResult:
    """Result of installation attempt."""

    status: Literal["success", "partial", "failed"] = "success"
    steps_completed: list[InstallStep] = field(default_factory=list)
    steps_skipped: list[InstallStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def add_completed(self, step: InstallStep) -> None:
        """Mark a step as completed."""
        self.steps_completed.append(step)

    def add_skipped(self, step: InstallStep, reason: str) -> None:
        """Mark a step as skipped with reason."""
        self.steps_skipped.append(step)
        self.warnings.append(f"{step.value}: skipped - {reason}")

    def add_error(self, step: InstallStep, error: str) -> None:
        """Record an error for a step."""
        self.errors.append(f"{step.value}: {error}")
        self.status = "failed"

    def add_warning(self, warning: str) -> None:
        """Add a warning message."""
        self.warnings.append(warning)


@dataclass
class InstallOptions:
    """Options controlling installation behavior."""

    dev_mode: bool = False
    skip_qdrant: bool = False
    skip_hooks: bool = False
    skip_mcp: bool = False
    skip_server: bool = False
    force: bool = False
    dry_run: bool = False
    verbose: bool = False
    calm_home: Path | None = None  # Override for testing
    dev_directory: Path | None = None  # Development directory for --dev mode


def install(options: InstallOptions | None = None) -> InstallResult:
    """Run CALM installation.

    Args:
        options: Installation options (uses defaults if None)

    Returns:
        InstallResult with status and details
    """
    from calm.install.steps import run_installation

    if options is None:
        options = InstallOptions()
    return run_installation(options)


__all__ = [
    "InstallStep",
    "InstallResult",
    "InstallOptions",
    "install",
]
