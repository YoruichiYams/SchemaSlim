"""Virtualizing MCP server that exposes schemaslim_search and schemaslim_call meta-tools."""

import json
import sys
import time
from typing import Any, Optional

from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from schemaslim.config.models import Config
from schemaslim.core.pool import MCPSessionPool, SessionCallError, SessionNotFoundError
from schemaslim.storage.vector_store import VectorStore
from schemaslim.telemetry import (
    ProxyEvent,
    TelemetryTracker,
    estimate_tokens,
    estimate_tools_tokens,
    get_tracker,
)
from schemaslim.utils.logger import get_logger

logger = get_logger("server")

# ── Meta-tool definitions ─────────────────────────────────────────────────────

SEARCH_TOOL = types.Tool(
    name="schemaslim_search",
    description=(
        "Search and discover available tools based on your intent. "
        "Returns tool schemas and namespaced IDs needed for invocation."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Natural language description of the task or intent.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum number of tools to return.",
                "default": 3,
            },
        },
        "required": ["query"],
    },
)

CALL_TOOL = types.Tool(
    name="schemaslim_call",
    description="Execute a discovered tool using its namespaced_name and arguments.",
    input_schema={
        "type": "object",
        "properties": {
            "namespaced_name": {
                "type": "string",
                "description": "Fully qualified tool identifier returned by schemaslim_search (format: server__tool).",
            },
            "arguments": {
                "type": "object",
                "description": "Arguments to pass to the target tool.",
                "default": {},
            },
        },
        "required": ["namespaced_name", "arguments"],
    },
)

META_TOOLS = [SEARCH_TOOL, CALL_TOOL]
META_TOOLS_TOKENS = estimate_tools_tokens(META_TOOLS)


# ── VirtualMCPServer ─────────────────────────────────────────────────────────


