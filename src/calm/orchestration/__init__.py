"""CALM Orchestration - Business logic for task management.

This module provides the business logic layer for orchestration,
including task management, worktree handling, gate checks, and more.
"""

from calm.orchestration.counters import (
    add_counter,
    get_counter,
    increment_counter,
    list_counters,
    reset_counter,
    set_counter,
)
from calm.orchestration.phases import (
    BUG_PHASES,
    BUG_TRANSITIONS,
    FEATURE_PHASES,
    FEATURE_TRANSITIONS,
    get_initial_phase,
    get_next_phases,
    is_valid_transition,
)
from calm.orchestration.project import (
    detect_main_repo,
    detect_project_path,
    get_current_commit,
)
from calm.orchestration.reviews import (
    Review,
    check_reviews,
    clear_reviews,
    list_reviews,
    record_review,
)
from calm.orchestration.tasks import (
    Task,
    create_task,
    delete_task,
    get_task,
    list_tasks,
    transition_task,
    update_task,
)
from calm.orchestration.workers import (
    Worker,
    cleanup_stale_workers,
    complete_worker,
    fail_worker,
    get_role_prompt,
    get_worker_context,
    list_workers,
    start_worker,
)

__all__ = [
    # Tasks
    "Task",
    "create_task",
    "get_task",
    "list_tasks",
    "update_task",
    "transition_task",
    "delete_task",
    # Phases
    "FEATURE_PHASES",
    "BUG_PHASES",
    "FEATURE_TRANSITIONS",
    "BUG_TRANSITIONS",
    "get_initial_phase",
    "get_next_phases",
    "is_valid_transition",
    # Project
    "detect_project_path",
    "detect_main_repo",
    "get_current_commit",
    # Counters
    "list_counters",
    "get_counter",
    "set_counter",
    "increment_counter",
    "reset_counter",
    "add_counter",
    # Reviews
    "Review",
    "record_review",
    "list_reviews",
    "check_reviews",
    "clear_reviews",
    # Workers
    "Worker",
    "start_worker",
    "complete_worker",
    "fail_worker",
    "list_workers",
    "cleanup_stale_workers",
    "get_worker_context",
    "get_role_prompt",
]
