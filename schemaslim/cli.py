"""Typer command-line interface for SchemaSlim."""

import sys
from pathlib import Path
from typing import Optional
import typer
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

# Ensure UTF-8 stream handling on Windows to prevent UnicodeEncodeError in non-ASCII paths
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import asyncio
from schemaslim import __version__
from schemaslim.config.loader import (
    ConfigError,
    ConfigNotFoundError,
    ConfigValidationError,
    create_default_config,
    find_config_file,
    load_config,
    save_config,
)
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.storage.vector_store import VectorStore
from schemaslim.utils.logger import setup_logger

app = typer.Typer(
    name="schemaslim",
    help="SchemaSlim: Lightweight local virtualizing reverse-proxy for Model Context Protocol (MCP).",
    no_args_is_help=True,
)
config_app = typer.Typer(
    name="config",
    help="Manage and validate SchemaSlim configuration files.",
    no_args_is_help=True,
)
app.add_typer(config_app, name="config")

console = Console(legacy_windows=False)


@app.command(name="version")
def version() -> None:
    """Print SchemaSlim version information."""
    console.print(f"[bold cyan]SchemaSlim[/bold cyan] version [bold green]{__version__}[/bold green]")


@config_app.command(name="validate")
def validate_config_cmd(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to configuration file to validate. If omitted, uses auto-discovery.",
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Show detailed server list and configuration parameters."
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
) -> None:
    """Validate a SchemaSlim configuration file against Pydantic schema."""
    setup_logger(level="DEBUG" if verbose else "INFO")

    try:
        cfg = load_config(path, allow_cwd=allow_cwd)
        found_path = find_config_file(path, allow_cwd=allow_cwd)
    except ConfigNotFoundError as e:
        console.print(f"[bold red]Configuration Not Found:[/bold red] {e}")
        raise typer.Exit(code=1)
    except ConfigValidationError as e:
        console.print(
            Panel(
                f"[bold red]Validation Error[/bold red]\n\n{e}",
                title="Configuration Error",
                border_style="red",
            )
        )
        raise typer.Exit(code=1)
    except ConfigError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Summary table
    table = Table(title=f"Configuration Valid: {found_path.name}", border_style="green")
    table.add_column("Property", style="bold cyan")
    table.add_column("Value", style="white")

    table.add_row("Config File", str(found_path))
    table.add_row("Total Servers", str(len(cfg.mcpServers)))
    table.add_row("Active Servers", str(len(cfg.active_servers)))
    table.add_row("Embedding Model", cfg.settings.embedding_model)
    table.add_row("Vector DB Path", str(cfg.settings.resolved_db_path))
    table.add_row("Top K", str(cfg.settings.top_k))
    table.add_row("Similarity Threshold", str(cfg.settings.similarity_threshold))

    console.print(table)

    if verbose and cfg.mcpServers:
        server_table = Table(title="Configured MCP Servers", border_style="cyan")
        server_table.add_column("Name", style="bold yellow")
        server_table.add_column("Transport", style="magenta")
        server_table.add_column("Target / Command", style="white")
        server_table.add_column("Status", style="green")

        for name, s_cfg in cfg.mcpServers.items():
            transport = s_cfg.transport
            target = s_cfg.command if transport == "stdio" else str(s_cfg.url)
            status = "[green]Enabled[/green]" if s_cfg.enabled else "[dim red]Disabled[/dim red]"
            server_table.add_row(name, transport, target, status)

        console.print(server_table)

    console.print("[bold green]✓ Configuration is valid and ready for use.[/bold green]")


@config_app.command(name="show")
def show_config_cmd(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path to configuration file. If omitted, uses auto-discovery.",
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
) -> None:
    """Display the loaded configuration in formatted JSON."""
    try:
        cfg = load_config(path, allow_cwd=allow_cwd)
        found_path = find_config_file(path, allow_cwd=allow_cwd)
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        raise typer.Exit(code=1)

    json_str = cfg.model_dump_json(indent=2, by_alias=True)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
    console.print(Panel(syntax, title=f"Config: {found_path}", border_style="blue"))


@config_app.command(name="init")
def init_config_cmd(
    path: Path = typer.Argument(
        Path("schemaslim.json"),
        help="Target path to create template configuration.",
    ),
    overwrite: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing configuration file."
    ),
) -> None:
    """Generate a starter schemaslim.json configuration file."""
    resolved = path.resolve()
    if resolved.is_file() and not overwrite:
        console.print(
            f"[bold yellow]File already exists:[/bold yellow] {resolved}\n"
            f"Use [bold]--force[/bold] to overwrite."
        )
        raise typer.Exit(code=1)

    starter = create_default_config()
    saved = save_config(starter, resolved)
    console.print(f"[bold green]✓ Created starter configuration at:[/bold green] {saved}")


