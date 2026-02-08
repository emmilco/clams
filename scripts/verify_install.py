#!/usr/bin/env python3
"""Verify CALM installation by checking binary and imports."""

import os
import subprocess
import sys
from pathlib import Path


def verify_mcp_server(venv_path: Path) -> bool:
    """Verify MCP server binary exists and basic import works.

    The MCP server is spawned by Claude Code, not run standalone,
    so we verify the binary exists and basic imports work.

    Returns:
        True if binary exists and is executable
    """
    calm_bin = venv_path / "bin" / "calm"

    if not calm_bin.exists():
        print(f"Error: calm not found at {calm_bin}")
        return False

    if not os.access(calm_bin, os.X_OK):
        print(f"Error: calm is not executable: {calm_bin}")
        return False

    # Verify basic import works using the venv's Python
    venv_python = venv_path / "bin" / "python"
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "from calm.server.main import main"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=venv_path.parent,
            stdin=subprocess.DEVNULL,
        )

        if result.returncode != 0:
            print("Error: Failed to import calm.server.main")
            print(f"stderr: {result.stderr}")
            return False

        print("✓ MCP server binary exists and is executable")
        print("✓ Basic imports verified")
        return True

    except subprocess.TimeoutExpired:
        print("Error: Import verification timeout")
        return False
    except Exception as e:
        print(f"Error: {e}")
        return False


def verify_storage_directory() -> bool:
    """Verify ~/.calm directory structure."""
    calm_dir = Path.home() / ".calm"
    sessions_dir = calm_dir / "sessions"
    roles_dir = calm_dir / "roles"
    workflows_dir = calm_dir / "workflows"
    skills_dir = calm_dir / "skills"
    journal_dir = calm_dir / "journal"

    checks = [
        (calm_dir, "directory"),
        (sessions_dir, "directory"),
        (roles_dir, "directory"),
        (workflows_dir, "directory"),
        (skills_dir, "directory"),
        (journal_dir, "directory"),
    ]

    all_good = True
    for path, kind in checks:
        if kind == "directory" and not path.is_dir():
            print(f"✗ Missing directory: {path}")
            all_good = False
        elif kind == "file" and not path.is_file():
            print(f"✗ Missing file: {path}")
            all_good = False
        else:
            print(f"✓ {path}")

    return all_good


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: verify_install.py <venv_path>")
        sys.exit(1)

    venv_path = Path(sys.argv[1])

    print("\n=== Verifying CALM Installation ===\n")

    storage_ok = verify_storage_directory()
    server_ok = verify_mcp_server(venv_path)

    if storage_ok and server_ok:
        print("\n✓ Installation verified successfully")
        sys.exit(0)
    else:
        print("\n✗ Installation verification failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
