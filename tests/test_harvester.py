"""Tests for SchemaHarvester with mocked MCP clients and failure handling."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from mcp.types import Tool

from schemaslim.config.models import Config, SseServerConfig, StdioServerConfig
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.storage.models import IndexedTool


class DummyAsyncContextManager:
    """Helper for mocking async context managers."""

    def __init__(self, enter_result: any = None):
        self.enter_result = enter_result

    async def __aenter__(self):
        return self.enter_result

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def sample_mcp_tools():
    return [
        Tool(
            name="read_file",
            description="Reads file from disk",
            inputSchema={"type": "object", "properties": {"path": {"type": "string"}}},
        ),
        Tool(
            name="list_dir",
            description="Lists directory entries",
            inputSchema={"type": "object", "properties": {"dir": {"type": "string"}}},
        ),
    ]


@pytest.mark.asyncio
async def test_harvest_stdio_server(sample_mcp_tools):
    harvester = SchemaHarvester()
    stdio_cfg = StdioServerConfig(command="python", args=["server.py"], env={"FOO": "BAR"})

    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_response = MagicMock()
    mock_response.tools = sample_mcp_tools
    mock_session.list_tools = AsyncMock(return_value=mock_response)

    with patch("schemaslim.core.harvester.stdio_client", return_value=DummyAsyncContextManager((None, None))), \
         patch("schemaslim.core.harvester.ClientSession", return_value=DummyAsyncContextManager(mock_session)):
        tools = await harvester.harvest_server("local_fs", stdio_cfg)

    assert len(tools) == 2
    assert isinstance(tools[0], IndexedTool)
    assert tools[0].namespaced_name == "local_fs__read_file"
    assert tools[0].server_name == "local_fs"
    assert tools[0].description == "Reads file from disk"
    assert tools[1].namespaced_name == "local_fs__list_dir"


@pytest.mark.asyncio
async def test_harvest_sse_server(sample_mcp_tools):
    harvester = SchemaHarvester()
    sse_cfg = SseServerConfig(url="http://127.0.0.1:8080/sse", headers={"X-Auth": "Token"})

    mock_session = MagicMock()
    mock_session.initialize = AsyncMock()
    mock_response = MagicMock()
    mock_response.tools = sample_mcp_tools[:1]
    mock_session.list_tools = AsyncMock(return_value=mock_response)

    with patch("schemaslim.core.harvester.sse_client", return_value=DummyAsyncContextManager((None, None))), \
         patch("schemaslim.core.harvester.ClientSession", return_value=DummyAsyncContextManager(mock_session)):
        tools = await harvester.harvest_server("remote_api", sse_cfg)

    assert len(tools) == 1
    assert tools[0].namespaced_name == "remote_api__read_file"


@pytest.mark.asyncio
async def test_harvest_all_with_server_failure():
    harvester = SchemaHarvester()
    config = Config(
        mcpServers={
            "healthy": StdioServerConfig(command="python", args=["ok.py"]),
            "faulty": StdioServerConfig(command="broken", args=[]),
        }
    )

    healthy_tools = [
        IndexedTool.create("healthy", "ping", "Healthcheck ping tool", {})
    ]

    async def mock_harvest(server_name, cfg, timeout=None):
        if server_name == "faulty":
            raise RuntimeError("Process crashed with exit code 127")
        return healthy_tools

    with patch.object(harvester, "harvest_server", side_effect=mock_harvest):
        tools, failures = await harvester.harvest_all(config)

    assert len(tools) == 1
    assert tools[0].namespaced_name == "healthy__ping"
    assert "faulty" in failures
    assert "RuntimeError" in failures["faulty"]
