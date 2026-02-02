"""Project path detection and management for CALM orchestration.

This module provides utilities for detecting the current project path
and the main repository path (for worktree scenarios).
"""

import subprocess
from pathlib import Path


def detect_project_path() -> str:
    """Detect the project path from current working directory.

    This finds the git root of the current directory.

    Returns:
        The absolute path to the project root
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return str(Path.cwd())


def detect_main_repo() -> str:
    """Detect the main repo path (not worktree).

    If the current directory is in a worktree, this returns
    the path to the main repository.

    Returns:
        The absolute path to the main repository
    """
    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        first_line = result.stdout.split("\n")[0]
        if first_line.startswith("worktree "):
            return first_line[9:]
    return detect_project_path()


def get_current_commit(path: str | Path | None = None) -> str:
    """Get the current commit SHA.

    Args:
        path: Optional path to the repository

    Returns:
        The current commit SHA (short form)
    """
    cwd = str(path) if path else None
    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def get_current_branch(path: str | Path | None = None) -> str:
    """Get the current branch name.

    Args:
        path: Optional path to the repository

    Returns:
        The current branch name
    """
    cwd = str(path) if path else None
    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def is_in_worktree(path: str | Path | None = None) -> bool:
    """Check if the current directory is in a worktree.

    Args:
        path: Optional path to check

    Returns:
        True if in a worktree, False otherwise
    """
    cwd = str(path) if path else None
    result = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode != 0:
        return False

    # Check if this is a linked worktree
    git_dir_result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if git_dir_result.returncode == 0:
        git_dir = git_dir_result.stdout.strip()
        # Linked worktrees have a .git file pointing to worktrees/<name>
        return ".git/worktrees/" in git_dir or git_dir.endswith(".git")
    return False


def get_worktree_name(path: str | Path | None = None) -> str | None:
    """Get the worktree name if in a worktree.

    Args:
        path: Optional path to check

    Returns:
        The worktree name or None if not in a worktree
    """
    cwd = str(path) if path else None
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    if result.returncode == 0:
        git_dir = result.stdout.strip()
        # Linked worktrees have format: .git/worktrees/<name>
        if ".git/worktrees/" in git_dir:
            parts = git_dir.split(".git/worktrees/")
            if len(parts) > 1:
                return parts[1].split("/")[0]
    return None
