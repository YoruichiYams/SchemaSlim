"""Comprehensive unit and integration tests for SchemaSlim telemetry, token tracker, and TUI dashboard."""

import concurrent.futures
import io
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from mcp import types
from rich.console import Console

from schemaslim.config.models import Config
from schemaslim.core.server import VirtualMCPServer
from schemaslim.storage.models import IndexedTool, SearchResult
from schemaslim.telemetry import (
    ProxyEvent,
    TelemetrySummary,
    TelemetryTracker,
    estimate_tokens,
    estimate_tools_tokens,
    get_tracker,
    reset_tracker,
)
from schemaslim.ui.dashboard import (
    DashboardRunner,
    create_header,
    create_metrics_panel,
    create_request_feed,
    render_dashboard,
)


# ── Token Estimation Tests ───────────────────────────────────────────────────


def test_estimate_tokens_empty_and_none():
    """Empty or None input should yield 0 tokens."""
    assert estimate_tokens(None) == 0
    assert estimate_tokens("") == 0
    assert estimate_tokens({}) == 0
    assert estimate_tokens([]) == 0


def test_estimate_tokens_text_and_dict():
    """String and dictionary token counts should track ~4 chars per token."""
    text = "Hello world!"  # 12 chars -> 3 tokens
    tokens = estimate_tokens(text)
    assert tokens == 3

    payload = {"query": "search files", "limit": 5}
    dict_tokens = estimate_tokens(payload)
    assert dict_tokens > 0


def test_estimate_tools_tokens():
    """estimate_tools_tokens handles IndexedTool, dicts, and mcp Tools."""
    t1 = IndexedTool.create(
        server_name="fs",
        tool_name="read",
        description="Read file contents",
        parameters={"type": "object", "properties": {"p": {"type": "string"}}},
    )
    t2 = types.Tool(
        name="write",
        description="Write file contents",
        input_schema={"type": "object", "properties": {"p": {"type": "string"}}},
    )
    t3 = {"name": "delete", "description": "Delete file", "parameters": {}}

    tokens = estimate_tools_tokens([t1, t2, t3])
    assert tokens > 0
    assert estimate_tools_tokens([]) == 0


# ── ProxyEvent Model Tests ───────────────────────────────────────────────────


def test_proxy_event_calculation_of_tokens_saved():
    """ProxyEvent should calculate tokens_saved automatically as max(0, baseline - actual)."""
    ev = ProxyEvent(
        event_type="search",
        tool_name="query: find files",
        latency_ms=1.5,
        tokens_baseline=5000,
        tokens_actual=400,
    )
    assert ev.tokens_saved == 4600
    assert ev.status == "success"
    assert ev.timestamp > 0

    # Negative savings (actual > baseline) clamps to 0
    ev2 = ProxyEvent(
        event_type="call",
        tool_name="fs__read",
        latency_ms=10.0,
        tokens_baseline=100,
        tokens_actual=300,
    )
    assert ev2.tokens_saved == 0


# ── TelemetryTracker Unit Tests ─────────────────────────────────────────────


def test_tracker_circular_buffer():
    """Tracker should only keep up to max_events in its ring buffer."""
    tracker = TelemetryTracker(max_events=10)
    for i in range(25):
        tracker.record_event(
            ProxyEvent(
                event_type="search",
                tool_name=f"query_{i}",
                latency_ms=1.0,
                tokens_baseline=1000,
                tokens_actual=200,
            )
        )

    events = tracker.get_recent_events()
    assert len(events) == 10
    # Newest should be first
    assert events[0].tool_name == "query_24"
    assert events[-1].tool_name == "query_15"


