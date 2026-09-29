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


# ── Idle Session Reaper & Resource Management ────────────────────────────────


@pytest.mark.asyncio
async def test_last_accessed_timestamp_tracking():
    """Verify last_accessed timestamp updates on tool calls."""
    import asyncio

    pool = MCPSessionPool()
    config = Config(
        mcpServers={
            "srv": StdioServerConfig(command="python", args=["srv.py"]),
        }
    )
    mock_session = _make_mock_session()

    with patch.object(pool, "_connect_server", return_value=mock_session):
        await pool.initialize(config)

    t0 = pool.get_last_accessed("srv")
    assert t0 is not None
    assert t0 > 0

    await asyncio.sleep(0.02)

    await pool.call_tool("srv__test_tool", {})
    t1 = pool.get_last_accessed("srv")
    assert t1 is not None
    assert t1 > t0

    await pool.shutdown()


@pytest.mark.asyncio
async def test_idle_reaper_shuts_down_expired_session():
    """Background reaper terminates sessions exceeding idle_timeout."""
    import asyncio

    pool = MCPSessionPool(idle_timeout=0.08)
    config = Config(
        mcpServers={
            "idle_srv": StdioServerConfig(command="python", args=["idle.py"]),
            "active_srv": StdioServerConfig(command="python", args=["active.py"]),
        }
    )

    mock_idle = _make_mock_session()
    mock_active = _make_mock_session()
    sessions = {"idle_srv": mock_idle, "active_srv": mock_active}

    async def mock_connect(server_name, server_config):
        return sessions[server_name]

    with patch.object(pool, "_connect_server", side_effect=mock_connect):
        await pool.initialize(config)

    assert "idle_srv" in pool.server_names
    assert "active_srv" in pool.server_names

    # Keep active_srv refreshed while idle_srv exceeds 0.08s
    for _ in range(5):
        await asyncio.sleep(0.03)
        await pool.call_tool("active_srv__ping", {})

    # idle_srv should have been reaped
    assert "idle_srv" not in pool.server_names
    assert "active_srv" in pool.server_names

    await pool.shutdown()


@pytest.mark.asyncio
async def test_transparent_on_demand_revival():
    """Calling a reaped session automatically restarts the child process and succeeds."""
    import asyncio

    pool = MCPSessionPool(idle_timeout=0.06)
    config = Config(
        mcpServers={
            "srv": StdioServerConfig(command="python", args=["srv.py"]),
        }
    )

    connect_count = 0

    async def mock_connect(server_name, server_config):
        nonlocal connect_count
        connect_count += 1
        return _make_mock_session()

    with patch.object(pool, "_connect_server", side_effect=mock_connect):
        await pool.initialize(config)
        assert connect_count == 1
        assert "srv" in pool.server_names

        # Wait for srv to be reaped
        await asyncio.sleep(0.12)
        assert "srv" not in pool.server_names

        # Call srv - should revive transparently
        result = await pool.call_tool("srv__reborn_tool", {"foo": "bar"})
        assert not result.is_error
        assert connect_count == 2
        assert "srv" in pool.server_names

    await pool.shutdown()


@pytest.mark.asyncio
async def test_reaper_skips_in_flight_calls():
    """Reaper will not terminate a session while a tool call is actively in-flight."""
    import asyncio

    pool = MCPSessionPool(idle_timeout=0.05)
    config = Config(
        mcpServers={
            "busy": StdioServerConfig(command="python", args=["busy.py"]),
        }
    )

    slow_session = _make_mock_session()

    async def slow_call_tool(tool_name, args):
        # Simulate long-running in-flight call (0.12s, which is > idle_timeout of 0.05s)
        await asyncio.sleep(0.12)
        return CallToolResult(content=[TextContent(type="text", text="done")], is_error=False)

    slow_session.call_tool = AsyncMock(side_effect=slow_call_tool)

    with patch.object(pool, "_connect_server", return_value=slow_session):
        await pool.initialize(config)
        assert "busy" in pool.server_names

        # Launch call in background task
        task = asyncio.create_task(pool.call_tool("busy__slow_op", {}))

        # While task is running (e.g. at 0.07s > 0.05s), busy should NOT be reaped
        await asyncio.sleep(0.07)
        assert "busy" in pool.server_names

        # Wait for call to complete
        res = await task
        assert not res.is_error

    await pool.shutdown()


@pytest.mark.asyncio
async def test_shutdown_cancels_reaper_task_cleanly():
    """Pool shutdown cancels the background reaper task cleanly without unhandled errors."""
    pool = MCPSessionPool(idle_timeout=10.0)
    config = Config(
        mcpServers={
            "dummy": StdioServerConfig(command="python", args=["dummy.py"]),
        }
    )
    with patch.object(pool, "_connect_server", return_value=_make_mock_session()):
        await pool.initialize(config)

    assert pool._reaper_task is not None
    assert not pool._reaper_task.done()

    await pool.shutdown()

    assert pool._reaper_task is None
    assert not pool.is_initialized


@pytest.mark.asyncio
async def test_idle_reaper_disabled_when_none_or_nonpositive():
    """No reaper task is created when idle_timeout is None or <= 0."""
    pool_none = MCPSessionPool(idle_timeout=None)
    await pool_none.initialize(Config(mcpServers={}))
    assert pool_none._reaper_task is None
    await pool_none.shutdown()

    pool_zero = MCPSessionPool(idle_timeout=0)
    await pool_zero.initialize(Config(mcpServers={}))
    assert pool_zero._reaper_task is None
    await pool_zero.shutdown()

    pool_neg = MCPSessionPool(idle_timeout=-10.0)
    await pool_neg.initialize(Config(mcpServers={}))
    assert pool_neg._reaper_task is None
    await pool_neg.shutdown()


@pytest.mark.asyncio
async def test_idle_reaper_respects_keep_alive_exemption():
    """Servers with keep_alive=True are never reaped, even after idle_timeout."""
    import asyncio

    pool = MCPSessionPool(idle_timeout=0.06)
    config = Config(
        mcpServers={
            "ephemeral_srv": StdioServerConfig(command="python", args=["eph.py"], keep_alive=False),
            "stateful_srv": StdioServerConfig(command="python", args=["db.py"], keep_alive=True),
        }
    )

    sessions = {
        "ephemeral_srv": _make_mock_session(),
        "stateful_srv": _make_mock_session(),
    }

    async def mock_connect(server_name, server_config):
        return sessions[server_name]

    with patch.object(pool, "_connect_server", side_effect=mock_connect):
        await pool.initialize(config)

    assert "ephemeral_srv" in pool.server_names
    assert "stateful_srv" in pool.server_names

    # Wait for idle_timeout to pass without invoking either server
    await asyncio.sleep(0.12)

    # ephemeral_srv should be reaped, but stateful_srv must be preserved
    assert "ephemeral_srv" not in pool.server_names
    assert "stateful_srv" in pool.server_names

    await pool.shutdown()
