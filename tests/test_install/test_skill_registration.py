"""Tests for Claude Code skill registration.

Regression tests for BUG-072: /orchestrate skill not registered
in Claude Code skills directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from calm.install.config_merge import (
    install_claude_code_skills,
    merge_skill_rules,
    register_claude_code_skills,
)


class TestMergeSkillRules:
    """Tests for merge_skill_rules."""

    def test_adds_calm_skills_to_empty_rules(self) -> None:
        """Should add all CALM skills to empty rules."""
        rules: dict[str, object] = {}
        result = merge_skill_rules(rules)

        assert "skills" in result
        assert "calm-orchestrate" in result["skills"]
        assert "calm-wrapup" in result["skills"]
        assert "calm-reflection" in result["skills"]

    def test_preserves_existing_skills(self) -> None:
        """Should not remove existing skills."""
        rules = {
            "skills": {
                "workflow-setup": {
                    "type": "domain",
                    "description": "Existing skill",
                }
            }
        }
        result = merge_skill_rules(rules)

        assert "workflow-setup" in result["skills"]
        assert "calm-orchestrate" in result["skills"]

    def test_does_not_mutate_original(self) -> None:
        """Should not modify the original rules dict."""
        inner: dict[str, dict[str, str]] = {"existing": {"type": "domain"}}
        rules: dict[str, object] = {"skills": inner}
        original_keys = set(inner.keys())

        merge_skill_rules(rules)

        assert set(inner.keys()) == original_keys

    def test_orchestrate_has_correct_triggers(self) -> None:
        """Should have correct trigger keywords for orchestrate."""
        result = merge_skill_rules({})
        orchestrate = result["skills"]["calm-orchestrate"]

        keywords = orchestrate["promptTriggers"]["keywords"]
        assert "/orchestrate" in keywords
        assert "orchestrate" in keywords
        assert "start orchestration" in keywords

    def test_wrapup_has_correct_triggers(self) -> None:
        """Should have correct trigger keywords for wrapup."""
        result = merge_skill_rules({})
        wrapup = result["skills"]["calm-wrapup"]

        keywords = wrapup["promptTriggers"]["keywords"]
        assert "/wrapup" in keywords
        assert "wrapup" in keywords

    def test_reflection_has_correct_triggers(self) -> None:
        """Should have correct trigger keywords for reflection."""
        result = merge_skill_rules({})
        reflection = result["skills"]["calm-reflection"]

        keywords = reflection["promptTriggers"]["keywords"]
        assert "/reflection" in keywords
        assert "reflection" in keywords

    def test_idempotent(self) -> None:
        """Running twice should produce same result."""
        rules: dict[str, object] = {}
        result1 = merge_skill_rules(rules)
        result2 = merge_skill_rules(result1)

        assert result1 == result2


class TestInstallClaudeCodeSkills:
    """Tests for install_claude_code_skills."""

    def test_installs_all_skill_wrappers(self, tmp_path: Path) -> None:
        """Should create SKILL.md symlinks for all three skills."""
        installed, skipped, errors = install_claude_code_skills(tmp_path)

        assert len(errors) == 0, f"Errors: {errors}"
        assert len(installed) == 3
        for name in ("orchestrate", "wrapup", "reflection"):
            skill_file = tmp_path / name / "SKILL.md"
            assert skill_file.exists()
            assert skill_file.is_symlink(), f"{name} should be a symlink"

    def test_skill_wrapper_has_frontmatter(self, tmp_path: Path) -> None:
        """Skill wrappers should have YAML frontmatter."""
        install_claude_code_skills(tmp_path)

        content = (tmp_path / "orchestrate" / "SKILL.md").read_text()
        assert content.startswith("---")
        assert "name: orchestrate" in content

    def test_orchestrate_skill_content(self, tmp_path: Path) -> None:
        """Orchestrate SKILL.md should reference calm commands."""
        install_claude_code_skills(tmp_path)

        content = (tmp_path / "orchestrate" / "SKILL.md").read_text()
        assert "calm status" in content
        assert "CLAUDE.md" in content

    def test_wrapup_skill_content(self, tmp_path: Path) -> None:
        """Wrapup SKILL.md should contain session handoff instructions."""
        install_claude_code_skills(tmp_path)

        content = (tmp_path / "wrapup" / "SKILL.md").read_text()
        assert "calm status" in content
        assert "Session Summary" in content

    def test_reflection_skill_content(self, tmp_path: Path) -> None:
        """Reflection SKILL.md should contain reflection process."""
        install_claude_code_skills(tmp_path)

        content = (tmp_path / "reflection" / "SKILL.md").read_text()
        assert "GHAP" in content
        assert "mcp__calm__" in content

    def test_skips_correct_symlinks(self, tmp_path: Path) -> None:
        """Should skip skill files that are already correct symlinks."""
        # First install
        install_claude_code_skills(tmp_path)

        # Second install — symlinks are already correct
        installed, skipped, errors = install_claude_code_skills(tmp_path)

        assert len(installed) == 0
        assert len(skipped) == 3
        assert "symlink correct" in skipped[0]

    def test_skips_existing_regular_file_without_force(
        self, tmp_path: Path
    ) -> None:
        """Should skip existing regular files without --force."""
        skill_dir = tmp_path / "orchestrate"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("custom content")

        installed, skipped, errors = install_claude_code_skills(tmp_path)

        assert len(skipped) >= 1
        assert skill_file.read_text() == "custom content"
        assert not skill_file.is_symlink()

    def test_force_replaces_regular_file_with_symlink(
        self, tmp_path: Path
    ) -> None:
        """Should replace existing regular files with symlinks when --force."""
        skill_dir = tmp_path / "orchestrate"
        skill_dir.mkdir(parents=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("custom content")

        installed, skipped, errors = install_claude_code_skills(
            tmp_path, force=True
        )

        assert len(errors) == 0
        assert skill_file.is_symlink()
        assert skill_file.read_text().startswith("---")

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        """Dry run should not create files."""
        installed, skipped, errors = install_claude_code_skills(
            tmp_path, dry_run=True
        )

        assert len(installed) == 3
        assert "Would symlink" in installed[0]
        assert not (tmp_path / "orchestrate" / "SKILL.md").exists()


class TestRegisterClaudeCodeSkills:
    """Tests for register_claude_code_skills (full registration)."""

    def test_installs_skills_and_updates_rules(self, tmp_path: Path) -> None:
        """Should install skills and update skill-rules.json."""
        skills_dir = tmp_path / "skills"
        rules_path = skills_dir / "skill-rules.json"

        message = register_claude_code_skills(skills_dir, rules_path)

        # Skill wrappers should exist
        assert (skills_dir / "orchestrate" / "SKILL.md").exists()
        assert (skills_dir / "wrapup" / "SKILL.md").exists()
        assert (skills_dir / "reflection" / "SKILL.md").exists()

        # skill-rules.json should be updated
        assert rules_path.exists()
        rules = json.loads(rules_path.read_text())
        assert "calm-orchestrate" in rules["skills"]
        assert "calm-wrapup" in rules["skills"]
        assert "calm-reflection" in rules["skills"]

        assert "Symlinked" in message

    def test_preserves_existing_rules(self, tmp_path: Path) -> None:
        """Should preserve existing entries in skill-rules.json."""
        skills_dir = tmp_path / "skills"
        rules_path = skills_dir / "skill-rules.json"

        # Create existing rules file
        skills_dir.mkdir(parents=True, exist_ok=True)
        existing_rules = {
            "version": "1.0",
            "skills": {
                "workflow-setup": {"type": "domain", "description": "Existing"},
            },
        }
        rules_path.write_text(json.dumps(existing_rules))

        register_claude_code_skills(skills_dir, rules_path)

        # Both old and new skills should exist
        rules = json.loads(rules_path.read_text())
        assert "workflow-setup" in rules["skills"]
        assert "calm-orchestrate" in rules["skills"]

    def test_dry_run_no_file_changes(self, tmp_path: Path) -> None:
        """Dry run should not create any files."""
        skills_dir = tmp_path / "skills"
        rules_path = skills_dir / "skill-rules.json"

        register_claude_code_skills(skills_dir, rules_path, dry_run=True)

        assert not (skills_dir / "orchestrate" / "SKILL.md").exists()
        assert not rules_path.exists()


class TestInstallerIntegration:
    """Integration tests verifying skills are installed during calm init."""

    def test_installation_creates_skill_wrappers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """calm init should create Claude Code skill wrappers."""
        from calm.install import InstallOptions, install

        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success", f"Errors: {result.errors}"

        # Claude Code skill wrappers should be created
        claude_skills = tmp_path / ".claude" / "skills"
        assert (claude_skills / "orchestrate" / "SKILL.md").exists()
        assert (claude_skills / "wrapup" / "SKILL.md").exists()
        assert (claude_skills / "reflection" / "SKILL.md").exists()

    def test_installation_updates_skill_rules(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """calm init should update skill-rules.json."""
        from calm.install import InstallOptions, install

        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success", f"Errors: {result.errors}"

        rules_path = tmp_path / ".claude" / "skills" / "skill-rules.json"
        assert rules_path.exists()
        rules = json.loads(rules_path.read_text())
        assert "calm-orchestrate" in rules["skills"]
        assert "calm-wrapup" in rules["skills"]
        assert "calm-reflection" in rules["skills"]

    def test_skip_hooks_skips_skills(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """--skip-hooks should also skip skill registration."""
        from calm.install import InstallOptions, InstallStep, install

        monkeypatch.setenv("HOME", str(tmp_path))
        calm_home = tmp_path / ".calm"

        options = InstallOptions(
            calm_home=calm_home,
            skip_qdrant=True,
            skip_mcp=True,
            skip_hooks=True,
            skip_server=True,
        )

        result = install(options)
        assert result.status == "success"
        assert InstallStep.REGISTER_SKILLS in result.steps_skipped

        # No skill wrappers should be created
        claude_skills = tmp_path / ".claude" / "skills"
        assert not (claude_skills / "orchestrate" / "SKILL.md").exists()
