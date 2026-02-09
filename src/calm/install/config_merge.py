"""JSON configuration merging utilities.

Provides safe JSON config reading, merging, and atomic writing.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from calm.config import settings as calm_settings


class ConfigError(Exception):
    """Error during config manipulation."""

    pass


def read_json_config(path: Path) -> dict[str, Any]:
    """Read JSON config file, creating empty dict if missing.

    Args:
        path: Path to JSON file

    Returns:
        Parsed JSON as dict

    Raises:
        ConfigError: If file exists but is invalid JSON
    """
    if not path.exists():
        return {}

    try:
        content = path.read_text(encoding="utf-8")
        if not content.strip():
            return {}
        data = json.loads(content)
        if not isinstance(data, dict):
            raise ConfigError(
                f"Invalid JSON in {path}: expected object, got {type(data).__name__}"
            )
        return data
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in {path}: {e}") from e


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically (write temp, rename).

    Args:
        path: Target path
        data: Data to write

    Raises:
        ConfigError: If write fails
    """
    # Ensure parent directory exists
    path.parent.mkdir(parents=True, exist_ok=True)

    # Use same directory for temp file (rename must be same filesystem)
    try:
        temp_fd, temp_path = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
        )
    except OSError as e:
        raise ConfigError(f"Cannot create temp file in {path.parent}: {e}") from e

    try:
        with os.fdopen(temp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")  # Trailing newline
            f.flush()
            os.fsync(f.fileno())

        # Atomic rename
        os.replace(temp_path, path)
    except Exception as e:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise ConfigError(f"Failed to write {path}: {e}") from e


def merge_mcp_server(
    config: dict[str, Any],
    mcp_url: str,
) -> dict[str, Any]:
    """Merge CALM MCP server into config.

    Args:
        config: Existing claude.json content
        mcp_url: Streamable HTTP endpoint URL (e.g., "http://127.0.0.1:6335/mcp")

    Returns:
        Updated config dict (original not mutated)
    """
    result = config.copy()

    # Ensure mcpServers exists
    if "mcpServers" not in result:
        result["mcpServers"] = {}
    else:
        # Deep copy to avoid mutating original
        result["mcpServers"] = dict(result["mcpServers"])

    # Add/update calm server with Streamable HTTP transport
    result["mcpServers"]["calm"] = {
        "type": "http",
        "url": mcp_url,
    }

    return result


def _is_calm_hook(hook: dict[str, Any]) -> bool:
    """Check if a hook is a CALM hook."""
    hooks = hook.get("hooks", [])
    for h in hooks:
        cmd = h.get("command", "")
        if "calm.hooks." in cmd or "python -m calm.hooks" in cmd:
            return True
    return False


def _is_old_clams_hook(hook: dict[str, Any]) -> bool:
    """Check if a hook is an old clams_scripts hook."""
    hooks = hook.get("hooks", [])
    for h in hooks:
        cmd = h.get("command", "")
        if "clams_scripts/hooks" in cmd:
            return True
    return False


def _clean_old_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    """Remove old clams_scripts hook references."""
    result: dict[str, Any] = {}
    for hook_type, hook_list in hooks.items():
        if not isinstance(hook_list, list):
            result[hook_type] = hook_list
            continue
        cleaned = [h for h in hook_list if not _is_old_clams_hook(h)]
        result[hook_type] = cleaned
    return result


def merge_hooks(
    settings: dict[str, Any],
    clean_old: bool = True,
) -> dict[str, Any]:
    """Merge CALM hooks into settings.

    Args:
        settings: Existing settings.json content
        clean_old: Remove old clams_scripts hook references

    Returns:
        Updated settings dict (original not mutated)
    """
    result = settings.copy()

    # Define CALM hooks
    calm_hooks: dict[str, list[dict[str, Any]]] = {
        "SessionStart": [
            {
                "matcher": "startup",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.session_start"}
                ],
            }
        ],
        "UserPromptSubmit": [
            {
                "hooks": [
                    {
                        "type": "command",
                        "command": "python -m calm.hooks.user_prompt_submit",
                    }
                ]
            }
        ],
        "PreToolUse": [
            {
                "matcher": "*",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.pre_tool_use"}
                ],
            }
        ],
        "PostToolUse": [
            {
                "matcher": "Bash(pytest:*)|Bash(npm test:*)|Bash(cargo test:*)",
                "hooks": [
                    {"type": "command", "command": "python -m calm.hooks.post_tool_use"}
                ],
            }
        ],
    }

    # Get or create hooks section
    existing_hooks = result.get("hooks", {})
    if not isinstance(existing_hooks, dict):
        existing_hooks = {}
    result["hooks"] = dict(existing_hooks)

    # Clean old references if requested
    if clean_old:
        result["hooks"] = _clean_old_hooks(result["hooks"])

    # Merge each hook type
    for hook_type, hook_list in calm_hooks.items():
        if hook_type not in result["hooks"]:
            result["hooks"][hook_type] = []
        else:
            result["hooks"][hook_type] = list(result["hooks"][hook_type])

        # Remove any existing CALM hooks (for idempotency)
        result["hooks"][hook_type] = [
            h for h in result["hooks"][hook_type] if not _is_calm_hook(h)
        ]

        # Add new CALM hooks
        result["hooks"][hook_type].extend(hook_list)

    return result


