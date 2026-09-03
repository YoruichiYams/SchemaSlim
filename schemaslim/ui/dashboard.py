"""Real-time Terminal UI (TUI) Dashboard for SchemaSlim using Rich."""

import asyncio
import datetime
import sys
from typing import List, Optional, Sequence

from rich.console import Console, Group
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from schemaslim import __version__
from schemaslim.telemetry.tracker import TelemetryTracker, get_tracker


def create_header(active_servers: Optional[Sequence[str]] = None) -> Panel:
    """Render the header panel displaying SchemaSlim version and active servers."""
    servers_list = list(active_servers or [])
    servers_count = len(servers_list)
    if servers_count > 0:
        servers_display = f"{servers_count} active ({', '.join(servers_list[:4])}{'...' if servers_count > 4 else ''})"
    else:
        servers_display = "none"

    header_text = Text()
    header_text.append("⚡ SchemaSlim ", style="bold cyan")
    header_text.append(f"v{__version__}", style="bold green")
    header_text.append(" │ Mode: ", style="dim")
    header_text.append("Virtualizing Stdio Proxy", style="bold white")
    header_text.append(" │ Servers: ", style="dim")
    header_text.append(servers_display, style="bold yellow")

    return Panel(
        header_text,
        border_style="cyan",
        padding=(0, 1),
    )


def create_metrics_panel(tracker: TelemetryTracker) -> Panel:
    """Render the 3-column aggregate metrics panel."""
    summary = tracker.get_summary()

    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column("Tokens", ratio=4)
    grid.add_column("Footprint", ratio=3)
    grid.add_column("Performance", ratio=3)

    # Column 1: Token Economy
    col1 = Text()
    col1.append("TOKEN SAVINGS\n", style="bold underline white")
    saved_str = f"{summary.total_tokens_saved:,}"
    col1.append(f"• Saved: {saved_str} tokens ", style="bold green")
    col1.append(f"(~{summary.avg_compression_pct:.1f}%)\n", style="bold cyan")
    col1.append(
        f"• Requests: {summary.total_requests} (Search: {summary.search_requests} │ Call: {summary.call_requests} │ Err: {summary.error_requests})",
        style="dim white",
    )

    # Column 2: Context Footprint
    col2 = Text()
    col2.append("CONTEXT FOOTPRINT\n", style="bold underline white")
    col2.append(f"• Baseline Catalog: {summary.baseline_catalog_tokens:,} tok\n", style="yellow")
    col2.append(f"• Proxied Footprint: {summary.total_tokens_actual:,} tok", style="cyan")

    # Column 3: Routing Latency
    col3 = Text()
    col3.append("ROUTING LATENCY\n", style="bold underline white")
    col3.append(f"• Avg Total: {summary.avg_latency_ms:.2f} ms\n", style="bold white")
    col3.append(
        f"• Search: {summary.avg_search_latency_ms:.1f}ms │ Call: {summary.avg_call_latency_ms:.1f}ms",
        style="dim white",
    )

    grid.add_row(col1, col2, col3)

    return Panel(grid, title="[bold]Session Metrics[/bold]", border_style="green", padding=(0, 1))


def create_request_feed(tracker: TelemetryTracker, limit: int = 8) -> Panel:
    """Render the live request feed table showing recent events."""
    events = tracker.get_recent_events(limit=limit)

    table = Table(expand=True, border_style="dim", header_style="bold cyan", pad_edge=False)
    table.add_column("Time", justify="center", width=10, style="dim")
    table.add_column("Type", justify="center", width=8)
    table.add_column("Tool / Query", ratio=4, no_wrap=True)
    table.add_column("Latency", justify="right", width=10)
    table.add_column("Status", justify="center", width=9)
    table.add_column("Tokens Saved", justify="right", width=16)

    if not events:
        table.add_row(
            "-",
            "-",
            "[dim italic]Waiting for incoming MCP requests...[/dim italic]",
            "-",
            "-",
            "-",
        )
    else:
        for ev in events:
            time_str = datetime.datetime.fromtimestamp(ev.timestamp).strftime("%H:%M:%S")
            type_str = (
                "[bold cyan]SEARCH[/bold cyan]"
                if ev.event_type == "search"
                else "[bold magenta]CALL[/bold magenta]"
            )
            # Truncate long tool names or queries
            display_name = ev.tool_name
            if len(display_name) > 42:
                display_name = display_name[:39] + "..."

            status_str = (
                "[green]✓ ok[/green]" if ev.status == "success" else "[red]✗ err[/red]"
            )
            saved_str = (
                f"[bold green]+{ev.tokens_saved:,} tok[/bold green]"
                if ev.tokens_saved > 0
                else "[dim]0 tok[/dim]"
            )
            lat_str = f"{ev.latency_ms:.1f} ms"

            table.add_row(
                time_str,
                type_str,
                display_name,
                lat_str,
                status_str,
                saved_str,
            )

    return Panel(table, title="[bold]Live Request Feed[/bold]", border_style="blue", padding=(0, 0))


def render_dashboard(
    tracker: TelemetryTracker,
    active_servers: Optional[Sequence[str]] = None,
    feed_limit: int = 8,
) -> Group:
    """Assemble the complete dashboard renderable group."""
    return Group(
        create_header(active_servers=active_servers),
        create_metrics_panel(tracker),
        create_request_feed(tracker, limit=feed_limit),
    )


class DashboardRunner:
    """Asynchronous runner for updating the live Rich dashboard on stderr."""

    def __init__(
        self,
        tracker: Optional[TelemetryTracker] = None,
        active_servers: Optional[Sequence[str]] = None,
        console: Optional[Console] = None,
        refresh_interval: float = 0.3,
    ) -> None:
        self.tracker = tracker or get_tracker()
        self.active_servers = list(active_servers or [])
        # CRITICAL: console strictly renders to stderr to maintain stdout purity for stdio MCP
        self.console = console or Console(stderr=True, legacy_windows=False)
        self.refresh_interval = refresh_interval
        self._live: Optional[Live] = None
        self._task: Optional[asyncio.Task] = None
        self._running = False

    def update_servers(self, servers: Sequence[str]) -> None:
        """Update active servers list dynamically."""
        self.active_servers = list(servers)

    async def start(self) -> None:
        """Start the live updating dashboard on stderr."""
        if self._running:
            return

        self._running = True
        self._live = Live(
            render_dashboard(self.tracker, self.active_servers),
            console=self.console,
            refresh_per_second=4,
            transient=False,
            auto_refresh=False,
        )
        self._live.start()
        self._task = asyncio.create_task(self._refresh_loop())

    async def _refresh_loop(self) -> None:
        """Background loop updating live display."""
        try:
            while self._running and self._live is not None:
                self._live.update(
                    render_dashboard(self.tracker, self.active_servers),
                    refresh=True,
                )
                await asyncio.sleep(self.refresh_interval)
        except asyncio.CancelledError:
            pass

    async def stop(self) -> None:
        """Stop the live dashboard cleanly."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        if self._live is not None:
            try:
                # Final refresh
                self._live.update(
                    render_dashboard(self.tracker, self.active_servers),
                    refresh=True,
                )
                self._live.stop()
            except Exception:
                pass
            self._live = None
