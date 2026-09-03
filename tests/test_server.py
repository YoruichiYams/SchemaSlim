"""Tests for VirtualMCPServer — meta-tool definitions and request dispatching."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from mcp import types
from mcp.types import CallToolResult, TextContent

from schemaslim.core.server import VirtualMCPServer, META_TOOLS, SEARCH_TOOL, CALL_TOOL
from schemaslim.core.pool import SessionNotFoundError, SessionCallError
from schemaslim.storage.models import IndexedTool, SearchResult


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture
def server() -> VirtualMCPServer:
    """Create a VirtualMCPServer instance."""
    return VirtualMCPServer()


@pytest.fixture
def mock_store():
    """Mock VectorStore with hybrid_search."""
    store = MagicMock()
    store.hybrid_search = MagicMock(return_value=[])
    store.get_total_tools_count = MagicMock(return_value=5)
    store.close = MagicMock()
    return store


@pytest.fixture
def sample_search_results():
    """Sample SearchResult list for testing search formatting."""
    tool = IndexedTool.create(
        server_name="filesystem",
        tool_name="read_file",
        description="Read contents of a file",
        parameters={
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "File path to read"},
            },
            "required": ["path"],
        },
    )
    return [SearchResult(tool=tool, score=0.85, vector_score=0.82, lexical_score=0.90)]


# ── Meta-tool Definitions ───────────────────────────────────────────────────


def test_meta_tools_count():
    """Exactly 2 meta-tools should be defined."""
    assert len(META_TOOLS) == 2


def test_meta_tool_names():
    """Meta-tools must be named schemaslim_search and schemaslim_call."""
    names = {t.name for t in META_TOOLS}
    assert names == {"schemaslim_search", "schemaslim_call"}


def test_search_tool_schema():
    """schemaslim_search must require 'query' and accept optional 'limit'."""
    schema = SEARCH_TOOL.input_schema
    assert schema["type"] == "object"
    assert "query" in schema["properties"]
    assert "limit" in schema["properties"]
    assert "query" in schema["required"]


def test_call_tool_schema():
    """schemaslim_call must require 'namespaced_name' and 'arguments'."""
    schema = CALL_TOOL.input_schema
    assert schema["type"] == "object"
    assert "namespaced_name" in schema["properties"]
    assert "arguments" in schema["properties"]
    assert set(schema["required"]) == {"namespaced_name", "arguments"}


# ── list_tools Handler ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_tools_returns_exactly_two(server):
    """tools/list must return exactly the 2 meta-tools."""
    result = await server._handle_list_tools(None, None)

    assert isinstance(result, types.ListToolsResult)
    assert len(result.tools) == 2

    names = {t.name for t in result.tools}
    assert names == {"schemaslim_search", "schemaslim_call"}


# ── call_tool: schemaslim_search ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_with_results(server, mock_store, sample_search_results):
    """schemaslim_search should return formatted JSON with discovered tools."""
    mock_store.hybrid_search.return_value = sample_search_results
    server._store = mock_store

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "read a file", "limit": 3},
    )
    result = await server._handle_call_tool(None, params)

    assert isinstance(result, CallToolResult)
    assert not result.is_error
    assert len(result.content) == 1

    payload = json.loads(result.content[0].text)
    assert payload["count"] == 1
    assert payload["results"][0]["namespaced_name"] == "filesystem__read_file"
    assert payload["results"][0]["relevance_score"] == 0.85
    assert "parameters" in payload["results"][0]


@pytest.mark.asyncio
async def test_search_empty_results(server, mock_store):
    """schemaslim_search with no matches returns empty results array."""
    mock_store.hybrid_search.return_value = []
    server._store = mock_store

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "something obscure"},
    )
    result = await server._handle_call_tool(None, params)

    assert not result.is_error
    payload = json.loads(result.content[0].text)
    assert payload["count"] == 0
    assert payload["results"] == []


@pytest.mark.asyncio
async def test_search_missing_query(server, mock_store):
    """schemaslim_search without query returns error."""
    server._store = mock_store

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error


@pytest.mark.asyncio
async def test_search_no_store(server):
    """schemaslim_search without initialized VectorStore returns error."""
    server._store = None

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "test"},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "not initialized" in result.content[0].text


@pytest.mark.asyncio
async def test_search_store_error(server, mock_store):
    """schemaslim_search handles VectorStore exceptions gracefully."""
    mock_store.hybrid_search.side_effect = RuntimeError("DB corrupted")
    server._store = mock_store

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "anything"},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "DB corrupted" in result.content[0].text


# ── call_tool: schemaslim_call ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_call_delegates_to_pool(server):
    """schemaslim_call should delegate to MCPSessionPool and return its result."""
    expected = CallToolResult(
        content=[TextContent(type="text", text="tool_output")],
        is_error=False,
    )
    server._pool.call_tool = AsyncMock(return_value=expected)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={
            "namespaced_name": "server__tool",
            "arguments": {"x": 1},
        },
    )
    result = await server._handle_call_tool(None, params)

    assert result is expected
    server._pool.call_tool.assert_awaited_once_with("server__tool", {"x": 1})


@pytest.mark.asyncio
async def test_call_missing_namespaced_name(server):
    """schemaslim_call without namespaced_name returns error."""
    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"arguments": {}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "namespaced_name" in result.content[0].text


@pytest.mark.asyncio
async def test_call_invalid_arguments_type(server):
    """schemaslim_call with non-dict arguments returns error."""
    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "s__t", "arguments": "not_a_dict"},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "JSON object" in result.content[0].text


@pytest.mark.asyncio
async def test_call_session_not_found(server):
    """schemaslim_call for a missing server returns error."""
    server._pool.call_tool = AsyncMock(
        side_effect=SessionNotFoundError("No active session for server 'missing'")
    )

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "missing__tool", "arguments": {}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "missing" in result.content[0].text


@pytest.mark.asyncio
async def test_call_session_error(server):
    """schemaslim_call wraps SessionCallError as error result."""
    server._pool.call_tool = AsyncMock(
        side_effect=SessionCallError("tool crashed")
    )

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "srv__tool", "arguments": {}},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "crashed" in result.content[0].text


# ── Unknown Tool ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_tool_returns_error(server):
    """Calling a non-existent tool returns is_error=True."""
    params = types.CallToolRequestParams(
        name="nonexistent_tool",
        arguments={},
    )
    result = await server._handle_call_tool(None, params)

    assert result.is_error
    assert "Unknown tool" in result.content[0].text
    assert "schemaslim_search" in result.content[0].text
    assert "schemaslim_call" in result.content[0].text
