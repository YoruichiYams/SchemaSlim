"""Logging setup using Rich for enhanced terminal formatting."""

import logging
import sys
from typing import Optional
from rich.console import Console
from rich.logging import RichHandler

# Ensure UTF-8 stream handling on Windows to prevent UnicodeEncodeError in non-ASCII paths
if sys.platform == "win32":
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_console = Console(stderr=True, legacy_windows=False)


def setup_logger(
    level: str = "INFO",
    name: str = "schemaslim",
    show_time: bool = True,
    show_path: bool = False,
) -> logging.Logger:
    """Configure and return a structured logger with Rich handler.

    Args:
        level: Log level (e.g. DEBUG, INFO, WARNING, ERROR).
        name: Logger name.
        show_time: Whether to render timestamp.
        show_path: Whether to render file path and line number.

    Returns:
        Configured logging.Logger instance.
    """
    logger = logging.getLogger(name)
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Avoid adding multiple handlers on repeated setup calls
    if not any(isinstance(h, RichHandler) for h in logger.handlers):
        handler = RichHandler(
            console=_console,
            show_time=show_time,
            show_path=show_path,
            rich_tracebacks=True,
            tracebacks_show_locals=False,
            markup=True,
        )
        handler.setLevel(numeric_level)
        formatter = logging.Formatter("%(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.propagate = False
    else:
        for handler in logger.handlers:
            if isinstance(handler, RichHandler):
                handler.setLevel(numeric_level)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Retrieve logger instance. Defaults to 'schemaslim' if not provided."""
    target_name = f"schemaslim.{name}" if name else "schemaslim"
    logger = logging.getLogger(target_name)
    if not logger.handlers:
        setup_logger(name=target_name)
    return logger
