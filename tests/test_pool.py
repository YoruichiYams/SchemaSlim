"""Tests for MCPSessionPool — persistent connection management to child MCP servers."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from mcp.types import CallToolResult, TextContent

from schemaslim.config.models import Config, StdioServerConfig, SseServerConfig
from schemaslim.core.pool import (
    MCPSessionPool,
    SessionCallError,
    SessionNotFoundError,
)


# ── Helpers ──────────────────────────────────────────────────────────────────


class DummyAsyncContextManager:
    """Helper for mocking async context managers that yield a tuple."""

    def __init__(self, enter_result=None):
        self.enter_result = enter_result

    async def __aenter__(self):
        return self.enter_result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


def _make_mock_session(tools=None) -> MagicMock:
    """Create a mock ClientSession with initialize and call_tool."""
    session = MagicMock()
    session.initialize = AsyncMock()
    session.call_tool = AsyncMock(
        return_value=CallToolResult(
            content=[TextContent(type="text", text="ok")],
            is_error=False,
        )
    )

    mock_response = MagicMock()
    mock_response.tools = tools or []
    session.list_tools = AsyncMock(return_value=mock_response)
    return session


# ── Initialization ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pool_initializes_empty_with_no_active_servers():
    pool = MCPSessionPool()
    config = Config(mcpServers={})

    await pool.initialize(config)

    assert pool.is_initialized
    assert pool.server_names == []

    await pool.shutdown()


@pytest.mark.asyncio
async def test_pool_initializes_with_active_servers():
    pool = MCPSessionPool()
    config = Config(
        mcpServers={
            "server_a": StdioServerConfig(command="python", args=["a.py"]),
            "server_b": StdioServerConfig(command="python", args=["b.py"]),
        }
    )

    mock_session_a = _make_mock_session()
    mock_session_b = _make_mock_session()
    sessions = iter([mock_session_a, mock_session_b])

    async def mock_connect(server_name, server_config):
        return next(sessions)

    with patch.object(pool, "_connect_server", side_effect=mock_connect):
        await pool.initialize(config)

    assert pool.is_initialized
    assert sorted(pool.server_names) == ["server_a", "server_b"]

    await pool.shutdown()


@pytest.mark.asyncio
async def test_pool_handles_partial_connection_failure():
    """If one server fails to connect, the others should still be available."""
    pool = MCPSessionPool()
    config = Config(
        mcpServers={
            "good": StdioServerConfig(command="python", args=["ok.py"]),
            "bad": StdioServerConfig(command="broken", args=[]),
        }
    )

    mock_session = _make_mock_session()

    async def mock_connect(server_name, server_config):
        if server_name == "bad":
            raise ConnectionError("Process crashed")
        return mock_session

    with patch.object(pool, "_connect_server", side_effect=mock_connect):
        await pool.initialize(config)

    assert pool.is_initialized
    assert pool.server_names == ["good"]

    await pool.shutdown()


@pytest.mark.asyncio
async def test_pool_double_initialize_is_noop():
    pool = MCPSessionPool()
    config = Config(mcpServers={})

    await pool.initialize(config)
    await pool.initialize(config)  # Should be a no-op

    assert pool.is_initialized
    await pool.shutdown()


# ── call_tool ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_tool_delegates_to_session():
    pool = MCPSessionPool()

    expected_result = CallToolResult(
        content=[TextContent(type="text", text="result_value")],
        is_error=False,
    )
    mock_session = _make_mock_session()
    mock_session.call_tool = AsyncMock(return_value=expected_result)

    pool._initialized = True
    pool._sessions = {"my_server": mock_session}

    result = await pool.call_tool("my_server__my_tool", {"arg1": "val1"})

    assert result is expected_result
    mock_session.call_tool.assert_awaited_once_with("my_tool", {"arg1": "val1"})

    await pool.shutdown()


@pytest.mark.asyncio
async def test_call_tool_raises_for_unknown_server():
    pool = MCPSessionPool()
    pool._initialized = True
    pool._sessions = {"existing": _make_mock_session()}

    with pytest.raises(SessionNotFoundError, match="missing"):
        await pool.call_tool("missing__tool", {})


@pytest.mark.asyncio
async def test_call_tool_raises_for_invalid_format():
    pool = MCPSessionPool()
    pool._initialized = True
    pool._sessions = {}

    with pytest.raises(ValueError, match="Invalid namespaced_name"):
        await pool.call_tool("no_separator_here", {})


@pytest.mark.asyncio
async def test_call_tool_raises_for_empty_parts():
    pool = MCPSessionPool()
    pool._initialized = True
    pool._sessions = {}

    with pytest.raises(ValueError, match="Invalid namespaced_name"):
        await pool.call_tool("__tool_only", {})


@pytest.mark.asyncio
async def test_call_tool_raises_before_init():
    pool = MCPSessionPool()

    with pytest.raises(RuntimeError, match="not been initialized"):
        await pool.call_tool("server__tool", {})


@pytest.mark.asyncio
async def test_call_tool_wraps_session_errors():
    pool = MCPSessionPool()
    pool._initialized = True

    mock_session = _make_mock_session()
    mock_session.call_tool = AsyncMock(side_effect=RuntimeError("child died"))
    pool._sessions = {"srv": mock_session}

    with pytest.raises(SessionCallError, match="child died"):
        await pool.call_tool("srv__broken_tool", {})


# ── Shutdown ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_shutdown_clears_state():
    pool = MCPSessionPool()
    config = Config(mcpServers={})
    await pool.initialize(config)
    assert pool.is_initialized

    await pool.shutdown()

    assert not pool.is_initialized
    assert pool.server_names == []


@pytest.mark.asyncio
async def test_shutdown_handles_exit_stack_errors():
    """Even if AsyncExitStack.aclose() raises, the pool should still reset."""
    pool = MCPSessionPool()
    config = Config(mcpServers={})
    await pool.initialize(config)

    # Force an error during aclose
    original_aclose = pool._exit_stack.aclose

    async def failing_aclose():
        raise OSError("cleanup failure")

    pool._exit_stack.aclose = failing_aclose

    # Should not raise
    await pool.shutdown()
    assert not pool.is_initialized
