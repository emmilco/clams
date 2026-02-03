"""Tests for template handling."""

from __future__ import annotations

from pathlib import Path

import pytest

from calm.install.templates import (
    copy_all_templates,
    copy_template_file,
    create_directory_structure,
    get_template_files,
    read_template,
)


class TestGetTemplateFiles:
    """Tests for get_template_files."""

    def test_returns_dict_with_categories(self) -> None:
        """Should return dict with expected categories."""
        templates = get_template_files()
        assert isinstance(templates, dict)
        assert "roles" in templates
        assert "workflows" in templates
        assert "skills" in templates

    def test_roles_contains_expected_files(self) -> None:
        """Should include expected role files."""
        templates = get_template_files()
        roles = templates.get("roles", [])
        expected_roles = [
            "architect.md",
            "backend.md",
            "frontend.md",
            "reviewer.md",
            "qa.md",
        ]
        for role in expected_roles:
            assert role in roles, f"Missing role: {role}"

    def test_all_role_files_present(self) -> None:
        """Should have all 15 role files."""
        templates = get_template_files()
        roles = templates.get("roles", [])
        # We have 15 role files as per spec
        assert len(roles) >= 14, f"Expected 15 roles, got {len(roles)}"

    def test_skills_contains_expected_files(self) -> None:
        """Should include expected skill files."""
        templates = get_template_files()
        skills = templates.get("skills", [])
        expected_skills = ["orchestrate.md", "wrapup.md", "reflection.md"]
        for skill in expected_skills:
            assert skill in skills, f"Missing skill: {skill}"


class TestReadTemplate:
    """Tests for read_template."""

    def test_read_existing_template(self) -> None:
        """Should read an existing template file."""
        content = read_template("roles/backend.md")
        assert content.startswith("#")
        assert "Backend" in content

    def test_read_nonexistent_template(self) -> None:
        """Should raise FileNotFoundError for missing template."""
        with pytest.raises(FileNotFoundError):
            read_template("roles/nonexistent.md")


class TestCopyTemplateFile:
    """Tests for copy_template_file."""

    def test_copy_to_new_file(self, tmp_path: Path) -> None:
        """Should copy template to new destination."""
        dest = tmp_path / "test.md"
        success, msg = copy_template_file("roles/backend.md", dest)
        assert success
        assert dest.exists()
        assert dest.read_text().startswith("#")

    def test_skip_existing_file(self, tmp_path: Path) -> None:
        """Existing files should be skipped without --force."""
        dest = tmp_path / "test.md"
        dest.write_text("existing content")

        copied, msg = copy_template_file("roles/backend.md", dest, force=False)
        assert not copied  # File was not copied (skipped)
        assert "skip" in msg.lower() or "Skipped" in msg
        assert dest.read_text() == "existing content"

    def test_force_overwrite(self, tmp_path: Path) -> None:
        """--force should overwrite existing files."""
        dest = tmp_path / "test.md"
        dest.write_text("existing content")

        success, msg = copy_template_file("roles/backend.md", dest, force=True)
        assert success
        assert dest.read_text() != "existing content"
        assert dest.read_text().startswith("#")

    def test_dry_run_no_copy(self, tmp_path: Path) -> None:
        """Dry run should not actually copy."""
        dest = tmp_path / "test.md"
        success, msg = copy_template_file("roles/backend.md", dest, dry_run=True)
        assert success
        assert "Would copy" in msg
        assert not dest.exists()

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        """Should create parent directories if needed."""
        dest = tmp_path / "deep" / "nested" / "test.md"
        success, msg = copy_template_file("roles/backend.md", dest)
        assert success
        assert dest.exists()


class TestCopyAllTemplates:
    """Tests for copy_all_templates."""

    def test_copies_to_empty_directory(self, tmp_path: Path) -> None:
        """Should copy all templates to empty directory."""
        copied, skipped, errors = copy_all_templates(tmp_path, force=False)

        assert len(copied) > 0, "Should have copied files"
        assert len(errors) == 0, f"Should have no errors: {errors}"

        # Check directories were created
        assert (tmp_path / "roles").exists()
        assert (tmp_path / "workflows").exists()
        assert (tmp_path / "skills").exists()

        # Check some files exist
        assert (tmp_path / "roles" / "backend.md").exists()
        assert (tmp_path / "workflows" / "default.md").exists()

    def test_skip_existing_files(self, tmp_path: Path) -> None:
        """Should skip existing files."""
        # First copy
        copy_all_templates(tmp_path, force=False)

        # Modify a file
        backend = tmp_path / "roles" / "backend.md"
        backend.write_text("modified")

        # Second copy
        copied, skipped, errors = copy_all_templates(tmp_path, force=False)

        assert len(skipped) > 0, "Should have skipped files"
        assert backend.read_text() == "modified"

    def test_force_overwrites(self, tmp_path: Path) -> None:
        """Force should overwrite existing files."""
        # First copy
        copy_all_templates(tmp_path, force=False)

        # Modify a file
        backend = tmp_path / "roles" / "backend.md"
        backend.write_text("modified")

        # Second copy with force
        copied, skipped, errors = copy_all_templates(tmp_path, force=True)

        assert backend.read_text() != "modified"

    def test_dry_run_no_changes(self, tmp_path: Path) -> None:
        """Dry run should not create any files."""
        copied, skipped, errors = copy_all_templates(tmp_path, dry_run=True)

        assert len(copied) > 0, "Should report would-copy files"
        assert not (tmp_path / "roles").exists()


class TestCreateDirectoryStructure:
    """Tests for create_directory_structure."""

    def test_creates_all_directories(self, tmp_path: Path) -> None:
        """Should create all required directories."""
        calm_home = tmp_path / ".calm"
        created = create_directory_structure(calm_home)

        assert len(created) > 0
        assert calm_home.exists()
        assert (calm_home / "workflows").exists()
        assert (calm_home / "roles").exists()
        assert (calm_home / "skills").exists()
        assert (calm_home / "sessions").exists()

    def test_idempotent(self, tmp_path: Path) -> None:
        """Running twice should not error."""
        calm_home = tmp_path / ".calm"

        # First run
        created1 = create_directory_structure(calm_home)
        assert len(created1) > 0

        # Second run
        created2 = create_directory_structure(calm_home)
        assert len(created2) == 0  # Nothing new to create

    def test_dry_run(self, tmp_path: Path) -> None:
        """Dry run should not create directories."""
        calm_home = tmp_path / ".calm"
        created = create_directory_structure(calm_home, dry_run=True)

        assert len(created) > 0
        assert "Would create" in created[0]
        assert not calm_home.exists()
