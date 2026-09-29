"""Typer command-line interface for SchemaSlim with minimalist reference design."""

import asyncio
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.theme import Theme

# Ensure UTF-8 stream handling on Windows to prevent UnicodeEncodeError in non-ASCII paths
if sys.platform == "win32":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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
from schemaslim.config.migrator import ConfigMigrator, MigrationError
from schemaslim.core.harvester import SchemaHarvester
from schemaslim.storage.vector_store import VectorStore
from schemaslim.utils.logger import setup_logger

# Reference aesthetic theme: clean white, dim gray, quiet green
monochrome_theme = Theme(
    {
        "info": "dim white",
        "warning": "dim yellow",
        "error": "red",
        "success": "green",
        "header": "bold white",
        "key": "dim",
        "val": "white",
        "muted": "bright_black",
    }
)

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

console = Console(theme=monochrome_theme, legacy_windows=False)


def print_section(
    title: str,
    lines: List[Tuple[str, str]],
    width: int = 58,
    footer: Optional[str] = None,
) -> None:
    """Render a clean section block in the SchemaSlim reference aesthetic."""
    prefix = f"◆ {title} "
    remaining = max(3, width - len(prefix))
    console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * remaining}[/dim]")
    for key, val in lines:
        console.print(f"  [dim]{key:<7}[/dim] [dim]›[/dim] {val}")
    if footer:
        console.print(f"\n  {footer}")
    console.print()


def version_callback(value: bool) -> None:
    if value:
        console.print(f"[bold white]SchemaSlim[/bold white] [dim]v{__version__}[/dim]")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-V",
        help="Print SchemaSlim version information and exit.",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """SchemaSlim: Lightweight local virtualizing reverse-proxy for Model Context Protocol (MCP)."""
    pass


@app.command(name="version")
def version() -> None:
    """Print SchemaSlim version information."""
    console.print(f"[bold white]SchemaSlim[/bold white] [dim]v{__version__}[/dim]")


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
        console.print(f"[red]Configuration Not Found:[/red] {e}")
        raise typer.Exit(code=1)
    except ConfigValidationError as e:
        console.print(f"[red]Validation Error:[/red] {e}")
        raise typer.Exit(code=1)
    except ConfigError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)

    active_cnt = len(cfg.active_servers)
    disabled_cnt = len(cfg.mcpServers) - active_cnt

    print_section(
        title=f"Configuration Valid: {found_path.name}",
        lines=[
            ("file", str(found_path)),
            ("mcp", f"{active_cnt} active  •  0 errors  •  {disabled_cnt} disabled"),
            ("embed", f"{cfg.settings.embedding_model} (384d)"),
            ("db", str(cfg.settings.resolved_db_path)),
            ("search", f"top_k: {cfg.settings.top_k}  •  threshold: {cfg.settings.similarity_threshold}"),
        ],
    )

    if verbose and cfg.mcpServers:
        prefix = "◆ Configured MCP Servers "
        console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
        for name, s_cfg in cfg.mcpServers.items():
            transport = s_cfg.transport
            target = s_cfg.command if transport == "stdio" else str(s_cfg.url)
            status = "[green]active[/green]" if s_cfg.enabled else "[dim]disabled[/dim]"
            console.print(f"  [dim]{name:<10}[/dim] [dim]›[/dim] {transport}  •  {target}  •  {status}")
        console.print()

    console.print("[green]✓ Configuration is valid and ready for use.[/green]")


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
        console.print(f"[red]Failed to load configuration:[/red] {e}")
        raise typer.Exit(code=1)

    prefix = f"◆ CONFIG: {found_path.name} "
    console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
    json_str = cfg.model_dump_json(indent=2, by_alias=True)
    syntax = Syntax(json_str, "json", theme="monokai", line_numbers=False)
    console.print(syntax)
    console.print()


