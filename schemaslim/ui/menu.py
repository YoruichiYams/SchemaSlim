"""Minimalist terminal interactive prompt and key reader matching SchemaSlim reference aesthetic."""

import sys
from typing import List, Optional, Tuple
from rich.console import Console
from rich.live import Live
from rich.text import Text


def make_header(title: str, width: int = 58) -> str:
    """Generate a clean monochrome section header line with ◆ glyph."""
    prefix = f"◆ {title.upper()} "
    remaining = max(3, width - len(prefix))
    return f"{prefix}{'─' * remaining}"


def _read_key() -> str:
    """Read a single keypress cross-platform without third-party dependencies."""
    if sys.platform == "win32":
        import msvcrt

        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            if ch2 == "H":
                return "UP"
            elif ch2 == "P":
                return "DOWN"
            return "OTHER"
        if ch in ("\r", "\n"):
            return "ENTER"
        if ch == " ":
            return "SPACE"
        if ch in ("\x03", "\x1a"):
            raise KeyboardInterrupt()
        if ch.lower() in ("y", "n", "q"):
            return ch.lower()
        return ch
    else:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == "\x1b":
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    if ch3 == "A":
                        return "UP"
                    elif ch3 == "B":
                        return "DOWN"
                return "ESC"
            elif ch in ("\r", "\n"):
                return "ENTER"
            elif ch == " ":
                return "SPACE"
            elif ch == "\x03":
                raise KeyboardInterrupt()
            elif ch.lower() in ("y", "n", "q"):
                return ch.lower()
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def prompt_confirmation(
    title: str = "MIGRATION CONFIRMATION",
    lines: Optional[List[Tuple[str, str]]] = None,
    confirm_label: str = "Apply migration",
    cancel_label: str = "Cancel",
    default: bool = True,
    console: Optional[Console] = None,
) -> bool:
    """Prompt user with an interactive binary selector in SchemaSlim reference style.

    Navigation:
      [Space] or [Up/Down]: toggle selection
      [Enter]: confirm selection
      [y/n]: quick select

    Falls back to `default` if stdin is not an interactive terminal.
    """
    cons = console or Console()

    if not sys.stdin.isatty():
        return default

    selected_idx = 0 if default else 1

    def _render(idx: int) -> Text:
        t = Text()
        header_text = title if title.startswith("◆") else make_header(title)
        t.append(f"{header_text}\n", style="bold white")

        if lines:
            for key, val in lines:
                t.append(f"  {key:<7} ", style="dim")
                t.append("› ", style="dim")
                t.append(f"{val}\n", style="white")
            t.append("\n")

        t.append("  Use [Space] to toggle, [Enter] to confirm:\n\n", style="dim")

        if idx == 0:
            t.append("  › ", style="bold green")
            t.append("[●] ", style="bold green")
            t.append(f"{confirm_label}\n", style="bold white")
            t.append("    [○] ", style="dim")
            t.append(f"{cancel_label}\n", style="dim")
        else:
            t.append("    [○] ", style="dim")
            t.append(f"{confirm_label}\n", style="dim")
            t.append("  › ", style="bold red")
            t.append("[●] ", style="bold red")
            t.append(f"{cancel_label}\n", style="bold white")
        return t

    try:
        with Live(_render(selected_idx), console=cons, auto_refresh=False, transient=True) as live:
            while True:
                key = _read_key()
                if key in ("SPACE", "UP", "DOWN"):
                    selected_idx = 1 - selected_idx
                    live.update(_render(selected_idx), refresh=True)
                elif key == "ENTER":
                    break
                elif key == "y":
                    selected_idx = 0
                    break
                elif key in ("n", "q"):
                    selected_idx = 1
                    break
    except (KeyboardInterrupt, EOFError):
        cons.print("\n[dim]Cancelled.[/dim]")
        return False

    return selected_idx == 0


def select_option(
    title: str = "SELECT CLIENT CONFIGURATION",
    options: Optional[List[Tuple[str, str]]] = None,
    default_index: int = 0,
    console: Optional[Console] = None,
) -> int:
    """Prompt user to select an item from a list of options in reference style.

    Args:
        title: Header prompt string.
        options: List of (label, detail) tuples.
        default_index: Initially selected index.
        console: Optional Rich Console.

    Returns:
        Chosen option index (0 to len(options)-1).
    """
    cons = console or Console()
    opt_list = options or []

    if not sys.stdin.isatty() or len(opt_list) <= 1:
        return default_index

    current_idx = min(max(0, default_index), len(opt_list) - 1)

    def _render(idx: int) -> Text:
        t = Text()
        header_text = title if title.startswith("◆") else make_header(title)
        t.append(f"{header_text}\n", style="bold white")
        t.append("  Use [↑/↓] to navigate, [Enter] to select:\n\n", style="dim")

        for i, (label, detail) in enumerate(opt_list):
            if i == idx:
                t.append("  › [●] ", style="bold green")
                t.append(f"{label} ", style="bold white")
                if detail:
                    t.append(f"• {detail}", style="dim")
                t.append("\n")
            else:
                t.append("    [○] ", style="dim")
                t.append(f"{label} ", style="dim white")
                if detail:
                    t.append(f"• {detail}", style="dim")
                t.append("\n")
        return t

    try:
        with Live(_render(current_idx), console=cons, auto_refresh=False, transient=True) as live:
            while True:
                key = _read_key()
                if key == "UP":
                    current_idx = (current_idx - 1) % len(opt_list)
                    live.update(_render(current_idx), refresh=True)
                elif key == "DOWN" or key == "SPACE":
                    current_idx = (current_idx + 1) % len(opt_list)
                    live.update(_render(current_idx), refresh=True)
                elif key == "ENTER":
                    break
                elif key in ("q", "n"):
                    break
    except (KeyboardInterrupt, EOFError):
        return default_index

    return current_idx
