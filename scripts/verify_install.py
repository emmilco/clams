#!/usr/bin/env python3
"""Verify CLAMS installation by checking binary and imports."""

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
    clams_bin = venv_path / "bin" / "clams-server"

    if not clams_bin.exists():
        print(f"Error: clams-server not found at {clams_bin}")
        return False

    if not os.access(clams_bin, os.X_OK):
        print(f"Error: clams-server is not executable: {clams_bin}")
        return False

    # Verify basic import works using the venv's Python
    venv_python = venv_path / "bin" / "python"
    try:
        result = subprocess.run(
            [str(venv_python), "-c", "from clams.server.main import main"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=venv_path.parent
        )

        if result.returncode != 0:
            print("Error: Failed to import clams.server.main")
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
    """Verify ~/.clams directory structure."""
    clams_dir = Path.home() / ".clams"
    journal_dir = clams_dir / "journal"
    archive_dir = journal_dir / "archive"
    session_id = journal_dir / ".session_id"

    checks = [
        (clams_dir, "directory"),
        (journal_dir, "directory"),
        (archive_dir, "directory"),
        (session_id, "file"),
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

    print("\n=== Verifying CLAMS Installation ===\n")

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