@app.command(name="index")
def index_cmd(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to schemaslim.json configuration file."
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force re-harvesting and vector index rebuild."
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose debug logging."
    ),
) -> None:
    """Harvest tool schemas from active MCP servers and index them into local vector DB."""
    setup_logger(level="DEBUG" if verbose else "INFO")

    try:
        cfg = load_config(config_path, allow_cwd=allow_cwd)
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        raise typer.Exit(code=1)

    active_count = len(cfg.active_servers)
    if active_count == 0:
        console.print("[bold yellow]No active MCP servers found in configuration.[/bold yellow]")
        raise typer.Exit(code=0)

    console.print(
        f"[bold cyan]Harvesting schemas from {active_count} active MCP servers...[/bold cyan]"
    )

    harvester = SchemaHarvester()
    tools, failures = asyncio.run(harvester.harvest_all(cfg))

    if failures:
        fail_table = Table(title="Server Harvesting Errors", border_style="red")
        fail_table.add_column("Server", style="bold red")
        fail_table.add_column("Error Message", style="yellow")
        for s_name, err in failures.items():
            fail_table.add_row(s_name, err)
        console.print(fail_table)

    if not tools:
        console.print("[bold yellow]No tools were harvested from active servers.[/bold yellow]")
        raise typer.Exit(code=1 if failures else 0)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    console.print(
        f"[bold cyan]Indexing {len(tools)} tools into vector DB at {db_path}...[/bold cyan]"
    )

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        if force:
            for s_name in cfg.active_servers.keys():
                store.remove_server_tools(s_name)

        upserted = store.upsert_tools(tools)
        total_count = store.get_total_tools_count()

    summary_table = Table(title="Index Synchronization Summary", border_style="green")
    summary_table.add_column("Metric", style="bold cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Harvested Tools", str(len(tools)))
    summary_table.add_row("New / Updated in Vector DB", str(upserted))
    summary_table.add_row("Total Indexed Tools in DB", str(total_count))
    summary_table.add_row("Embedding Model", embedding_model)
    summary_table.add_row("Database Location", str(db_path))

    console.print(summary_table)

    # Detailed tool listing
    detail_table = Table(title="Harvested Tools by Server", border_style="cyan")
    detail_table.add_column("Server", style="bold yellow")
    detail_table.add_column("Tool Name", style="magenta")
    detail_table.add_column("Namespaced Name", style="cyan")
    detail_table.add_column("Description", style="white")

    for t in tools:
        desc_preview = t.description[:60] + "..." if len(t.description) > 60 else (t.description or "-")
        detail_table.add_row(t.server_name, t.tool_name, t.namespaced_name, desc_preview)

    console.print(detail_table)
    console.print("[bold green]✓ Indexing complete and ready for semantic search.[/bold green]")


@app.command(name="search")
def search_cmd(
    query: str = typer.Argument(
        ..., help="Natural language query describing desired tool functionality."
    ),
    limit: int = typer.Option(
        3, "--limit", "-l", help="Maximum number of tools to return."
    ),
    threshold: float = typer.Option(
        0.45, "--threshold", "-t", help="Minimum relevance score threshold (0.0 to 1.0)."
    ),
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to schemaslim.json config file."
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
) -> None:
    """Perform hybrid semantic search for MCP tools matching natural language query."""
    try:
        cfg = load_config(config_path, allow_cwd=allow_cwd)
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        raise typer.Exit(code=1)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        total_in_db = store.get_total_tools_count()
        if total_in_db == 0:
            console.print(
                f"[bold yellow]Vector DB is empty ({db_path}).[/bold yellow]\n"
                "Run [bold cyan]schemaslim index[/bold cyan] first to harvest tool schemas."
            )
            raise typer.Exit(code=1)

        results = store.hybrid_search(query=query, limit=limit, threshold=threshold)

    if not results:
        console.print(
            f"[bold yellow]No tools found matching query:[/bold yellow] '{query}' "
            f"(threshold: {threshold}, total tools: {total_in_db})"
        )
        return

    table = Table(title=f"Search Results for: '{query}'", border_style="green")
    table.add_column("Rank", style="bold cyan", justify="right", width=5)
    table.add_column("Score", style="bold green", justify="right", width=8)
    table.add_column("Tool", style="bold yellow")
    table.add_column("Server", style="magenta")
    table.add_column("Description", style="white")
    table.add_column("Parameters", style="dim cyan")

    for i, res in enumerate(results, 1):
        tool = res.tool
        score_str = f"{res.score:.3f}"
        desc = tool.description[:80] + "..." if len(tool.description) > 80 else (tool.description or "-")
        props = list(tool.parameters.get("properties", {}).keys()) if isinstance(tool.parameters, dict) else []
        props_str = ", ".join(props) if props else "none"

        table.add_row(
            str(i),
            score_str,
            tool.tool_name,
            tool.server_name,
            desc,
            props_str,
        )

    console.print(table)


