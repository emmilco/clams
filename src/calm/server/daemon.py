"""CALM server daemon management.

This module handles starting, stopping, and monitoring the CALM server daemon.
Uses subprocess spawning (not fork) to avoid macOS MPS issues.
"""

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from calm.config import settings


def get_python_executable() -> str:
    """Get the correct Python executable, preferring the virtualenv Python.

    When the CLI is invoked from global Python (outside a virtualenv),
    sys.executable points to the system Python which may not have CALM's
    dependencies installed. This function resolves the correct interpreter:

    1. If VIRTUAL_ENV env var is set, use ``{VIRTUAL_ENV}/bin/python``.
    2. If sys.executable lives inside a venv (detected via ``pyvenv.cfg``
       in a parent directory), use sys.executable as-is.
    3. Fall back to sys.executable when neither heuristic matches.

    Returns:
        Absolute path to the Python interpreter that should be used
        to spawn CALM subprocesses.
    """
    # Strategy 1: VIRTUAL_ENV environment variable
    virtual_env = os.environ.get("VIRTUAL_ENV")
    if virtual_env:
        venv_python = Path(virtual_env) / "bin" / "python"
        if venv_python.is_file():
            return str(venv_python)

    # Strategy 2: Walk up from sys.executable looking for pyvenv.cfg
    exe_path = Path(sys.executable).resolve()
    # In a typical venv layout the executable is at
    # <venv>/bin/python  and  pyvenv.cfg sits at <venv>/pyvenv.cfg
    for parent in exe_path.parents:
        if (parent / "pyvenv.cfg").is_file():
            return str(exe_path)

    # Strategy 3: Fallback
    return sys.executable


def get_pid_file() -> Path:
    """Get the PID file path."""
    return Path(settings.pid_file).expanduser()


def get_log_file() -> Path:
    """Get the log file path."""
    return Path(settings.log_file).expanduser()


def get_server_pid() -> int | None:
    """Get the running server's PID.

    Returns:
        PID if server is running, None otherwise
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return None

    try:
        return int(pid_file.read_text().strip())
    except (ValueError, OSError):
        return None


def is_server_running() -> bool:
    """Check if the server is running.

    Returns:
        True if PID file exists and process is running
    """
    pid = get_server_pid()
    if pid is None:
        return False

    try:
        # Signal 0 doesn't kill, just checks if process exists
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def start_daemon() -> None:
    """Start the CALM server as a background daemon.

    Uses subprocess.Popen to avoid fork issues on macOS.
    The parent process exits immediately, leaving the daemon running.
    """
    log_file = get_log_file()
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Build command to run the server
    cmd = [
        get_python_executable(),
        "-m", "calm.server.main",
        "--host", settings.server_host,
        "--port", str(settings.server_port),
    ]

    # Open log file for output
    with open(log_file, "w") as log_out:
        with open("/dev/null") as devnull:
            # Start subprocess detached from this process
            proc = subprocess.Popen(
                cmd,
                stdin=devnull,
                stdout=log_out,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # Creates new session (like setsid)
            )

    # Write child PID to file
    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(proc.pid))

    print(f"Daemon started with PID {proc.pid}")
    print(f"Log file: {log_file}")


def run_foreground() -> None:
    """Run the server in the foreground (for debugging).

    This runs the server in the current process without daemonizing.
    """
    from calm.server.main import run_server
    run_server(settings.server_host, settings.server_port)


def stop_server() -> bool:
    """Stop the running server.

    Returns:
        True if server was stopped, False if not running
    """
    pid_file = get_pid_file()
    if not pid_file.exists():
        return False

    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)

        # Wait for process to exit (up to 5 seconds)
        for _ in range(50):
            try:
                os.kill(pid, 0)
                time.sleep(0.1)
            except (OSError, ProcessLookupError):
                # Process exited
                break

        # Force kill if still running
        try:
            os.kill(pid, signal.SIGKILL)
        except (OSError, ProcessLookupError):
            pass

        # Clean up PID file if server didn't
        if pid_file.exists():
            pid_file.unlink()

        return True
    except (ValueError, OSError, ProcessLookupError):
        # Invalid PID or process not running
        if pid_file.exists():
            pid_file.unlink()
        return False
