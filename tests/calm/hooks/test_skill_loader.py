"""Tests for CALM skill loader."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from calm.hooks.skill_loader import (
    TaskInfo,
    format_task_table,
    get_tasks_for_project,
    load_orchestrate_skill,
    load_skill,
)


class TestGetTasksForProject:
    """Tests for get_tasks_for_project function."""

    def test_no_tasks(self, temp_db: Path) -> None:
        """Test returns empty list when no tasks exist."""
        result = get_tasks_for_project("/test/project", temp_db)
        assert result == []

    def test_with_tasks(self, db_with_tasks: Path) -> None:
        """Test returns tasks for matching project."""
        result = get_tasks_for_project("/test/project", db_with_tasks)
        assert len(result) == 2
        task_ids = [t.id for t in result]
        assert "SPEC-001" in task_ids
        assert "BUG-001" in task_ids

    def test_excludes_done_tasks(self, temp_db: Path) -> None:
        """Test excludes tasks in DONE phase."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (id, title, task_type, phase, project_path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SPEC-DONE",
                "Done Task",
                "feature",
                "DONE",
                "/test/project",
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        result = get_tasks_for_project("/test/project", temp_db)
        task_ids = [t.id for t in result]
        assert "SPEC-DONE" not in task_ids

    def test_parses_blocked_by(self, temp_db: Path) -> None:
        """Test parses blocked_by JSON."""
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO tasks (id, title, task_type, phase, project_path, blocked_by, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "SPEC-002",
                "Blocked Task",
                "feature",
                "IMPLEMENT",
                "/test/project",
                '["SPEC-001"]',
                "2026-01-01T00:00:00",
                "2026-01-01T00:00:00",
            ),
        )
        conn.commit()
        conn.close()

        result = get_tasks_for_project("/test/project", temp_db)
        blocked_task = next(t for t in result if t.id == "SPEC-002")
        assert blocked_task.blocked_by == ["SPEC-001"]

    def test_missing_database(self, tmp_path: Path) -> None:
        """Test returns empty list when database missing."""
        result = get_tasks_for_project("/test/project", tmp_path / "nonexistent.db")
        assert result == []


class TestFormatTaskTable:
    """Tests for format_task_table function."""

    def test_empty_tasks(self) -> None:
        """Test formats message for no tasks."""
        result = format_task_table([])
        assert "No active tasks" in result

    def test_single_task(self) -> None:
        """Test formats single task."""
        tasks = [TaskInfo(id="SPEC-001", phase="IMPLEMENT", title="Test Task", blocked_by=[])]
        result = format_task_table(tasks)
        assert "| SPEC-001 | IMPLEMENT | Test Task | - |" in result

    def test_task_with_blockers(self) -> None:
        """Test formats task with blockers."""
        tasks = [
            TaskInfo(
                id="SPEC-002",
                phase="DESIGN",
                title="Blocked Task",
                blocked_by=["SPEC-001", "BUG-001"],
            )
        ]
        result = format_task_table(tasks)
        assert "SPEC-001, BUG-001" in result

    def test_truncates_long_titles(self) -> None:
        """Test truncates long titles."""
        tasks = [
            TaskInfo(
                id="SPEC-001",
                phase="IMPLEMENT",
                title="x" * 60,
                blocked_by=[],
            )
        ]
        result = format_task_table(tasks)
        # Should truncate at 40 chars + "..."
        assert "x" * 40 + "..." in result
        assert "x" * 41 + "..." not in result

    def test_limits_to_20_tasks(self) -> None:
        """Test limits output to 20 tasks."""
        tasks = [
            TaskInfo(id=f"SPEC-{i:03d}", phase="IMPLEMENT", title=f"Task {i}", blocked_by=[])
            for i in range(25)
        ]
        result = format_task_table(tasks)
        assert "SPEC-000" in result
        assert "SPEC-019" in result
        assert "SPEC-020" not in result
        assert "5 more tasks" in result


class TestLoadOrchestrateskill:
    """Tests for load_orchestrate_skill function."""

    def test_missing_skill_file(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test raises error when skill file missing."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        with pytest.raises(FileNotFoundError) as exc_info:
            load_orchestrate_skill("/test/project")

        assert "Skill file not found" in str(exc_info.value)

    def test_missing_workflow_file(
        self,
        temp_calm_home: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test raises error when workflow file missing."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        # Create skill file but not workflow file
        skills_dir = temp_calm_home / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "orchestrate.md").write_text("# Orchestrate\n{{WORKFLOW_CONTENT}}\n{{TASK_LIST}}")

        with pytest.raises(FileNotFoundError) as exc_info:
            load_orchestrate_skill("/test/project")

        assert "Workflow file not found" in str(exc_info.value)

    def test_loads_and_substitutes(
        self,
        temp_calm_home: Path,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test loads skill and substitutes placeholders."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home, db_path=temp_db)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        # Create skill file
        skills_dir = temp_calm_home / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "orchestrate.md").write_text(
            "# Orchestrate\n\n{{WORKFLOW_CONTENT}}\n\n## Tasks\n{{TASK_LIST}}"
        )

        # Create workflow file
        workflows_dir = temp_calm_home / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "default.md").write_text("# Workflow Instructions\n\nDo the thing.")

        result = load_orchestrate_skill("/test/project", temp_db)

        assert "# Orchestrate" in result
        assert "# Workflow Instructions" in result
        assert "Do the thing" in result
        assert "## Tasks" in result
        assert "No active tasks" in result


class TestLoadSkill:
    """Tests for load_skill function."""

    def test_loads_orchestrate_skill(
        self,
        temp_calm_home: Path,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test loads orchestrate skill."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home, db_path=temp_db)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        # Create required files
        skills_dir = temp_calm_home / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "orchestrate.md").write_text("{{WORKFLOW_CONTENT}}\n{{TASK_LIST}}")

        workflows_dir = temp_calm_home / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "default.md").write_text("Workflow")

        result = load_skill("orchestrate", "/test/project", temp_db)
        assert "Workflow" in result

    def test_loads_simple_skill(
        self,
        temp_calm_home: Path,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test loads simple skill without substitution."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home, db_path=temp_db)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        # Create skill file
        skills_dir = temp_calm_home / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "simple.md").write_text("# Simple Skill\n\nJust some content.")

        result = load_skill("simple", "/test/project", temp_db)
        assert "# Simple Skill" in result
        assert "Just some content" in result

    def test_missing_skill(
        self,
        temp_calm_home: Path,
        temp_db: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test raises error for missing skill."""
        from calm.config import CalmSettings

        settings = CalmSettings(home=temp_calm_home, db_path=temp_db)
        monkeypatch.setattr("calm.hooks.skill_loader.settings", settings)

        with pytest.raises(FileNotFoundError):
            load_skill("nonexistent", "/test/project", temp_db)
