"""Synthetic benchmark engine for SchemaSlim context compression and latency evaluation."""

import statistics
import time
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from schemaslim.core.server import META_TOOLS_TOKENS
from schemaslim.storage.models import IndexedTool
from schemaslim.storage.vector_store import VectorStore
from schemaslim.telemetry.tracker import estimate_tools_tokens


def generate_synthetic_tools() -> List[IndexedTool]:
    """Generate a realistic synthetic suite of 20 tools across 4 diverse MCP servers."""
    tools: List[IndexedTool] = []

    # 1. git_server (6 tools)
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_status",
            description="Check repository status, staged/unstaged changes, and untracked files.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Optional subpath to inspect"},
                    "short": {"type": "boolean", "description": "Give the output in the short-format", "default": False},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_diff",
            description="Show changes between commits, commit and working tree, or staged changes.",
            parameters={
                "type": "object",
                "properties": {
                    "staged": {"type": "boolean", "description": "View changes staged for commit", "default": False},
                    "path": {"type": "string", "description": "Specific file or directory to diff"},
                    "revision": {"type": "string", "description": "Commit or branch to diff against"},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_commit",
            description="Record staged changes to the repository with a commit message and author.",
            parameters={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit log message"},
                    "amend": {"type": "boolean", "description": "Amend previous commit", "default": False},
                    "author": {"type": "string", "description": "Override commit author"},
                },
                "required": ["message"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_log",
            description="Show commit history, commit hashes, authors, and timestamps.",
            parameters={
                "type": "object",
                "properties": {
                    "limit": {"type": "integer", "description": "Max number of commits to return", "default": 10},
                    "since": {"type": "string", "description": "Show commits more recent than a specific date"},
                    "author": {"type": "string", "description": "Limit commits to those by specified author"},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_branch",
            description="List, create, or delete branches in the local git repository.",
            parameters={
                "type": "object",
                "properties": {
                    "list_all": {"type": "boolean", "description": "List both remote and local branches", "default": False},
                    "create": {"type": "string", "description": "Create new branch with specified name"},
                    "delete": {"type": "string", "description": "Delete specified branch"},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="git_server",
            tool_name="git_checkout",
            description="Switch branches or restore working tree files to a specific commit.",
            parameters={
                "type": "object",
                "properties": {
                    "target": {"type": "string", "description": "Branch name, commit SHA, or file path"},
                    "create_branch": {"type": "boolean", "description": "Create new branch if it does not exist", "default": False},
                },
                "required": ["target"],
            },
        )
    )

    # 2. db_server (5 tools)
    tools.append(
        IndexedTool.create(
            server_name="db_server",
            tool_name="sql_query",
            description="Execute arbitrary SQL queries against the database (SELECT, INSERT, UPDATE, DELETE).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL statement to execute"},
                    "parameters": {"type": "array", "description": "Positional or named query parameters", "items": {"type": "string"}},
                    "timeout_sec": {"type": "integer", "description": "Execution timeout in seconds", "default": 30},
                },
                "required": ["query"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="db_server",
            tool_name="list_tables",
            description="List all database tables, views, schema definitions, and row counts.",
            parameters={
                "type": "object",
                "properties": {
                    "schema": {"type": "string", "description": "Database schema name", "default": "public"},
                    "include_views": {"type": "boolean", "description": "Whether to include views", "default": True},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="db_server",
            tool_name="describe_table",
            description="Describe table schema, column types, nullability, foreign keys, and indexes.",
            parameters={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Target table name"},
                    "schema": {"type": "string", "description": "Schema name", "default": "public"},
                },
                "required": ["table_name"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="db_server",
            tool_name="explain_query",
            description="Show query execution plan and cost estimates (EXPLAIN ANALYZE).",
            parameters={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL statement to analyze"},
                    "analyze": {"type": "boolean", "description": "Run query with actual timings", "default": False},
                },
                "required": ["query"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="db_server",
            tool_name="vacuum_db",
            description="Optimize database storage, rebuild indices, and update query planner statistics.",
            parameters={
                "type": "object",
                "properties": {
                    "table_name": {"type": "string", "description": "Optional specific table to vacuum"},
                    "full": {"type": "boolean", "description": "Perform full reclamation vacuum", "default": False},
                },
            },
        )
    )

    # 3. fs_server (5 tools)
    tools.append(
        IndexedTool.create(
            server_name="fs_server",
            tool_name="read_file",
            description="Read content from a file on the local filesystem with optional line offsets.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Absolute or relative file path"},
                    "offset": {"type": "integer", "description": "Starting line offset", "default": 1},
                    "limit": {"type": "integer", "description": "Max lines to read"},
                    "encoding": {"type": "string", "description": "File encoding", "default": "utf-8"},
                },
                "required": ["path"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="fs_server",
            tool_name="write_file",
            description="Write, overwrite, or append content to a file on local filesystem.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Target file path"},
                    "content": {"type": "string", "description": "Text content to write"},
                    "append": {"type": "boolean", "description": "Append instead of overwrite", "default": False},
                },
                "required": ["path", "content"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="fs_server",
            tool_name="list_directory",
            description="List directory entries recursively with file size, modified time, and glob filtering.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Directory path to list", "default": "."},
                    "pattern": {"type": "string", "description": "Glob filter pattern (e.g. *.py)", "default": "*"},
                    "recursive": {"type": "boolean", "description": "Traverse subdirectories", "default": False},
                },
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="fs_server",
            tool_name="move_file",
            description="Move or rename a file or directory across paths.",
            parameters={
                "type": "object",
                "properties": {
                    "source": {"type": "string", "description": "Source path"},
                    "destination": {"type": "string", "description": "Destination path"},
                    "overwrite": {"type": "boolean", "description": "Overwrite existing destination", "default": False},
                },
                "required": ["source", "destination"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="fs_server",
            tool_name="delete_file",
            description="Permanently delete a file or directory from filesystem.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File or folder path to delete"},
                    "recursive": {"type": "boolean", "description": "Recursively remove directories", "default": False},
                },
                "required": ["path"],
            },
        )
    )

    # 4. api_server (4 tools)
    tools.append(
        IndexedTool.create(
            server_name="api_server",
            tool_name="http_get",
            description="Send an HTTP GET request to external REST API with query params and headers.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target endpoint URL"},
                    "headers": {"type": "object", "description": "HTTP request headers"},
                    "timeout": {"type": "integer", "description": "Request timeout in seconds", "default": 10},
                },
                "required": ["url"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="api_server",
            tool_name="http_post",
            description="Send an HTTP POST request with JSON payload or form body to external API.",
            parameters={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target endpoint URL"},
                    "body": {"type": "object", "description": "JSON request payload"},
                    "headers": {"type": "object", "description": "Custom HTTP headers"},
                },
                "required": ["url"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="api_server",
            tool_name="set_headers",
            description="Configure global default HTTP headers (e.g. Bearer token, User-Agent).",
            parameters={
                "type": "object",
                "properties": {
                    "headers": {"type": "object", "description": "Key-value header pairs to set"},
                },
                "required": ["headers"],
            },
        )
    )
    tools.append(
        IndexedTool.create(
            server_name="api_server",
            tool_name="graphql_request",
            description="Execute a GraphQL query or mutation against a GraphQL endpoint.",
            parameters={
                "type": "object",
                "properties": {
                    "endpoint": {"type": "string", "description": "GraphQL server URL"},
                    "query": {"type": "string", "description": "GraphQL query or mutation string"},
                    "variables": {"type": "object", "description": "Query variables dictionary"},
                },
                "required": ["endpoint", "query"],
            },
        )
    )

    return tools


BENCHMARK_QUERIES = [
    "show uncommitted changes in git repository and modified files",
    "execute a SQL query to select all active users from users table",
    "read application configuration yaml file from disk",
    "send a POST request with JSON body to external webhook endpoint",
    "list commit history of recent commits on current branch",
]


class BenchmarkQueryResult(BaseModel):
    """Detailed result for an individual benchmark query."""

    query: str
    matched_tool: str
    score: float
    latency_ms: float
    tokens_actual: int
    tokens_saved: int
    compression_pct: float


class BenchmarkReport(BaseModel):
    """Comprehensive benchmark evaluation report."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    timestamp: float = Field(default_factory=time.time)
    total_tools: int
    servers_count: int
    runs: int
    tokens_baseline: int
    avg_tokens_virtualized: int
    avg_tokens_saved: int
    compression_pct: float
    latency_mean_ms: float
    latency_p50_ms: float
    latency_p95_ms: float
    queries_detail: List[BenchmarkQueryResult]


class BenchmarkRunner:
    """Orchestrates in-memory synthetic tool indexing, search benchmarking, and savings calculation."""

    def __init__(self, embedder: Optional[Any] = None) -> None:
        self.embedder = embedder

    def run(self, runs: int = 5, top_k: int = 3) -> BenchmarkReport:
        """Run the full benchmark suite across synthetic MCP servers.

        Args:
            runs: Number of benchmark query repetitions for latency sampling.
            top_k: Number of search results returned per query.

        Returns:
            BenchmarkReport containing metrics and token compression data.
        """
        tools = generate_synthetic_tools()
        servers = {t.server_name for t in tools}

        # 1. Baseline calculation
        tokens_baseline = estimate_tools_tokens(tools)

        # 2. In-memory indexing
        with VectorStore(db_path=":memory:", embedder=self.embedder) as store:
            store.upsert_tools(tools)

            all_latencies: List[float] = []
            query_results: List[BenchmarkQueryResult] = []

            for query_idx, query in enumerate(BENCHMARK_QUERIES):
                query_latencies: List[float] = []
                best_match = ""
                best_score = 0.0
                returned_tools: List[IndexedTool] = []

                for _ in range(runs):
                    t0 = time.perf_counter()
                    results = store.hybrid_search(query=query, limit=top_k)
                    latency = (time.perf_counter() - t0) * 1000.0

                    query_latencies.append(latency)
                    all_latencies.append(latency)

                    if results and not best_match:
                        best_match = results[0].tool.namespaced_name
                        best_score = results[0].score
                        returned_tools = [r.tool for r in results]

                avg_query_lat = statistics.mean(query_latencies) if query_latencies else 0.0

                # Actual token footprint: 2 meta-tools + returned tools schemas
                search_payload_tokens = estimate_tools_tokens(returned_tools)
                tokens_actual = META_TOOLS_TOKENS + search_payload_tokens
                tokens_saved = max(0, tokens_baseline - tokens_actual)
                comp_pct = (
                    (tokens_saved / tokens_baseline * 100.0)
                    if tokens_baseline > 0
                    else 0.0
                )

                query_results.append(
                    BenchmarkQueryResult(
                        query=query,
                        matched_tool=best_match or "none",
                        score=round(best_score, 3),
                        latency_ms=round(avg_query_lat, 2),
                        tokens_actual=tokens_actual,
                        tokens_saved=tokens_saved,
                        compression_pct=round(comp_pct, 1),
                    )
                )

        # Compute overall statistics
        sorted_latencies = sorted(all_latencies) if all_latencies else [0.0]
        mean_latency = statistics.mean(sorted_latencies)
        p50 = statistics.median(sorted_latencies)

        # 95th percentile
        p95_index = int(len(sorted_latencies) * 0.95)
        p95 = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]

        avg_actual = (
            int(statistics.mean([q.tokens_actual for q in query_results]))
            if query_results
            else META_TOOLS_TOKENS
        )
        avg_saved = max(0, tokens_baseline - avg_actual)
        overall_compression = (
            (avg_saved / tokens_baseline * 100.0) if tokens_baseline > 0 else 0.0
        )

        return BenchmarkReport(
            total_tools=len(tools),
            servers_count=len(servers),
            runs=runs,
            tokens_baseline=tokens_baseline,
            avg_tokens_virtualized=avg_actual,
            avg_tokens_saved=avg_saved,
            compression_pct=round(overall_compression, 1),
            latency_mean_ms=round(mean_latency, 2),
            latency_p50_ms=round(p50, 2),
            latency_p95_ms=round(p95, 2),
            queries_detail=query_results,
        )