class VirtualMCPServer:
    """MCP server that virtualizes child servers behind semantic search + lazy proxy.

    Exposes exactly two meta-tools:
      - schemaslim_search: semantic search over indexed tool schemas
      - schemaslim_call: proxy execution to the matched child server
    """

    def __init__(
        self,
        tracker: Optional[TelemetryTracker] = None,
        pool: Optional[MCPSessionPool] = None,
    ) -> None:
        self._pool: MCPSessionPool = pool or MCPSessionPool()
        self._store: VectorStore | None = None
        self._tracker: TelemetryTracker = tracker or get_tracker()
        self._baseline_tokens: int = 0

    def _get_baseline_tokens(self) -> int:
        """Get or compute baseline token footprint for all available tools."""
        if self._baseline_tokens > 0:
            return self._baseline_tokens
        if self._store is not None:
            try:
                all_tools = self._store.get_all_tools()
                self._baseline_tokens = estimate_tools_tokens(all_tools)
                self._tracker.set_baseline_tokens(self._baseline_tokens)
                return self._baseline_tokens
            except Exception:
                pass
        return 0

    async def _handle_list_tools(
        self,
        _ctx: Any,
        _params: types.PaginatedRequestParams | None,
    ) -> types.ListToolsResult:
        """Return the two SchemaSlim meta-tools."""
        return types.ListToolsResult(tools=META_TOOLS)

    async def _handle_call_tool(
        self,
        _ctx: Any,
        params: types.CallToolRequestParams,
    ) -> types.CallToolResult:
        """Dispatch tool calls to search or proxy execution with telemetry tracking."""
        start_time = time.perf_counter()
        tool_name = params.name
        arguments = params.arguments or {}
        baseline = self._get_baseline_tokens()

        if tool_name == "schemaslim_search":
            result = await self._do_search(arguments)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Estimate actual tokens: meta-tools definition + search payload returned to LLM
            content_text = result.content[0].text if result.content and hasattr(result.content[0], "text") else ""
            actual_tokens = META_TOOLS_TOKENS + estimate_tokens(content_text)
            status = "error" if result.is_error else "success"
            query_str = arguments.get("query", "") if isinstance(arguments, dict) else ""
            display_name = query_str if query_str else "schemaslim_search"

            self._tracker.record_event(
                ProxyEvent(
                    timestamp=time.time(),
                    event_type="search",
                    tool_name=display_name,
                    latency_ms=latency_ms,
                    tokens_baseline=baseline,
                    tokens_actual=actual_tokens,
                    tokens_saved=max(0, baseline - actual_tokens),
                    status=status,
                )
            )
            return result

        elif tool_name == "schemaslim_call":
            result = await self._do_call(arguments)
            latency_ms = (time.perf_counter() - start_time) * 1000.0

            # Actual tokens: meta-tools + call arguments + response
            content_text = result.content[0].text if result.content and hasattr(result.content[0], "text") else ""
            actual_tokens = META_TOOLS_TOKENS + estimate_tokens(arguments) + estimate_tokens(content_text)
            status = "error" if result.is_error else "success"
            target_tool = arguments.get("namespaced_name", "") if isinstance(arguments, dict) else ""
            display_name = target_tool if target_tool else "schemaslim_call"

            self._tracker.record_event(
                ProxyEvent(
                    timestamp=time.time(),
                    event_type="call",
                    tool_name=display_name,
                    latency_ms=latency_ms,
                    tokens_baseline=baseline,
                    tokens_actual=actual_tokens,
                    tokens_saved=max(0, baseline - actual_tokens),
                    status=status,
                )
            )
            return result

        else:
            latency_ms = (time.perf_counter() - start_time) * 1000.0
            error_res = types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Unknown tool: '{tool_name}'. "
                        "Available tools: schemaslim_search, schemaslim_call",
                    )
                ],
                is_error=True,
            )
            self._tracker.record_event(
                ProxyEvent(
                    timestamp=time.time(),
                    event_type="call",
                    tool_name=tool_name,
                    latency_ms=latency_ms,
                    tokens_baseline=baseline,
                    tokens_actual=META_TOOLS_TOKENS,
                    tokens_saved=max(0, baseline - META_TOOLS_TOKENS),
                    status="error",
                )
            )
            return error_res

    async def _do_search(self, arguments: dict[str, Any]) -> types.CallToolResult:
        """Execute semantic search over the indexed tool schemas."""
        query = arguments.get("query", "")
        limit = arguments.get("limit", 3)

        if not query or not isinstance(query, str):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="Parameter 'query' is required and must be a non-empty string.",
                    )
                ],
                is_error=True,
            )

        if not isinstance(limit, int) or limit < 1:
            limit = 3
        # Security hardening: clamp limit to prevent DoS and SQLite variable overflow
        limit = min(max(1, limit), 20)

        if self._store is None:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="VectorStore is not initialized. Run 'schemaslim index' first.",
                    )
                ],
                is_error=True,
            )

        try:
            results = self._store.hybrid_search(query=query, limit=limit)
        except Exception as exc:
            logger.error("Search failed: %s: %s", type(exc).__name__, exc)
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Search error: {type(exc).__name__}: {exc}",
                    )
                ],
                is_error=True,
            )

        if not results:
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=json.dumps(
                            {"query": query, "results": [], "count": 0},
                            ensure_ascii=False,
                        ),
                    )
                ],
            )

        formatted = []
        for res in results:
            tool = res.tool
            formatted.append(
                {
                    "namespaced_name": tool.namespaced_name,
                    "server": tool.server_name,
                    "tool": tool.tool_name,
                    "description": tool.description,
                    "parameters": tool.parameters,
                    "relevance_score": res.score,
                }
            )

        payload = {
            "query": query,
            "count": len(formatted),
            "results": formatted,
        }

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(payload, indent=2, ensure_ascii=False),
                )
            ],
        )

    async def _do_call(self, arguments: dict[str, Any]) -> types.CallToolResult:
        """Proxy a tool call to the appropriate child server."""
        namespaced_name = arguments.get("namespaced_name", "")
        tool_arguments = arguments.get("arguments", {})

        if not namespaced_name or not isinstance(namespaced_name, str):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="Parameter 'namespaced_name' is required and must be a non-empty string.",
                    )
                ],
                is_error=True,
            )

        if not isinstance(tool_arguments, dict):
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text="Parameter 'arguments' must be a JSON object.",
                    )
                ],
                is_error=True,
            )

        try:
            result = await self._pool.call_tool(namespaced_name, tool_arguments)
            return result
        except (SessionNotFoundError, ValueError) as exc:
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text=str(exc))
                ],
                is_error=True,
            )
        except SessionCallError as exc:
            return types.CallToolResult(
                content=[
                    types.TextContent(type="text", text=str(exc))
                ],
                is_error=True,
            )
        except Exception as exc:
            logger.error("Unexpected error in call_tool: %s: %s", type(exc).__name__, exc)
            return types.CallToolResult(
                content=[
                    types.TextContent(
                        type="text",
                        text=f"Unexpected error: {type(exc).__name__}: {exc}",
                    )
                ],
                is_error=True,
            )

    async def start_stdio(self, config: Config, enable_tui: bool = False) -> None:
        """Start the virtualizing MCP server over stdin/stdout.

        Lifecycle:
          1. Open VectorStore for search and calculate baseline tokens.
          2. Optionally start live TUI dashboard on stderr.
          3. Initialize MCPSessionPool with persistent child connections.
          4. Run the MCP server over stdio transport.
          5. On exit, shut down pool, stop dashboard, and close VectorStore.

        Args:
            config: SchemaSlim root configuration.
            enable_tui: If True, renders live Rich dashboard exclusively to stderr.
        """
        server = Server(
            name="schemaslim",
            version="0.1.0",
            instructions=(
                "SchemaSlim is a virtualizing proxy for MCP tools. "
                "Use schemaslim_search to discover tools by intent, "
                "then schemaslim_call to execute them."
            ),
            on_list_tools=self._handle_list_tools,
            on_call_tool=self._handle_call_tool,
        )

        db_path = config.settings.resolved_db_path
        embedding_model = config.settings.embedding_model

        dashboard_runner = None
        if enable_tui:
            from schemaslim.ui.dashboard import DashboardRunner

            dashboard_runner = DashboardRunner(
                tracker=self._tracker,
                active_servers=list(config.active_servers.keys()),
            )
            await dashboard_runner.start()

        try:
            # 1. Initialize VectorStore
            logger.info("Opening VectorStore at %s...", db_path)
            self._store = VectorStore(
                db_path=db_path, embedding_model=embedding_model
            )
            total = self._store.get_total_tools_count()
            logger.info("VectorStore ready: %d indexed tools.", total)

            # Precalculate baseline tokens
            baseline = self._get_baseline_tokens()
            logger.info("Baseline catalog footprint: ~%d tokens.", baseline)

            # 2. Initialize session pool
            logger.info("Initializing child server session pool...")
            await self._pool.initialize(config)
            connected = self._pool.server_names
            logger.info(
                "Session pool ready: %d servers connected.", len(connected)
            )
            if dashboard_runner is not None:
                dashboard_runner.update_servers(connected)

            # 3. Run stdio server
            logger.info("SchemaSlim MCP server starting on stdio...")
            async with stdio_server() as (read_stream, write_stream):
                init_options = server.create_initialization_options()
                await server.run(read_stream, write_stream, init_options)

        finally:
            # 4. Cleanup
            if dashboard_runner is not None:
                await dashboard_runner.stop()
            await self._pool.shutdown()
            if self._store is not None:
                self._store.close()
                self._store = None
            logger.info("SchemaSlim MCP server stopped.")
