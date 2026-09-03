"""End-to-end integration tests for SchemaSlim full lifecycle and proxy workflow."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types

from schemaslim.benchmark.runner import BenchmarkRunner, generate_synthetic_tools
from schemaslim.core.server import VirtualMCPServer, META_TOOLS
from schemaslim.storage.models import IndexedTool
from schemaslim.storage.vector_store import VectorStore
from schemaslim.telemetry import TelemetryTracker


@pytest.mark.asyncio
async def test_full_proxy_e2e_flow(tmp_path):
    """End-to-end test of the complete SchemaSlim lifecycle.

    Tests:
      1. Isolated vector database creation and indexing.
      2. VirtualMCPServer initialization with custom telemetry tracker.
      3. MCP tools/list returning exactly the 2 meta-tools.
      4. schemaslim_search discovering indexed tools.
      5. schemaslim_call proxying to child server session pool.
      6. TelemetryTracker capturing both operations with context savings.
    """
    db_path = tmp_path / "e2e_index.db"

    # 1. Index synthetic tools using real FastEmbed
    tools = generate_synthetic_tools()

    with VectorStore(db_path=db_path) as store:
        upserted = store.upsert_tools(tools)
        assert upserted == len(tools)
        assert store.get_total_tools_count() == len(tools)

    # 2. Wire VirtualMCPServer
    tracker = TelemetryTracker()
    server = VirtualMCPServer(tracker=tracker)
    active_store = VectorStore(db_path=db_path)
    server._store = active_store

    # Mock pool execution
    expected_call_result = types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps({"rows": [{"id": 1, "name": "Alice"}]}))],
        is_error=False,
    )
    server._pool.call_tool = AsyncMock(return_value=expected_call_result)

    try:
        # 3. Step 1: tools/list
        list_res = await server._handle_list_tools(None, None)
        assert len(list_res.tools) == 2
        tool_names = {t.name for t in list_res.tools}
        assert tool_names == {"schemaslim_search", "schemaslim_call"}

        # 4. Step 2: schemaslim_search
        search_params = types.CallToolRequestParams(
            name="schemaslim_search",
            arguments={"query": "run sql query against postgres database", "limit": 5},
        )
        search_res = await server._handle_call_tool(None, search_params)
        assert not search_res.is_error
        assert len(search_res.content) == 1

        search_data = json.loads(search_res.content[0].text)
        assert search_data["count"] >= 1
        matched_servers = [r["server"] for r in search_data["results"]]
        assert "db_server" in matched_servers

        # 5. Step 3: schemaslim_call with discovered tool
        target_tool = search_data["results"][0]["namespaced_name"]
        call_params = types.CallToolRequestParams(
            name="schemaslim_call",
            arguments={
                "namespaced_name": target_tool,
                "arguments": {"query": "SELECT * FROM users;"},
            },
        )
        call_res = await server._handle_call_tool(None, call_params)
        assert not call_res.is_error
        assert "Alice" in call_res.content[0].text
        server._pool.call_tool.assert_awaited_once_with(
            target_tool, {"query": "SELECT * FROM users;"}
        )

        # 6. Step 4: Verify Telemetry
        events = tracker.get_recent_events()
        assert len(events) == 2

        # Events are returned newest first: [call, search]
        call_ev = events[0]
        search_ev = events[1]

        assert call_ev.event_type == "call"
        assert call_ev.tool_name == target_tool
        assert call_ev.status == "success"
        assert call_ev.latency_ms >= 0

        assert search_ev.event_type == "search"
        assert "sql query" in search_ev.tool_name
        assert search_ev.status == "success"
        assert search_ev.tokens_baseline > 0

        summary = tracker.get_summary()
        assert summary.total_requests == 2
        assert summary.search_requests == 1
        assert summary.call_requests == 1
        assert summary.error_requests == 0
        assert summary.total_tokens_saved > 0

    finally:
        active_store.close()


def test_benchmark_runner_e2e():
    """Verify synthetic benchmark engine runs end-to-end with realistic tools."""
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.01] * 384] * 20

    runner = BenchmarkRunner(embedder=mock_embedder)
    report = runner.run(runs=1)

    assert report.total_tools == 20
    assert report.servers_count == 4
    assert report.tokens_baseline > 1000
    assert report.avg_tokens_virtualized > 0
    assert report.avg_tokens_saved > 0
    assert report.compression_pct > 0.0
    assert len(report.queries_detail) == 5
    for q in report.queries_detail:
        assert q.latency_ms >= 0.0
        assert q.tokens_saved > 0


def test_cli_benchmark_table_output():
    """Test schemaslim benchmark CLI in table mode."""
    from typer.testing import CliRunner
    from schemaslim.cli import app

    runner = CliRunner()
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.01] * 384] * 20

    with patch("schemaslim.benchmark.BenchmarkRunner") as mock_cls:
        instance = mock_cls.return_value
        instance.run.return_value = BenchmarkRunner(embedder=mock_embedder).run(runs=1)

        result = runner.invoke(app, ["benchmark", "--runs", "1", "--output", "table"])
        assert result.exit_code == 0
        assert "Context Virtualization Benchmark Summary" in result.output
        assert "Benchmark Intent Query Breakdown" in result.output


def test_cli_benchmark_json_output():
    """Test schemaslim benchmark CLI in json mode."""
    from typer.testing import CliRunner
    from schemaslim.cli import app

    runner = CliRunner()
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.01] * 384] * 20

    with patch("schemaslim.benchmark.BenchmarkRunner") as mock_cls:
        instance = mock_cls.return_value
        instance.run.return_value = BenchmarkRunner(embedder=mock_embedder).run(runs=1)

        result = runner.invoke(app, ["benchmark", "--runs", "1", "--output", "json"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["total_tools"] == 20
        assert data["servers_count"] == 4
        assert "compression_pct" in data


def test_cli_benchmark_invalid_output():
    """Test schemaslim benchmark CLI with invalid output format."""
    from typer.testing import CliRunner
    from schemaslim.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["benchmark", "--output", "xml"])
    assert result.exit_code == 1
    assert "Invalid output format" in result.output
