# SPEC-025: Production Command Verification in Tests (R6-C)

## Background

SPEC-024 (Configuration Parity Verification) established that tests should use production configuration values. This spec extends that work to ensure integration tests use the exact same commands and entry points as production.

BUG-033 showed command mismatches between different parts of the system. This spec ensures integration tests use the exact same commands as production hooks.

## Problem Statement

Integration tests may use commands that differ from production, causing:
- "Works in test, fails in production" scenarios
- Missed bugs related to entry point configuration
- Inconsistent behavior between test and production environments

Currently:
- Tests may use various ad-hoc commands to start the server
- Hooks use `"$REPO_ROOT/.venv/bin/python" -m clams.server.main --http --daemon` for daemon mode
- MCP tests use `.venv/bin/clams-server` for stdio transport (entry point from pyproject.toml)
- No utility ensures consistency between test and production commands

## Goals

1. Create a utility function that returns the canonical server command
2. Support both entry point styles (module invocation and binary)
3. Ensure all integration tests use this utility
4. Document the parity requirement in test files
5. Verify test commands match hook commands

## Non-Goals

- Changing the actual production command
- Modifying hook scripts (they already use the correct command)
- Adding new test infrastructure beyond the utility function

## Solution Overview

### 1. Canonical Command Utility

Create utility in `tests/conftest.py`:

```python
def get_server_command(
    *,
    http: bool = True,
    daemon: bool = False,
    host: str | None = None,
    port: int | None = None,
    use_module: bool = False,
) -> list[str]:
    """Get canonical server start command for tests.

    IMPORTANT: This function returns commands matching production usage.

    Production hooks (session_start.sh) use module invocation for daemon mode:
        "$REPO_ROOT/.venv/bin/python" -m clams.server.main --http --daemon

    MCP tests use the binary entry point for stdio transport:
        .venv/bin/clams-server

    Both are equivalent - they invoke the same entry point with the same venv.

    Args:
        http: Include --http flag (default True)
        daemon: Include --daemon flag (default False for tests)
        host: Optional --host value
        port: Optional --port value
        use_module: If True, return python -m style (matches hooks).
                   If False (default), return clams-server binary style.

    Returns:
        Command as list suitable for subprocess.run() or StdioServerParameters

    Reference: SPEC-025, BUG-033
    """
    repo_root = Path(__file__).parent.parent
    venv_python = repo_root / ".venv" / "bin" / "python"
    venv_server = repo_root / ".venv" / "bin" / "clams-server"

    if use_module:
        # Module invocation style (matches session_start.sh hooks)
        if venv_python.exists():
            cmd = [str(venv_python), "-m", "clams.server.main"]
        else:
            import warnings
            warnings.warn(
                f"Venv python not found at {venv_python}. "
                "Using system python which may differ from production.",
                UserWarning,
                stacklevel=2,
            )
            cmd = ["python", "-m", "clams.server.main"]
    else:
        # Binary invocation style (common in MCP tests)
        if venv_server.exists():
            cmd = [str(venv_server)]
        else:
            import warnings
            warnings.warn(
                f"Venv clams-server not found at {venv_server}. "
                "Using PATH lookup which may differ from production.",
                UserWarning,
                stacklevel=2,
            )
            cmd = ["clams-server"]

    if http:
        cmd.append("--http")
    if daemon:
        cmd.append("--daemon")
    if host:
        cmd.extend(["--host", host])
    if port is not None:
        cmd.extend(["--port", str(port)])

    return cmd
```

### 2. Test Migration

Audit and update integration tests to use the utility:
- `tests/integration/` - any tests that start the server
- `tests/hooks/` - tests that verify hook behavior

### 3. Verification Tests

Add tests in `tests/infrastructure/test_command_parity.py` that verify the utility returns commands matching production:

```python
def test_module_command_matches_hooks():
    """Verify get_server_command(use_module=True) matches session_start.sh."""
    # Read hook script
    hook_path = Path(__file__).parent.parent.parent / "clams/hooks/session_start.sh"
    hook_content = hook_path.read_text()

    # Verify hook uses the expected pattern:
    # "$REPO_ROOT/.venv/bin/python" -m clams.server.main --http --daemon
    assert ".venv/bin/python" in hook_content
    assert "-m clams.server.main" in hook_content
    assert "--http" in hook_content
    assert "--daemon" in hook_content

    # Verify our utility produces matching command structure
    test_cmd = get_server_command(http=True, daemon=True, use_module=True)
    assert "-m" in test_cmd
    assert "clams.server.main" in test_cmd
    assert "--http" in test_cmd
    assert "--daemon" in test_cmd


def test_binary_command_matches_mcp_tests():
    """Verify get_server_command() matches test_mcp_protocol.py pattern."""
    from clams.server.config import ServerSettings

    settings = ServerSettings()

    # Default (use_module=False) should return clams-server binary
    test_cmd = get_server_command(http=False)
    assert "clams-server" in test_cmd[0]

    # Should match ServerSettings.server_command
    assert settings.server_command in test_cmd[0]
```

## Acceptance Criteria

- [ ] `get_server_command()` utility exists in `tests/conftest.py`
- [ ] Utility returns command matching hook pattern when `use_module=True`
- [ ] Utility returns clams-server binary when `use_module=False` (default)
- [ ] Utility supports `http`, `daemon`, `host`, `port` parameters matching hook usage
- [ ] Utility logs warning when falling back to system python/PATH lookup
- [ ] Verification tests exist in `tests/infrastructure/test_command_parity.py`
- [ ] Tests verify utility output matches session_start.sh command structure
- [ ] Docstring explains parity requirement and references session_start.sh

## Testing Requirements

- Test that utility returns canonical command when `.venv/bin/python` exists
- Test that utility returns clams-server binary when `.venv/bin/clams-server` exists
- Test that utility falls back gracefully when venv not present
- Test that warns on fallback
- Test that `use_module=True` output matches hook command structure
- Test that `use_module=False` output matches MCP test command structure

## Dependencies

- SPEC-024 (Configuration Parity Verification) - DONE

## References

- BUG-033: Hook server command mismatch
- R6-C in `planning_docs/tickets/recommendations-r5-r8.md`