def test_tracker_aggregations():
    """Tracker should aggregate totals, average latencies, and compression percentage."""
    tracker = TelemetryTracker(baseline_tokens=2000)

    # 1st: search (saved 1600)
    tracker.record_event(
        ProxyEvent(
            event_type="search",
            tool_name="find tools",
            latency_ms=2.0,
            tokens_baseline=2000,
            tokens_actual=400,
            tokens_saved=1600,
            status="success",
        )
    )
    # 2nd: call (saved 1500)
    tracker.record_event(
        ProxyEvent(
            event_type="call",
            tool_name="fs__read",
            latency_ms=8.0,
            tokens_baseline=2000,
            tokens_actual=500,
            tokens_saved=1500,
            status="success",
        )
    )
    # 3rd: call error (saved 1700)
    tracker.record_event(
        ProxyEvent(
            event_type="call",
            tool_name="fs__bad",
            latency_ms=5.0,
            tokens_baseline=2000,
            tokens_actual=300,
            tokens_saved=1700,
            status="error",
        )
    )

    summary = tracker.get_summary()
    assert summary.total_requests == 3
    assert summary.search_requests == 1
    assert summary.call_requests == 2
    assert summary.error_requests == 1
    assert summary.total_tokens_baseline == 6000
    assert summary.total_tokens_actual == 1200
    assert summary.total_tokens_saved == 4800
    # Compression: 4800 / 6000 * 100 = 80.0%
    assert summary.avg_compression_pct == 80.0
    # Latencies: (2 + 8 + 5) / 3 = 5.0 ms
    assert summary.avg_latency_ms == 5.0
    assert summary.avg_search_latency_ms == 2.0
    assert summary.avg_call_latency_ms == 6.5  # (8 + 5) / 2


def test_tracker_reset():
    """Reset should clear events and zero all metrics."""
    tracker = TelemetryTracker()
    tracker.record_event(
        ProxyEvent(
            event_type="search",
            tool_name="query",
            latency_ms=1.0,
            tokens_baseline=100,
            tokens_actual=50,
        )
    )
    assert tracker.get_summary().total_requests == 1

    tracker.reset()
    assert tracker.get_summary().total_requests == 0
    assert len(tracker.get_recent_events()) == 0


def test_tracker_thread_safety():
    """Tracker should be thread-safe when updated concurrently."""
    tracker = TelemetryTracker(max_events=200)

    def record_batch(start: int):
        for i in range(50):
            tracker.record_event(
                ProxyEvent(
                    event_type="search" if i % 2 == 0 else "call",
                    tool_name=f"t_{start}_{i}",
                    latency_ms=1.0,
                    tokens_baseline=1000,
                    tokens_actual=200,
                )
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(record_batch, worker_id) for worker_id in range(4)]
        for f in futures:
            f.result()

    summary = tracker.get_summary()
    assert summary.total_requests == 200
    assert summary.search_requests == 100
    assert summary.call_requests == 100


# ── VirtualMCPServer Telemetry Integration Tests ─────────────────────────────


@pytest.mark.asyncio
async def test_server_telemetry_on_search():
    """schemaslim_search should record search event in tracker."""
    tracker = TelemetryTracker()
    server = VirtualMCPServer(tracker=tracker)

    # Mock store
    mock_store = MagicMock()
    tool = IndexedTool.create("srv", "t1", "desc", {})
    mock_store.hybrid_search.return_value = [SearchResult(tool=tool, score=0.9)]
    mock_store.get_all_tools.return_value = [tool]
    server._store = mock_store

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "find files"},
    )
    result = await server._handle_call_tool(None, params)
    assert not result.is_error

    events = tracker.get_recent_events()
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "search"
    assert ev.tool_name == "find files"
    assert ev.status == "success"
    assert ev.latency_ms >= 0.0
    assert ev.tokens_baseline > 0
    assert ev.tokens_actual > 0


@pytest.mark.asyncio
async def test_server_telemetry_on_call():
    """schemaslim_call should record call event in tracker."""
    tracker = TelemetryTracker()
    server = VirtualMCPServer(tracker=tracker)

    mock_res = types.CallToolResult(
        content=[types.TextContent(type="text", text="ok")],
        is_error=False,
    )
    server._pool.call_tool = AsyncMock(return_value=mock_res)

    params = types.CallToolRequestParams(
        name="schemaslim_call",
        arguments={"namespaced_name": "srv__tool", "arguments": {"x": 1}},
    )
    result = await server._handle_call_tool(None, params)
    assert not result.is_error

    events = tracker.get_recent_events()
    assert len(events) == 1
    ev = events[0]
    assert ev.event_type == "call"
    assert ev.tool_name == "srv__tool"
    assert ev.status == "success"