def register_mcp_server(
    claude_json_path: Path,
    dry_run: bool = False,
) -> str:
    """Register CALM MCP server in claude.json.

    Builds the Streamable HTTP URL from calm.config.settings
    (server_host, server_port) and writes it into the claude.json
    MCP server registration.

    Args:
        claude_json_path: Path to ~/.claude.json
        dry_run: If True, don't write changes

    Returns:
        Description of what was done

    Raises:
        ConfigError: If registration fails
    """
    # Build Streamable HTTP URL from settings
    mcp_url = f"http://{calm_settings.server_host}:{calm_settings.server_port}/mcp"

    # Read existing config
    config = read_json_config(claude_json_path)

    # Merge CALM server
    updated = merge_mcp_server(config, mcp_url)

    if dry_run:
        return f"Would update {claude_json_path} with CALM MCP server"

    # Write atomically
    atomic_write_json(claude_json_path, updated)

    return f"Registered CALM MCP server in {claude_json_path}"


def register_hooks(
    settings_path: Path,
    dry_run: bool = False,
) -> str:
    """Register CALM hooks in settings.json.

    Args:
        settings_path: Path to ~/.claude/settings.json
        dry_run: If True, don't write changes

    Returns:
        Description of what was done

    Raises:
        ConfigError: If registration fails
    """
    # Ensure parent directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    # Read existing settings
    settings = read_json_config(settings_path)

    # Merge hooks
    updated = merge_hooks(settings, clean_old=True)

    if dry_run:
        return f"Would update {settings_path} with CALM hooks"

    # Write atomically
    atomic_write_json(settings_path, updated)

    return f"Registered CALM hooks in {settings_path}"


# --- Claude Code Skill Registration ---

# Skill definitions: (skill_name, directory_name, trigger_keywords, intent_patterns)
CALM_SKILLS: list[tuple[str, str, list[str], list[str]]] = [
    (
        "orchestrate",
        "orchestrate",
        [
            "orchestrate",
            "/orchestrate",
            "start orchestration",
            "activate workflow",
            "CALM orchestration",
            "orchestration mode",
            "activate orchestration",
        ],
        [
            "(start|activate|enter|begin|run).*?orchestrat",
            "/orchestrate",
            "(CALM|calm).*?(mode|workflow|orchestrat)",
        ],
    ),
    (
        "wrapup",
        "wrapup",
        [
            "wrapup",
            "/wrapup",
            "wrap up",
            "end session",
            "session wrapup",
            "session handoff",
        ],
        [
            "(end|wrap|close|finish).*?session",
            "/wrapup",
            "session.*?(wrapup|wrap up|handoff|end)",
        ],
    ),
    (
        "reflection",
        "reflection",
        [
            "reflection",
            "/reflection",
            "reflect",
            "review sessions",
            "extract learnings",
            "session reflection",
        ],
        [
            "(reflect|review).*?(session|experience|learning)",
            "/reflection",
            "extract.*?learning",
        ],
    ),
]


