"""Template handling for CALM installation.

Provides template discovery, validation, and copying functionality.
"""

from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


def get_templates_path() -> Path:
    """Get path to templates directory.

    Uses importlib.resources for reliable access.
    """
    return Path(str(resources.files("calm.templates")))


def _iter_template_files(category: str) -> Iterator[tuple[str, str]]:
    """Iterate over template files in a category.

    Args:
        category: Template category (roles, workflows, skills)

    Yields:
        Tuples of (relative_path, filename)
    """
    try:
        templates = resources.files("calm.templates")
        category_ref = templates.joinpath(category)

        # Check if category exists
        if not category_ref.is_dir():
            return

        # Iterate over files in category
        for item in category_ref.iterdir():
            if item.is_file() and item.name.endswith(".md"):
                yield f"{category}/{item.name}", item.name
    except (AttributeError, TypeError, FileNotFoundError):
        # Handle case where templates package doesn't exist yet
        return


def get_template_files() -> dict[str, list[str]]:
    """Get all available template files organized by category.

    Returns:
        Dict mapping category (roles, workflows, skills) to list of filenames
    """
    result: dict[str, list[str]] = {
        "roles": [],
        "workflows": [],
        "skills": [],
    }

    for category in result:
        for _, filename in _iter_template_files(category):
            result[category].append(filename)

    # Also check for config file
    try:
        templates = resources.files("calm.templates")
        config_ref = templates.joinpath("config.yaml.default")
        if config_ref.is_file():
            result["config"] = ["config.yaml.default"]
    except (AttributeError, TypeError, FileNotFoundError):
        pass

    return result


def read_template(relative_path: str) -> str:
    """Read a template file's content.

    Args:
        relative_path: Path relative to templates dir (e.g., "roles/backend.md")

    Returns:
        Template file content

    Raises:
        FileNotFoundError: If template doesn't exist
    """
    try:
        ref = resources.files("calm.templates").joinpath(relative_path)
        return ref.read_text(encoding="utf-8")
    except (AttributeError, TypeError, FileNotFoundError) as e:
        raise FileNotFoundError(
            f"Template not found: {relative_path}. Reinstall CALM: uv pip install -e ."
        ) from e


def copy_template_file(
    template_path: str,
    dest_path: Path,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[bool, str]:
    """Copy a single template file.

    Args:
        template_path: Relative path within templates package
        dest_path: Absolute destination path
        force: Overwrite if exists
        dry_run: Don't actually copy

    Returns:
        Tuple of (copied, message)
    """
    # Check if destination exists
    if dest_path.exists() and not force:
        return False, f"Skipped (exists): {dest_path}"

    if dry_run:
        if dest_path.exists():
            return True, f"Would overwrite: {dest_path}"
        return True, f"Would copy: {dest_path}"

    # Read template content
    try:
        content = read_template(template_path)
    except FileNotFoundError as e:
        return False, f"Error: {e}"

    # Ensure parent directory exists
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    # Write to destination
    try:
        dest_path.write_text(content, encoding="utf-8")
        if force and dest_path.exists():
            return True, f"Overwrote: {dest_path}"
        return True, f"Copied: {dest_path}"
    except OSError as e:
        return False, f"Error writing {dest_path}: {e}"


def copy_all_templates(
    calm_home: Path,
    force: bool = False,
    dry_run: bool = False,
) -> tuple[list[str], list[str], list[str]]:
    """Copy all templates to CALM home directory.

    Args:
        calm_home: Target directory (e.g., ~/.calm)
        force: Overwrite existing files
        dry_run: Don't actually copy

    Returns:
        Tuple of (copied_files, skipped_files, error_messages)
    """
    copied: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    # Copy roles
    roles_dir = calm_home / "roles"
    for rel_path, filename in _iter_template_files("roles"):
        dest = roles_dir / filename
        success, msg = copy_template_file(rel_path, dest, force, dry_run)
        if success:
            copied.append(msg)
        elif "Skipped" in msg:
            skipped.append(msg)
        else:
            errors.append(msg)

    # Copy workflows
    workflows_dir = calm_home / "workflows"
    for rel_path, filename in _iter_template_files("workflows"):
        dest = workflows_dir / filename
        success, msg = copy_template_file(rel_path, dest, force, dry_run)
        if success:
            copied.append(msg)
        elif "Skipped" in msg:
            skipped.append(msg)
        else:
            errors.append(msg)

    # Copy skills
    skills_dir = calm_home / "skills"
    for rel_path, filename in _iter_template_files("skills"):
        dest = skills_dir / filename
        success, msg = copy_template_file(rel_path, dest, force, dry_run)
        if success:
            copied.append(msg)
        elif "Skipped" in msg:
            skipped.append(msg)
        else:
            errors.append(msg)

    # Copy config if it doesn't exist (never overwrite config)
    config_dest = calm_home / "config.yaml"
    if not config_dest.exists():
        try:
            content = read_template("config.yaml.default")
            if dry_run:
                copied.append(f"Would copy: {config_dest}")
            else:
                config_dest.write_text(content, encoding="utf-8")
                copied.append(f"Copied: {config_dest}")
        except (FileNotFoundError, OSError) as e:
            errors.append(f"Error copying config: {e}")
    else:
        skipped.append(f"Skipped (exists): {config_dest}")

    return copied, skipped, errors


def create_directory_structure(
    calm_home: Path,
    dry_run: bool = False,
) -> list[str]:
    """Create the CALM directory structure.

    Args:
        calm_home: Base directory (e.g., ~/.calm)
        dry_run: Don't actually create directories

    Returns:
        List of created directories (or would-create messages for dry run)
    """
    directories = [
        calm_home,
        calm_home / "workflows",
        calm_home / "roles",
        calm_home / "skills",
        calm_home / "sessions",
        calm_home / "journal",
    ]

    created: list[str] = []
    for directory in directories:
        if directory.exists():
            continue
        if dry_run:
            created.append(f"Would create: {directory}")
        else:
            directory.mkdir(parents=True, exist_ok=True)
            created.append(f"Created: {directory}")

    return created