@app.command(name="stats")
def stats_cmd(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to schemaslim.json configuration file."
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
) -> None:
    """Display tool repository statistics and estimated LLM token economy."""
    try:
        cfg = load_config(config_path, allow_cwd=allow_cwd)
    except Exception as e:
        console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        raise typer.Exit(code=1)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    from schemaslim.telemetry import estimate_tools_tokens
    from schemaslim.core.server import META_TOOLS_TOKENS

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        total_tools = store.get_total_tools_count()
        all_tools = store.get_all_tools()

    active_servers = list(cfg.active_servers.keys())
    baseline_catalog_tokens = estimate_tools_tokens(all_tools) if all_tools else 0

    # Typical SchemaSlim virtualized footprint:
    # 2 meta-tools (~280 tok) + top-k results schema payload (e.g. 3 tools ~ 400 tok)
    typical_top_k = min(cfg.settings.top_k, total_tools) if total_tools > 0 else 0
    sample_tools = all_tools[:typical_top_k] if all_tools else []
    sample_search_payload_tokens = estimate_tools_tokens(sample_tools)
    virtualized_tokens = META_TOOLS_TOKENS + sample_search_payload_tokens if total_tools > 0 else META_TOOLS_TOKENS
    tokens_saved_per_turn = max(0, baseline_catalog_tokens - virtualized_tokens)
    compression_pct = (
        (tokens_saved_per_turn / baseline_catalog_tokens * 100.0)
        if baseline_catalog_tokens > 0
        else 0.0
    )

    # Summary table
    table = Table(title="SchemaSlim Token Economy & Index Analysis", border_style="cyan")
    table.add_column("Metric", style="bold white", ratio=3)
    table.add_column("Value", style="bold green", ratio=2)
    table.add_column("Notes / Description", style="dim", ratio=4)

    table.add_row(
        "Active MCP Servers",
        f"{len(active_servers)}",
        ", ".join(active_servers) if active_servers else "None",
    )
    table.add_row(
        "Indexed Tools in DB",
        f"{total_tools}",
        f"Storage: {db_path}",
    )
    table.add_row(
        "Baseline Catalog Size",
        f"{baseline_catalog_tokens:,} tokens",
        "Tokens required if all tools were exposed directly to LLM",
    )
    table.add_row(
        "Virtualized Footprint",
        f"{virtualized_tokens:,} tokens",
        f"2 meta-tools (~{META_TOOLS_TOKENS} tok) + top-{typical_top_k} search results",
    )
    table.add_row(
        "Savings Per LLM Turn",
        f"+{tokens_saved_per_turn:,} tokens",
        f"Context compression: ~{compression_pct:.1f}%",
    )
    table.add_row(
        "Est. 20-Turn Session Savings",
        f"+{tokens_saved_per_turn * 20:,} tokens",
        "Estimated token reduction across a standard session",
    )
    table.add_row(
        "Est. 100-Turn Agent Savings",
        f"+{tokens_saved_per_turn * 100:,} tokens",
        "Estimated token reduction for long-running autonomous workflows",
    )

    console.print(table)


@app.command(name="serve")
def serve_cmd(
    config_path: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to schemaslim.json configuration file."
    ),
    allow_cwd: bool = typer.Option(
        False,
        "--allow-cwd/--no-allow-cwd",
        help="Allow loading configuration from untrusted current working directory.",
    ),
    tui: bool = typer.Option(
        False,
        "--tui/--no-tui",
        "--dashboard/--no-dashboard",
        help="Enable live Rich TUI dashboard on stderr (quiet stdio mode by default).",
    ),
) -> None:
    """Start the SchemaSlim virtualizing MCP server over stdio transport.

    This command runs SchemaSlim as a persistent MCP server that exposes
    two meta-tools (schemaslim_search, schemaslim_call) over stdin/stdout.

    All logs and dashboard views are directed strictly to stderr to keep
    the stdio JSON-RPC channel pure and uninterrupted.
    """
    # Load config first (before entering async world)
    try:
        cfg = load_config(config_path, allow_cwd=allow_cwd)
    except Exception as e:
        # Use stderr console to avoid stdout pollution
        err_console = Console(stderr=True, legacy_windows=False)
        err_console.print(f"[bold red]Failed to load configuration:[/bold red] {e}")
        raise typer.Exit(code=1)

    # Initialize logger to stderr only
    setup_logger(level=cfg.settings.log_level, name="schemaslim")

    from schemaslim.core.server import VirtualMCPServer

    server = VirtualMCPServer()
    asyncio.run(server.start_stdio(cfg, enable_tui=tui))


