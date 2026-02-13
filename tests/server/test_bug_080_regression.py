"""Regression tests for BUG-080: Dead MCP session/counter tools removed.

These 5 MCP tools were replaced by file-based hooks and should NOT appear
in the tool registry or tool definitions:
- start_session
- get_orphaned_ghap
- should_check_in
- increment_tool_count
- reset_tool_count

The hooks (session_start.py, pre_tool_use.py, post_tool_use.py) handle
these concerns via direct file I/O and SQLite queries instead.
"""

import pytest

from calm.server.app import _get_all_tool_definitions

# The 5 dead tool names that must NOT be in the registry
REMOVED_TOOL_NAMES = [
    "start_session",
    "get_orphaned_ghap",
    "should_check_in",
    "increment_tool_count",
    "reset_tool_count",
]


class TestDeadSessionToolsRemoved:
    """Verify BUG-080: Dead session/counter tools are not registered."""

    def test_removed_tools_not_in_definitions(self) -> None:
        """Tool definitions must not include the 5 removed session tools."""
        tool_defs = _get_all_tool_definitions()
        tool_names = {t.name for t in tool_defs}

        for removed_name in REMOVED_TOOL_NAMES:
            assert removed_name not in tool_names, (
                f"Tool \'{removed_name}\' should have been removed in BUG-080 "
                f"but is still present in _get_all_tool_definitions()"
            )

    @pytest.mark.asyncio
    async def test_removed_tools_not_in_registry(self) -> None:
        """Tool registry must not include the 5 removed session tools."""
        from calm.server.app import create_server

        _server, tool_registry = await create_server(use_mock=True)

        for removed_name in REMOVED_TOOL_NAMES:
            assert removed_name not in tool_registry, (
                f"Tool \'{removed_name}\' should have been removed in BUG-080 "
                f"but is still present in the tool registry"
            )

    def test_session_tools_module_removed(self) -> None:
        """The calm.tools.session module should no longer exist."""
        with pytest.raises(ImportError):
            import calm.tools.session  # type: ignore[import-not-found]  # noqa: F401

    def test_remaining_tools_still_present(self) -> None:
        """Verify that journal tools and other tools are still present."""
        tool_defs = _get_all_tool_definitions()
        tool_names = {t.name for t in tool_defs}

        # Journal tools should still be present
        assert "store_journal_entry" in tool_names
        assert "list_journal_entries" in tool_names
        assert "get_journal_entry" in tool_names
        assert "mark_entries_reflected" in tool_names

        # GHAP tools should still be present
        assert "start_ghap" in tool_names
        assert "get_active_ghap" in tool_names
        assert "resolve_ghap" in tool_names

        # Ping should still be present
        assert "ping" in tool_names

    def test_tool_count_is_29(self) -> None:
        """Verify we have exactly 29 tools (34 - 5 removed)."""
        tool_defs = _get_all_tool_definitions()
        assert len(tool_defs) == 29, (
            f"Expected 29 tools after removing 5 session tools, "
            f"but found {len(tool_defs)}"
        )


class TestPingTool:
    """Verify ping tool returns real health check data."""

    @pytest.mark.asyncio
    async def test_ping_returns_healthy_status(self) -> None:
        """Ping tool should return status, server name, and version."""
        from calm.server.app import create_server

        _server, tool_registry = await create_server(use_mock=True)
        ping = tool_registry["ping"]

        result = await ping()

        assert result["status"] == "healthy"
        assert result["server"] == "calm"
        assert "version" in result
        assert result["version"]  # Not empty

    @pytest.mark.asyncio
    async def test_ping_is_not_stub(self) -> None:
        """Ping tool must not return not_implemented or stub response."""
        from calm.server.app import create_server

        _server, tool_registry = await create_server(use_mock=True)
        ping = tool_registry["ping"]

        result = await ping()

        assert result.get("status") != "not_implemented"
        assert "error" not in result