def merge_skill_rules(
    rules: dict[str, Any],
) -> dict[str, Any]:
    """Merge CALM skill triggers into skill-rules.json.

    Args:
        rules: Existing skill-rules.json content

    Returns:
        Updated rules dict (original not mutated)
    """
    result = dict(rules)

    # Ensure skills section exists
    if "skills" not in result:
        result["skills"] = {}
    else:
        result["skills"] = dict(result["skills"])

    for skill_name, _dir_name, keywords, intent_patterns in CALM_SKILLS:
        rule_key = f"calm-{skill_name}"
        result["skills"][rule_key] = {
            "type": "domain",
            "enforcement": "suggest",
            "priority": "high",
            "description": f"CALM {skill_name} skill",
            "promptTriggers": {
                "keywords": keywords,
                "intentPatterns": intent_patterns,
            },
        }

    return result


def install_claude_code_skills(
    claude_skills_dir: Path,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Install CALM skill wrappers into ~/.claude/skills/.

    Creates thin SKILL.md wrappers that Claude Code can discover,
    pointing back to the CALM skill system.

    Args:
        claude_skills_dir: Path to ~/.claude/skills/
        force: Overwrite existing skill files
        dry_run: Don't actually write files

    Returns:
        Tuple of (installed, skipped, errors)
    """
    from calm.install.templates import read_template

    installed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    for skill_name, dir_name, _keywords, _patterns in CALM_SKILLS:
        skill_dir = claude_skills_dir / dir_name
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists() and not force:
            skipped.append(f"Skipped (exists): {skill_file}")
            continue

        if dry_run:
            if skill_file.exists():
                installed.append(f"Would overwrite: {skill_file}")
            else:
                installed.append(f"Would install: {skill_file}")
            continue

        try:
            # Read the template
            template_path = f"claude_skills/{skill_name}_SKILL.md"
            content = read_template(template_path)

            # Create directory and write file
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_file.write_text(content, encoding="utf-8")
            installed.append(f"Installed: {skill_file}")
        except (FileNotFoundError, OSError) as e:
            errors.append(f"Error installing {skill_name} skill: {e}")

    return installed, skipped, errors


def register_claude_code_skills(
    claude_skills_dir: Path,
    skill_rules_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> str:
    """Register CALM skills in Claude Code.

    Installs skill wrappers to ~/.claude/skills/ and updates
    skill-rules.json with trigger patterns.

    Args:
        claude_skills_dir: Path to ~/.claude/skills/
        skill_rules_path: Path to ~/.claude/skills/skill-rules.json
        force: Overwrite existing files
        dry_run: If True, don't write changes

    Returns:
        Description of what was done

    Raises:
        ConfigError: If registration fails
    """
    messages: list[str] = []

    # Install skill wrapper files
    installed, skipped, errors = install_claude_code_skills(
        claude_skills_dir, force=force, dry_run=dry_run
    )
    messages.extend(installed)
    messages.extend(skipped)

    if errors:
        raise ConfigError(f"Failed to install skill wrappers: {'; '.join(errors)}")

    # Update skill-rules.json
    rules = read_json_config(skill_rules_path)
    updated_rules = merge_skill_rules(rules)

    if dry_run:
        messages.append(f"Would update {skill_rules_path} with CALM skill triggers")
    else:
        atomic_write_json(skill_rules_path, updated_rules)
        messages.append(f"Updated {skill_rules_path} with CALM skill triggers")

    summary = "; ".join(messages) if messages else "No changes needed"
    return summary
