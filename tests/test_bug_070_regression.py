"""Regression tests for BUG-070: verify_install.py and steps.py missing directory checks.

Both verify_storage_directory() (in scripts/verify_install.py) and step_verify()
(in src/calm/install/steps.py) were missing checks for skills/ and/or journal/
directories. These tests ensure the verification functions detect missing directories.
"""

from __future__ import annotations

import re
from pathlib import Path
from unittest.mock import MagicMock

from calm.install import InstallOptions, InstallResult, InstallStep
from calm.install.steps import step_verify


class TestBug070StepsVerify:
    """Regression tests for step_verify() missing journal directory check."""

    def _make_calm_home(self, tmp_path: Path) -> Path:
        """Create a CALM home with all expected directories."""
        calm_home = tmp_path / ".calm"
        for dirname in ["roles", "workflows", "skills", "sessions", "journal"]:
            (calm_home / dirname).mkdir(parents=True, exist_ok=True)
        # Create required files
        (calm_home / "metadata.db").touch()
        (calm_home / "config.yaml").touch()
        return calm_home

    def test_step_verify_passes_with_all_dirs(self, tmp_path: Path) -> None:
        """step_verify() should pass when all directories exist, including journal."""
        calm_home = self._make_calm_home(tmp_path)
        options = InstallOptions(calm_home=calm_home)
        result = InstallResult()
        output = MagicMock()

        success = step_verify(options, result, output)

        assert success is True
        assert InstallStep.VERIFY in result.steps_completed

    def test_step_verify_fails_when_journal_missing(self, tmp_path: Path) -> None:
        """BUG-070 REGRESSION: step_verify() must detect missing journal/ directory."""
        calm_home = self._make_calm_home(tmp_path)
        # Remove the journal directory
        (calm_home / "journal").rmdir()

        options = InstallOptions(calm_home=calm_home)
        result = InstallResult()
        output = MagicMock()

        success = step_verify(options, result, output)

        assert success is False, (
            "BUG-070 REGRESSION: step_verify() did not detect missing journal/ directory"
        )

    def test_step_verify_fails_when_skills_missing(self, tmp_path: Path) -> None:
        """step_verify() must detect missing skills/ directory."""
        calm_home = self._make_calm_home(tmp_path)
        # Remove the skills directory
        (calm_home / "skills").rmdir()

        options = InstallOptions(calm_home=calm_home)
        result = InstallResult()
        output = MagicMock()

        success = step_verify(options, result, output)

        assert success is False, (
            "step_verify() did not detect missing skills/ directory"
        )

    def test_step_verify_dirs_to_check_includes_journal(self) -> None:
        """Source code must include 'journal' in dirs_to_check list."""
        steps_path = Path(__file__).parent.parent / "src" / "calm" / "install" / "steps.py"
        source = steps_path.read_text()

        # Find the dirs_to_check assignment
        match = re.search(r'dirs_to_check\s*=\s*\[([^\]]+)\]', source)
        assert match is not None, "Could not find dirs_to_check in steps.py"

        dirs_str = match.group(1)
        assert '"journal"' in dirs_str, (
            "BUG-070 REGRESSION: 'journal' not in dirs_to_check list in steps.py"
        )
        assert '"skills"' in dirs_str, (
            "'skills' not in dirs_to_check list in steps.py"
        )


class TestBug070VerifyInstall:
    """Regression tests for verify_storage_directory() missing directory checks."""

    def test_verify_install_checks_skills_directory(self) -> None:
        """BUG-070 REGRESSION: verify_install.py must check for skills/ directory."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        verify_install_path = scripts_dir / "verify_install.py"
        source = verify_install_path.read_text()

        assert 'skills_dir' in source, (
            "BUG-070 REGRESSION: verify_install.py does not define skills_dir"
        )
        assert '(skills_dir, "directory")' in source, (
            "BUG-070 REGRESSION: verify_install.py does not check skills_dir"
        )

    def test_verify_install_checks_journal_directory(self) -> None:
        """BUG-070 REGRESSION: verify_install.py must check for journal/ directory."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        verify_install_path = scripts_dir / "verify_install.py"
        source = verify_install_path.read_text()

        assert 'journal_dir' in source, (
            "BUG-070 REGRESSION: verify_install.py does not define journal_dir"
        )
        assert '(journal_dir, "directory")' in source, (
            "BUG-070 REGRESSION: verify_install.py does not check journal_dir"
        )

    def test_verify_install_checks_match_create_directory_structure(self) -> None:
        """verify_install.py should check all directories that create_directory_structure creates."""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        verify_install_path = scripts_dir / "verify_install.py"
        source = verify_install_path.read_text()

        # All directories from create_directory_structure (in templates.py)
        # must have a corresponding check in verify_storage_directory
        expected_subdirs = ["sessions", "roles", "workflows", "skills", "journal"]
        for subdir in expected_subdirs:
            assert f'{subdir}_dir' in source, (
                f"verify_install.py is missing check for '{subdir}' directory"
            )