@app.command(name="benchmark")
def benchmark_cmd(
    runs: int = typer.Option(
        5, "--runs", "-r", help="Number of benchmark iterations for latency measurement."
    ),
    output: str = typer.Option(
        "table", "--output", "-o", help="Output format: 'table' or 'json'."
    ),
) -> None:
    """Run synthetic MCP benchmark to evaluate context compression and search latency."""
    if output not in {"table", "json"}:
        console.print(f"[bold red]Error:[/bold red] Invalid output format '{output}'. Choose 'table' or 'json'.")
        raise typer.Exit(code=1)

    if output == "json":
        # Suppress informative logs for clean JSON stdout
        setup_logger(level="ERROR")
    else:
        console.print(
            f"[bold cyan]Running SchemaSlim synthetic virtualization benchmark ({runs} iterations)...[/bold cyan]"
        )

    from schemaslim.benchmark import BenchmarkRunner

    runner = BenchmarkRunner()
    report = runner.run(runs=runs)

    if output == "json":
        sys.stdout.write(report.model_dump_json(indent=2) + "\n")
        return

    # Overview table
    summary_table = Table(
        title="SchemaSlim Context Virtualization Benchmark Summary",
        border_style="green",
    )
    summary_table.add_column("Metric", style="bold cyan", ratio=3)
    summary_table.add_column("Value", style="bold white", ratio=2)
    summary_table.add_column("Details", style="dim", ratio=4)

    summary_table.add_row(
        "Synthetic Servers",
        f"{report.servers_count} servers ({report.total_tools} tools)",
        "git_server, db_server, fs_server, api_server",
    )
    summary_table.add_row(
        "Full Catalog Footprint",
        f"{report.tokens_baseline:,} tokens",
        "Raw unvirtualized MCP tools manifest",
    )
    summary_table.add_row(
        "Virtualized Footprint / Turn",
        f"{report.avg_tokens_virtualized:,} tokens",
        "2 meta-tools + matched tool schemas",
    )
    summary_table.add_row(
        "Context Saved / Turn",
        f"[bold green]+{report.avg_tokens_saved:,} tokens[/bold green]",
        f"[bold green]~{report.compression_pct:.1f}% reduction[/bold green]",
    )
    summary_table.add_row(
        "Search Latency (Mean)",
        f"{report.latency_mean_ms:.2f} ms",
        f"p50: {report.latency_p50_ms:.2f} ms │ p95: {report.latency_p95_ms:.2f} ms",
    )

    console.print(summary_table)

    # Detailed query table
    detail_table = Table(
        title="Benchmark Intent Query Breakdown",
        border_style="cyan",
    )
    detail_table.add_column("#", justify="right", width=4)
    detail_table.add_column("Developer Query Intent", ratio=4)
    detail_table.add_column("Top Match", style="bold yellow", ratio=3)
    detail_table.add_column("Score", justify="right", style="green", width=7)
    detail_table.add_column("Latency", justify="right", style="magenta", width=10)
    detail_table.add_column("Context Saved", justify="right", style="bold green", width=15)
    detail_table.add_column("Economy", justify="right", style="cyan", width=9)

    for i, q in enumerate(report.queries_detail, 1):
        detail_table.add_row(
            str(i),
            q.query,
            q.matched_tool,
            f"{q.score:.3f}",
            f"{q.latency_ms:.1f} ms",
            f"+{q.tokens_saved:,} tok",
            f"~{q.compression_pct:.1f}%",
        )

    console.print(detail_table)
    console.print(
        f"[bold green]✓ Benchmark complete:[/bold green] Achieved [bold]{report.compression_pct:.1f}%[/bold] token reduction with [bold]{report.latency_mean_ms:.1f}ms[/bold] avg routing latency."
    )


if __name__ == "__main__":
    app()


