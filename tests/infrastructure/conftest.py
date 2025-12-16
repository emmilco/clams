"""Shared utilities for configuration parity verification tests.

This module provides helper functions used across all parity test modules.
These utilities enable consistent verification of test/production configuration
alignment across the codebase.

Reference: SPEC-024 (Configuration Parity Verification)
Related bugs: BUG-031 (clustering), BUG-033 (server command)
"""

import re
from pathlib import Path
from typing import Any

from clams.server.config import ServerSettings


def get_repo_root() -> Path:
    """Get the repository root directory.

    Returns:
        Path to the repository root (parent of tests/)
    """
    return Path(__file__).parent.parent.parent


def get_fixture_expectations() -> dict[str, dict[str, Any]]:
    """Return expected fixture values based on ServerSettings.

    This is the canonical reference for what fixture values should be.
    Tests compare actual fixture values against these expectations.

    Returns:
        Dict mapping fixture names to their expected configuration values.
    """
    settings = ServerSettings()

    return {
        "mock_code_embedder": {
            # 384 is MiniLM model output dimension - fixed, not configurable
            "dimension": 384,
            "embed_return_length": 384,
        },
        "mock_semantic_embedder": {
            "dimension": settings.embedding_dimension,  # 768
            "embed_return_length": settings.embedding_dimension,
        },
        "clustering": {
            "min_cluster_size": settings.hdbscan_min_cluster_size,
            "min_samples": settings.hdbscan_min_samples,
        },
        "timeouts": {
            "verification": settings.verification_timeout,
            "http_call": settings.http_call_timeout,
            "qdrant": settings.qdrant_timeout,
        },
        "server": {
            "command": settings.server_command,
            "host": settings.http_host,
            "port": settings.http_port,
        },
        "ghap": {
            "check_frequency": settings.ghap_check_frequency,
        },
    }


# Files that may intentionally use non-production configuration
ALLOWED_INTENTIONAL_DIFFERENCES: dict[str, set[str]] = {
    "min_cluster_size": {
        "tests/clustering/test_bug_031_regression.py",
        "tests/clustering/test_experience.py",
        "tests/clustering/test_clusterer.py",
    },
    "min_samples": {
        "tests/clustering/test_bug_031_regression.py",
        "tests/clustering/test_experience.py",
        "tests/clustering/test_clusterer.py",
    },
}


def is_intentional_difference(config_key: str, file_path: Path) -> bool:
    """Check if a file is allowed to have intentional configuration differences.

    Args:
        config_key: The configuration key being checked (e.g., "min_cluster_size")
        file_path: The file path being verified

    Returns:
        True if this file is in the allowlist for this configuration key
    """
    allowed_files = ALLOWED_INTENTIONAL_DIFFERENCES.get(config_key, set())
    # Normalize path for comparison
    repo_root = get_repo_root()
    try:
        relative_path = str(file_path.relative_to(repo_root))
    except ValueError:
        # file_path is not relative to repo_root, use string replacement
        relative_path = str(file_path).replace(str(repo_root) + "/", "")
    return relative_path in allowed_files


def extract_python_assignments(
    content: str, variable_name: str
) -> list[tuple[int, str]]:
    """Extract variable assignments from Python source code.

    Args:
        content: Python source code
        variable_name: Name of variable to find assignments for

    Returns:
        List of (line_number, value) tuples for each assignment found
    """
    # Pattern matches: variable_name = value or variable_name=value
    pattern = rf"(?:^|\s){re.escape(variable_name)}\s*=\s*([^\n,)]+)"
    matches: list[tuple[int, str]] = []
    for i, line in enumerate(content.split("\n"), 1):
        match = re.search(pattern, line)
        if match:
            value = match.group(1).strip().rstrip(",").strip()
            matches.append((i, value))
    return matches


def extract_shell_assignments(
    content: str, variable_name: str
) -> list[tuple[int, str]]:
    """Extract variable assignments from shell script.

    Args:
        content: Shell script content
        variable_name: Name of variable to find assignments for

    Returns:
        List of (line_number, value) tuples for each assignment found
    """
    # Pattern: VARIABLE_NAME="value" or VARIABLE_NAME=value or VARIABLE_NAME=${...:-default}
    pattern = rf'^{re.escape(variable_name)}=(["\']?)([^"\'}}\n]+)\1'
    matches: list[tuple[int, str]] = []
    for i, line in enumerate(content.split("\n"), 1):
        match = re.match(pattern, line.strip())
        if match:
            value = match.group(2).strip()
            matches.append((i, value))
    return matches