@pytest.mark.asyncio
async def test_server_telemetry_on_error():
    """Failed searches or calls should record status='error'."""
    tracker = TelemetryTracker()
    server = VirtualMCPServer(tracker=tracker)
    server._store = None  # Force search error

    params = types.CallToolRequestParams(
        name="schemaslim_search",
        arguments={"query": "test"},
    )
    result = await server._handle_call_tool(None, params)
    assert result.is_error

    events = tracker.get_recent_events()
    assert len(events) == 1
    assert events[0].status == "error"


# ── Stdout Purity & Stderr Isolation Tests ────────────────────────────────────


def test_dashboard_renders_strictly_to_stderr(capsys):
    """DashboardRunner and Console(stderr=True) must NOT write anything to sys.stdout."""
    tracker = TelemetryTracker()
    tracker.record_event(
        ProxyEvent(
            event_type="search",
            tool_name="test query",
            latency_ms=2.5,
            tokens_baseline=3000,
            tokens_actual=400,
        )
    )

    # Use custom string IO to inspect streams
    stderr_buf = io.StringIO()
    test_console = Console(file=stderr_buf, width=120, force_terminal=True, legacy_windows=False)

    dashboard = render_dashboard(tracker, active_servers=["server1", "server2"])
    test_console.print(dashboard)

    captured = capsys.readouterr()
    # CRITICAL: stdout must be completely empty!
    assert captured.out == "", "Nothing must ever be printed to stdout by dashboard"

    output_stderr = stderr_buf.getvalue()
    assert "SchemaSlim" in output_stderr
    assert "TOKEN SAVINGS" in output_stderr
    assert "Live Request Feed" in output_stderr
    assert "test query" in output_stderr


@pytest.mark.asyncio
async def test_dashboard_runner_lifecycle():
    """DashboardRunner start and stop lifecycle."""
    tracker = TelemetryTracker()
    buf = io.StringIO()
    test_console = Console(file=buf, force_terminal=False, legacy_windows=False)

    runner = DashboardRunner(
        tracker=tracker,
        active_servers=["s1"],
        console=test_console,
        refresh_interval=0.05,
    )
    await runner.start()
    assert runner._running is True
    runner.update_servers(["s1", "s2"])

    # Let it run briefly
    import asyncio
    await asyncio.sleep(0.12)
    await runner.stop()
    assert runner._running is False


# ── CLI stats Command Test ───────────────────────────────────────────────────


def test_cli_stats_command(tmp_path):
    """Test schemaslim stats command output."""
    from typer.testing import CliRunner
    from schemaslim.cli import app
    from schemaslim.config.models import Config, SchemaSlimSettings, StdioServerConfig
    from schemaslim.storage.vector_store import VectorStore

    runner = CliRunner()
    result = runner.invoke(app, ["stats", "--help"])
    assert result.exit_code == 0
    assert "Display tool repository statistics" in result.output

    # Test with real populated VectorStore
    db_file = tmp_path / "test_stats.db"
    cfg_file = tmp_path / "schemaslim.json"

    cfg = Config(
        mcpServers={
            "local_fs": StdioServerConfig(command="node", args=["server.js"]),
        },
        settings=SchemaSlimSettings(
            db_path=str(db_file),
            top_k=2,
        ),
    )
    cfg_file.write_text(cfg.model_dump_json(by_alias=True), encoding="utf-8")

    # Populate dummy tools
    mock_embedder = MagicMock()
    mock_embedder.embed.return_value = [[0.1] * 384] * 3
    with VectorStore(db_path=db_file, embedder=mock_embedder) as store:
        tools = [
            IndexedTool.create(
                server_name="local_fs",
                tool_name=f"tool_{i}",
                description=f"Description for tool {i}",
                parameters={"type": "object", "properties": {"param": {"type": "string"}}},
            )
            for i in range(3)
        ]
        store.upsert_tools(tools)

    res = runner.invoke(app, ["stats", "--config", str(cfg_file)])
    assert res.exit_code == 0
    assert "Indexed Tools in DB" in res.output
    assert "local_fs" in res.output
    assert "Savings Per LLM Turn" in res.output
