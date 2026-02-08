"""Git worktree management for CALM orchestration.

This module handles creation, management, and merging of git worktrees.
"""

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from calm.orchestration.counters import get_counter, increment_counter
from calm.orchestration.project import detect_main_repo, get_current_commit
from calm.orchestration.tasks import get_task, update_task


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    task_id: str
    path: Path
    branch: str
    task_type: str | None = None
    phase: str | None = None


def create_worktree(
    task_id: str,
    base_dir: Path | None = None,
    db_path: Path | None = None,
) -> WorktreeInfo:
    """Create a git worktree for a task.

    Args:
        task_id: Task identifier (becomes branch name)
        base_dir: Base directory for worktrees (defaults to .worktrees in main repo)
        db_path: Optional path to database file

    Returns:
        WorktreeInfo for the created worktree

    Raises:
        ValueError: If task not found or worktree creation fails
    """
    # Get task info
    task = get_task(task_id, db_path=db_path)
    if not task:
        raise ValueError(f"Task {task_id} not found")

    # Get main repo path
    main_repo = Path(detect_main_repo())

    if base_dir is None:
        base_dir = main_repo / ".worktrees"

    worktree_path = base_dir / task_id

    # Create worktree
    result = subprocess.run(
        ["git", "worktree", "add", str(worktree_path), "-b", task_id],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        # Try without -b if branch already exists
        result = subprocess.run(
            ["git", "worktree", "add", str(worktree_path), task_id],
            cwd=main_repo,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise ValueError(f"Failed to create worktree: {result.stderr}")

    # Create appropriate directories based on task type
    if task.task_type == "feature":
        planning_dir = worktree_path / "planning_docs" / task_id
        planning_dir.mkdir(parents=True, exist_ok=True)

        changelog_dir = worktree_path / "changelog.d"
        changelog_dir.mkdir(parents=True, exist_ok=True)
    elif task.task_type == "bug":
        bug_reports_dir = worktree_path / "bug_reports"
        bug_reports_dir.mkdir(parents=True, exist_ok=True)

        # Create bug report template
        bug_report_file = bug_reports_dir / f"{task_id}.md"
        if not bug_report_file.exists():
            bug_report_file.write_text(f"""# Bug Report: {task_id}

## Title
{task.title}

## First Noticed On Commit
<!-- SHA where bug was first observed -->

## Reproduction Steps
1.
2.
3.

## Expected Behavior


## Actual Behavior


## Root Cause
<!-- Filled during investigation -->

## Fix Plan
<!-- Filled during investigation -->
""")

        changelog_dir = worktree_path / "changelog.d"
        changelog_dir.mkdir(parents=True, exist_ok=True)

    # Update task with worktree path
    update_task(task_id, worktree_path=str(worktree_path), db_path=db_path)

    return WorktreeInfo(
        task_id=task_id,
        path=worktree_path,
        branch=task_id,
        task_type=task.task_type,
        phase=task.phase,
    )


def remove_worktree(
    task_id: str,
    db_path: Path | None = None,
) -> None:
    """Remove a worktree without merging.

    Args:
        task_id: Task identifier
        db_path: Optional path to database file

    Raises:
        ValueError: If removal fails
    """
    main_repo = Path(detect_main_repo())
    worktree_path = main_repo / ".worktrees" / task_id

    # If our cwd is inside the worktree, move to main repo first to
    # avoid leaving the process (and any parent shell) in a deleted dir.
    try:
        cwd = Path.cwd()
        if cwd == worktree_path or worktree_path in cwd.parents:
            os.chdir(main_repo)
    except OSError:
        os.chdir(main_repo)

    # Remove worktree
    result = subprocess.run(
        ["git", "worktree", "remove", str(worktree_path), "--force"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise ValueError(f"Failed to remove worktree: {result.stderr}")

    # Clear worktree path in task
    task = get_task(task_id, db_path=db_path)
    if task:
        update_task(task_id, worktree_path="", db_path=db_path)


def list_worktrees(
    project_path: str | None = None,
    db_path: Path | None = None,
) -> list[WorktreeInfo]:
    """List all worktrees.

    Args:
        project_path: Project path filter
        db_path: Optional path to database file

    Returns:
        List of WorktreeInfo
    """
    main_repo = Path(detect_main_repo())

    result = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return []

    worktrees: list[WorktreeInfo] = []
    current_path: Path | None = None
    current_branch: str | None = None

    for line in result.stdout.split("\n"):
        if line.startswith("worktree "):
            current_path = Path(line[9:])
        elif line.startswith("branch refs/heads/"):
            current_branch = line[18:]
        elif line == "" and current_path and current_branch:
            # Skip the main worktree
            if ".worktrees" in str(current_path):
                task_id = current_branch
                task = get_task(task_id, db_path=db_path)
                worktrees.append(
                    WorktreeInfo(
                        task_id=task_id,
                        path=current_path,
                        branch=current_branch,
                        task_type=task.task_type if task else None,
                        phase=task.phase if task else None,
                    )
                )
            current_path = None
            current_branch = None

    return worktrees


def get_worktree_path(
    task_id: str,
    db_path: Path | None = None,
) -> Path | None:
    """Get the worktree path for a task.

    Args:
        task_id: Task identifier
        db_path: Optional path to database file

    Returns:
        The worktree path or None if not found
    """
    task = get_task(task_id, db_path=db_path)
    if task and task.worktree_path:
        return Path(task.worktree_path)
    return None


def merge_worktree(
    task_id: str,
    skip_sync: bool = False,
    force: bool = False,
    db_path: Path | None = None,
) -> str:
    """Merge worktree to main and cleanup.

    Args:
        task_id: Task identifier
        skip_sync: Skip dependency sync after merge
        force: Force merge even if merge_lock is set
        db_path: Optional path to database file

    Returns:
        The merge commit SHA

    Raises:
        ValueError: If merge fails or merge_lock is active
    """
    # Check merge lock
    if not force and get_counter("merge_lock", db_path) > 0:
        raise ValueError("Merge lock is active. Use --force to override.")

    main_repo = Path(detect_main_repo())
    worktree_path = main_repo / ".worktrees" / task_id

    if not worktree_path.exists():
        raise ValueError(f"Worktree not found: {worktree_path}")

    # Switch to main branch
    result = subprocess.run(
        ["git", "checkout", "main"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Failed to checkout main: {result.stderr}")

    # Pull latest
    result = subprocess.run(
        ["git", "pull", "--ff-only"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )
    # Pull may fail if there's no upstream, which is OK

    # Merge with --no-ff
    result = subprocess.run(
        ["git", "merge", "--no-ff", task_id, "-m", f"Merge task {task_id}"],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise ValueError(f"Merge failed: {result.stderr}")

    # Get merge commit SHA
    merge_sha = get_current_commit(main_repo)

    # Increment merge counters
    increment_counter("merges_since_e2e", db_path)
    increment_counter("merges_since_docs", db_path)

    # Sync dependencies if needed
    if not skip_sync:
        uv_lock = main_repo / "uv.lock"
        requirements = main_repo / "requirements.txt"
        if uv_lock.exists():
            subprocess.run(["uv", "sync"], cwd=main_repo, capture_output=True)
        elif requirements.exists():
            subprocess.run(
                ["pip", "install", "-r", "requirements.txt"],
                cwd=main_repo,
                capture_output=True,
            )

    # If our cwd is inside the worktree, move to main repo first to
    # avoid leaving the process (and any parent shell) in a deleted dir.
    try:
        cwd = Path.cwd()
        if cwd == worktree_path or worktree_path in cwd.parents:
            os.chdir(main_repo)
    except OSError:
        # cwd already invalid (deleted by a prior operation)
        os.chdir(main_repo)

    # Remove worktree
    subprocess.run(
        ["git", "worktree", "remove", str(worktree_path), "--force"],
        cwd=main_repo,
        capture_output=True,
    )

    # Delete branch
    subprocess.run(
        ["git", "branch", "-d", task_id],
        cwd=main_repo,
        capture_output=True,
    )

    # Clear worktree path in task
    task = get_task(task_id, db_path=db_path)
    if task:
        update_task(task_id, worktree_path="", db_path=db_path)

    return merge_sha


def check_merge_conflicts(
    task_id: str,
) -> list[str]:
    """Check for merge conflicts without merging.

    Args:
        task_id: Task identifier

    Returns:
        List of conflicting files (empty if no conflicts)
    """
    main_repo = Path(detect_main_repo())

    # Try a dry-run merge
    result = subprocess.run(
        ["git", "merge", "--no-commit", "--no-ff", task_id],
        cwd=main_repo,
        capture_output=True,
        text=True,
    )

    # Abort the merge
    subprocess.run(
        ["git", "merge", "--abort"],
        cwd=main_repo,
        capture_output=True,
    )

    if result.returncode == 0:
        return []

    # Parse conflicting files from output
    conflicts: list[str] = []
    for line in result.stderr.split("\n"):
        if "CONFLICT" in line:
            # Extract filename from conflict message
            parts = line.split(" ")
            for part in parts:
                if "/" in part or "." in part:
                    conflicts.append(part.strip(":"))
                    break

    return conflicts
