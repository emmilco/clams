"""Deployment verification tests for CALM hooks and skills.

SPEC-061-06: Verifies that:
1. Hook registration in ~/.claude/settings.json is correct (AC1)
2. Skill files exist and are non-empty (AC4)
3. skill-rules.json is valid JSON with correct trigger patterns (AC5)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def claude_settings_path() -> Path:
    """Path to Claude Code settings.json."""
    return Path.home() / ".claude" / "settings.json"


@pytest.fixture
def claude_skills_path() -> Path:
    """Path to Claude Code skills directory."""
    return Path.home() / ".claude" / "skills"


class TestHookRegistration:
    """AC1: Hook registration in settings.json is correct."""

    def test_settings_json_exists(self, claude_settings_path: Path) -> None:
        """Test that ~/.claude/settings.json exists."""
        assert claude_settings_path.exists(), f"settings.json not found at {claude_settings_path}"

    def test_settings_json_is_valid_json(self, claude_settings_path: Path) -> None:
        """Test that settings.json is valid JSON."""
        if not claude_settings_path.exists():
            pytest.skip("settings.json not found")
        content = claude_settings_path.read_text()
        data = json.loads(content)  # Raises JSONDecodeError if invalid
        assert isinstance(data, dict)

    def test_hooks_section_exists(self, claude_settings_path: Path) -> None:
        """Test that hooks section exists in settings."""
        if not claude_settings_path.exists():
            pytest.skip("settings.json not found")
        data = json.loads(claude_settings_path.read_text())
        assert "hooks" in data, "No 'hooks' section in settings.json"

    def test_all_four_hooks_registered(self, claude_settings_path: Path) -> None:
        """Test that all four hook types are registered."""
        if not claude_settings_path.exists():
            pytest.skip("settings.json not found")
        data = json.loads(claude_settings_path.read_text())
        hooks = data.get("hooks", {})
        expected = ["SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse"]
        for hook_name in expected:
            assert hook_name in hooks, f"Missing hook: {hook_name}"

    @pytest.mark.parametrize(
        "hook_name,expected_module",
        [
            ("SessionStart", "calm.hooks.session_start"),
            ("UserPromptSubmit", "calm.hooks.user_prompt_submit"),
            ("PreToolUse", "calm.hooks.pre_tool_use"),
            ("PostToolUse", "calm.hooks.post_tool_use"),
        ],
    )
    def test_hook_command_format(
        self,
        claude_settings_path: Path,
        hook_name: str,
        expected_module: str,
    ) -> None:
        """Test each hook has correct command format."""
        if not claude_settings_path.exists():
            pytest.skip("settings.json not found")
        data = json.loads(claude_settings_path.read_text())
        hooks = data.get("hooks", {})
        if hook_name not in hooks:
            pytest.skip(f"Hook {hook_name} not registered")

        entries = hooks[hook_name]
        assert isinstance(entries, list), f"{hook_name}: expected list of entries"
        assert len(entries) > 0, f"{hook_name}: no entries"

        entry = entries[0]
        assert "hooks" in entry, f"{hook_name}: entry missing 'hooks' key"

        hook_list = entry["hooks"]
        assert len(hook_list) > 0, f"{hook_name}: no hooks in entry"

        hook_def = hook_list[0]
        assert hook_def.get("type") == "command", f"{hook_name}: type should be 'command'"
        command = hook_def.get("command", "")
        assert expected_module in command, (
            f"{hook_name}: command '{command}' doesn't reference '{expected_module}'"
        )


class TestSkillFiles:
    """AC4: Skill files exist and are syntactically valid."""

    @pytest.mark.parametrize(
        "skill_name",
        ["orchestrate", "wrapup", "reflection"],
    )
    def test_skill_file_exists(
        self,
        claude_skills_path: Path,
        skill_name: str,
    ) -> None:
        """Test that SKILL.md exists for each skill."""
        skill_file = claude_skills_path / skill_name / "SKILL.md"
        assert skill_file.exists(), f"Missing skill file: {skill_file}"

    @pytest.mark.parametrize(
        "skill_name",
        ["orchestrate", "wrapup", "reflection"],
    )
    def test_skill_file_not_empty(
        self,
        claude_skills_path: Path,
        skill_name: str,
    ) -> None:
        """Test that SKILL.md files are non-empty."""
        skill_file = claude_skills_path / skill_name / "SKILL.md"
        if not skill_file.exists():
            pytest.skip(f"Skill file not found: {skill_file}")
        content = skill_file.read_text()
        assert len(content.strip()) > 0, f"Skill file is empty: {skill_file}"


class TestSkillRules:
    """AC5: skill-rules.json is valid JSON with correct trigger patterns."""

    def test_skill_rules_exists(self, claude_skills_path: Path) -> None:
        """Test that skill-rules.json exists."""
        rules_path = claude_skills_path / "skill-rules.json"
        assert rules_path.exists(), f"Missing skill-rules.json at {rules_path}"

    def test_skill_rules_valid_json(self, claude_skills_path: Path) -> None:
        """Test that skill-rules.json is valid JSON."""
        rules_path = claude_skills_path / "skill-rules.json"
        if not rules_path.exists():
            pytest.skip("skill-rules.json not found")
        content = rules_path.read_text()
        data = json.loads(content)
        assert isinstance(data, dict)

    def test_skill_rules_has_skills_section(self, claude_skills_path: Path) -> None:
        """Test that skill-rules.json has a 'skills' section."""
        rules_path = claude_skills_path / "skill-rules.json"
        if not rules_path.exists():
            pytest.skip("skill-rules.json not found")
        data = json.loads(rules_path.read_text())
        assert "skills" in data, "Missing 'skills' section in skill-rules.json"

    def test_skill_rules_has_calm_skills(self, claude_skills_path: Path) -> None:
        """Test that skill-rules.json includes CALM skill triggers."""
        rules_path = claude_skills_path / "skill-rules.json"
        if not rules_path.exists():
            pytest.skip("skill-rules.json not found")
        data = json.loads(rules_path.read_text())
        skills = data.get("skills", {})

        # Check for CALM-specific skills
        expected_patterns = ["orchestrat", "wrapup", "reflection"]
        skill_keys = list(skills.keys())
        skill_values_str = json.dumps(skills).lower()

        for pattern in expected_patterns:
            assert pattern in skill_values_str, (
                f"No trigger for '{pattern}' found in skill-rules.json. "
                f"Available skill keys: {skill_keys}"
            )

    def test_skill_rules_has_trigger_patterns(self, claude_skills_path: Path) -> None:
        """Test that each skill entry has promptTriggers."""
        rules_path = claude_skills_path / "skill-rules.json"
        if not rules_path.exists():
            pytest.skip("skill-rules.json not found")
        data = json.loads(rules_path.read_text())
        skills = data.get("skills", {})

        for skill_name, skill_def in skills.items():
            if isinstance(skill_def, dict):
                assert "promptTriggers" in skill_def, (
                    f"Skill '{skill_name}' missing promptTriggers"
                )
                triggers = skill_def["promptTriggers"]
                # Should have either keywords or intentPatterns
                has_keywords = "keywords" in triggers and len(triggers["keywords"]) > 0
                has_patterns = "intentPatterns" in triggers and len(triggers["intentPatterns"]) > 0
                assert has_keywords or has_patterns, (
                    f"Skill '{skill_name}' has no keywords or intentPatterns"
                )