@config_app.command(name="init")
def init_config_cmd(
    path: Optional[Path] = typer.Argument(
        None,
        help="Path where starter schemaslim.json will be generated. Default: ./schemaslim.json",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Overwrite existing configuration file if present."
    ),
) -> None:
    """Generate a starter schemaslim.json template with example server definitions."""
    target = path or Path("schemaslim.json")
    resolved = target.resolve()

    if resolved.exists() and not force:
        console.print(
            f"[dim yellow]File already exists:[/dim yellow] {resolved}\n"
            "Use [bold]--force[/bold] to overwrite."
        )
        raise typer.Exit(code=1)

    starter = create_default_config()
    saved = save_config(starter, resolved)
    console.print(f"[green]✓ Created starter configuration at:[/green] {saved}")


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
        console.print(f"[red]Failed to load configuration:[/red] {e}")
        raise typer.Exit(code=1)

    active_count = len(cfg.active_servers)
    if active_count == 0:
        console.print("[dim]No active MCP servers found in configuration.[/dim]")
        raise typer.Exit(code=0)

    console.print(f"[dim]Harvesting schemas from {active_count} active MCP servers...[/dim]")

    harvester = SchemaHarvester()
    tools, failures = asyncio.run(harvester.harvest_all(cfg))

    if failures:
        prefix = "◆ SERVER HARVESTING ERRORS "
        console.print(f"[bold red]{prefix}[/bold red][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
        for s_name, err in failures.items():
            console.print(f"  [bold red]{s_name:<10}[/bold red] [dim]›[/dim] [dim yellow]{err}[/dim yellow]")
        console.print()

    if not tools:
        console.print("[dim yellow]No tools were harvested from active servers.[/dim yellow]")
        raise typer.Exit(code=1 if failures else 0)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    console.print(f"[dim]Indexing {len(tools)} tools into vector DB at {db_path}...[/dim]")

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        if force:
            for s_name in cfg.active_servers.keys():
                store.remove_server_tools(s_name)

        upserted = store.upsert_tools(tools)
        total_count = store.get_total_tools_count()

    print_section(
        title="Index Synchronization",
        lines=[
            ("harvest", f"{len(tools)} tools harvested  •  {active_count} active servers  •  {len(failures)} errors"),
            ("store", f"{upserted} updated/new  •  {total_count} total in DB  •  {embedding_model}"),
            ("path", str(db_path)),
        ],
    )

    if tools:
        prefix = "◆ HARVESTED TOOLS "
        console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
        for t in tools:
            desc_preview = (
                t.description[:65] + "..."
                if len(t.description) > 65
                else (t.description or "-")
            )
            console.print(f"  [dim]{t.server_name:<10}[/dim] [dim]›[/dim] [bold white]{t.tool_name}[/bold white]  •  [dim]{desc_preview}[/dim]")
        console.print()

    console.print("[green]✓ Indexing complete and ready for semantic search.[/green]")


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
        console.print(f"[red]Failed to load configuration:[/red] {e}")
        raise typer.Exit(code=1)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        total_in_db = store.get_total_tools_count()
        if total_in_db == 0:
            console.print(
                f"[dim yellow]Vector DB is empty ({db_path}).[/dim yellow]\n"
                "Run [bold]schemaslim index[/bold] first to harvest tool schemas."
            )
            raise typer.Exit(code=1)

        results = store.hybrid_search(query=query, limit=limit, threshold=threshold)

    if not results:
        console.print(
            f"[dim]No tools found matching query:[/dim] '{query}' "
            f"(threshold: {threshold}, total tools: {total_in_db})"
        )
        raise typer.Exit(code=0)

    prefix = f"◆ SEARCH RESULTS: '{query}' "
    console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
    for i, tool in enumerate(results, 1):
        score_str = f"{tool.relevance_score:.3f}" if tool.relevance_score is not None else "N/A"
        desc = (
            tool.description[:75] + "..."
            if len(tool.description) > 75
            else (tool.description or "-")
        )
        console.print(f"  [dim]#{i}[/dim] [[green]{score_str}[/green]] [bold white]{tool.namespaced_name}[/bold white]")
        console.print(f"     [dim]›[/dim] {desc}")
    console.print()


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
        console.print(f"[red]Failed to load configuration:[/red] {e}")
        raise typer.Exit(code=1)

    db_path = cfg.settings.resolved_db_path
    embedding_model = cfg.settings.embedding_model

    from schemaslim.core.server import META_TOOLS_TOKENS
    from schemaslim.telemetry import estimate_tools_tokens

    with VectorStore(db_path=db_path, embedding_model=embedding_model) as store:
        total_tools = store.get_total_tools_count()
        all_tools = store.get_all_tools()

    active_servers = list(cfg.active_servers.keys())
    baseline_catalog_tokens = estimate_tools_tokens(all_tools) if all_tools else 0

    typical_top_k = min(cfg.settings.top_k, total_tools) if total_tools > 0 else 0
    sample_tools = all_tools[:typical_top_k] if all_tools else []
    sample_search_payload_tokens = estimate_tools_tokens(sample_tools)
    virtualized_tokens = (
        META_TOOLS_TOKENS + sample_search_payload_tokens
        if total_tools > 0
        else META_TOOLS_TOKENS
    )
    tokens_saved_per_turn = max(0, baseline_catalog_tokens - virtualized_tokens)
    compression_pct = (
        (tokens_saved_per_turn / baseline_catalog_tokens * 100.0)
        if baseline_catalog_tokens > 0
        else 0.0
    )

    servers_preview = f" ({', '.join(active_servers)})" if active_servers else ""
    print_section(
        title="Workspace MCP Status",
        lines=[
            ("mcp", f"{len(active_servers)} active{servers_preview}  •  0 errors  •  0 disabled"),
            ("tools", f"{total_tools} (Indexed Tools in DB)  •  ~{compression_pct:.1f}% context compression"),
            ("db", f"sqlite-vec (384d)  •  {db_path}"),
            ("catalog", f"{baseline_catalog_tokens:,} raw tokens  ›  ~{virtualized_tokens:,} virtualized"),
            ("savings", f"[green]+{tokens_saved_per_turn:,} tokens (Savings Per LLM Turn)[/green]"),
            (
                "session",
                f"[green]+{tokens_saved_per_turn * 20:,} tok / 20 turns[/green]  •  [green]+{tokens_saved_per_turn * 100:,} tok / 100 turns[/green]",
            ),
        ],
    )


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
    try:
        cfg = load_config(config_path, allow_cwd=allow_cwd)
    except Exception as e:
        err_console = Console(stderr=True, legacy_windows=False)
        err_console.print(f"[red]Failed to load configuration:[/red] {e}")
        raise typer.Exit(code=1)

    setup_logger(level=cfg.settings.log_level, name="schemaslim")

    from schemaslim.core.server import VirtualMCPServer

    server = VirtualMCPServer()
    asyncio.run(server.start_stdio(cfg, enable_tui=tui))


@app.command(name="wrap")
def wrap_cmd(
    path: Optional[Path] = typer.Option(
        None, "--path", "-p", help="Target client configuration file to wrap."
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip interactive confirmation prompt."
    ),
    no_index: bool = typer.Option(
        False, "--no-index", help="Skip automatic schema harvesting and indexing."
    ),
) -> None:
    """Wrap an existing MCP client configuration to route through SchemaSlim."""
    migrator = ConfigMigrator()

    try:
        if not path:
            detected = migrator.discover_clients()
            if not detected:
                console.print(
                    "[dim yellow]No existing MCP client configurations automatically discovered.[/dim yellow]\n"
                    "Specify target file directly: [bold]schemaslim wrap --path /path/to/config.json[/bold]"
                )
                raise typer.Exit(code=1)

            if len(detected) > 1 and not yes and sys.stdin.isatty():
                from schemaslim.ui.menu import select_option

                choices = [
                    (
                        c.name,
                        f"{c.path.name} • {c.server_count} servers"
                        + (" (wrapped)" if c.is_wrapped else ""),
                    )
                    for c in detected
                ]
                chosen_idx = select_option(
                    title="SELECT CLIENT CONFIGURATION",
                    options=choices,
                    console=console,
                )
                selected_client = detected[chosen_idx]
                target_file = selected_client.path
            else:
                selected_client = detected[0]
                target_file = selected_client.path
        else:
            target_file = path

        result = migrator.wrap(
            target_path=target_file,
            auto_confirm=yes,
            run_index=not no_index,
        )

        if result.cancelled:
            console.print("[dim]Wrap operation cancelled.[/dim]")
            raise typer.Exit(code=0)

        if not result.success:
            console.print(f"[red]Wrap failed:[/red] {result.message}")
            raise typer.Exit(code=1)

        print_section(
            title="SchemaSlim Virtualization",
            lines=[
                ("client", str(result.client_name)),
                ("target", str(result.target_path)),
                ("backup", str(result.backup_path) if result.backup_path else "none"),
                ("mcp", f"{result.servers_migrated} servers migrated"),
                ("global", str(migrator.global_config_path)),
                ("status", "[green]Virtualization Active (schemaslim serve)[/green]"),
            ],
        )
        console.print(f"[green]✓ {result.message}[/green]")

    except MigrationError as e:
        console.print(f"[red]Migration Error:[/red] {e}")
        raise typer.Exit(code=1)


@app.command(name="unwrap")
def unwrap_cmd(
    path: Optional[Path] = typer.Option(
        None,
        "--path",
        "-p",
        help="Target client configuration file to restore from backup.",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip interactive confirmation prompt."
    ),
) -> None:
    """Restore original client configuration from .schemaslim.bak backup."""
    migrator = ConfigMigrator()

    try:
        result = migrator.unwrap(target_path=path, auto_confirm=yes)

        if result.cancelled:
            console.print("[dim]Unwrap operation cancelled.[/dim]")
            raise typer.Exit(code=0)

        if not result.success:
            console.print(f"[red]Unwrap failed:[/red] {result.message}")
            raise typer.Exit(code=1)

        print_section(
            title="SchemaSlim Rollback",
            lines=[
                ("client", str(result.client_name)),
                ("target", str(result.target_path)),
                ("status", "[green]Original configuration restored[/green]"),
            ],
        )
        console.print(f"[green]✓ {result.message}[/green]")

    except MigrationError as e:
        console.print(f"[red]Rollback Error:[/red] {e}")
        raise typer.Exit(code=1)


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
        console.print(
            f"[red]Error:[/red] Invalid output format '{output}'. Choose 'table' or 'json'."
        )
        raise typer.Exit(code=1)

    if output == "json":
        setup_logger(level="ERROR")
    else:
        console.print(
            f"[dim]Running SchemaSlim synthetic virtualization benchmark ({runs} iterations)...[/dim]"
        )

    from schemaslim.benchmark import BenchmarkRunner

    runner = BenchmarkRunner()
    report = runner.run(runs=runs)

    if output == "json":
        sys.stdout.write(report.model_dump_json(indent=2) + "\n")
        return

    print_section(
        title="Context Virtualization Benchmark Summary",
        lines=[
            ("servers", f"{report.servers_count} synthetic  •  {report.total_tools} tools"),
            (
                "context",
                f"{report.tokens_baseline:,} raw tokens  ›  ~{report.avg_tokens_virtualized:,} virtualized  •  [green]+{report.avg_tokens_saved:,} saved/turn (~{report.compression_pct:.1f}%)[/green]",
            ),
            (
                "latency",
                f"{report.latency_mean_ms:.2f}ms mean  •  p50: {report.latency_p50_ms:.2f}ms  •  p95: {report.latency_p95_ms:.2f}ms",
            ),
        ],
    )

    prefix = "◆ Benchmark Intent Query Breakdown "
    console.print(f"[bold white]{prefix}[/bold white][dim]{'─' * max(3, 58 - len(prefix))}[/dim]")
    for i, q in enumerate(report.queries_detail, 1):
        console.print(f"  [dim]#{i}[/dim] [white]{q.query}[/white]")
        console.print(
            f"     [dim]›[/dim] [white]{q.matched_tool}[/white]  •  [dim]score:[/dim] [green]{q.score:.3f}[/green]  •  [dim]latency:[/dim] {q.latency_ms:.1f}ms  •  [green]+{q.tokens_saved:,} tok[/green] (~{q.compression_pct:.1f}%)"
        )
    console.print()

    console.print(
        f"[green]✓ Benchmark complete:[/green] Achieved [bold]{report.compression_pct:.1f}%[/bold] token reduction with [bold]{report.latency_mean_ms:.1f}ms[/bold] avg routing latency."
    )


if __name__ == "__main__":
    app()
