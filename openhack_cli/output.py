"""Rendering helpers shared by all commands.

Every command supports two modes:
  - human: Rich tables / panels (default, when stdout is a TTY or not --json)
  - json:  raw machine-readable JSON for agents and scripts (--json)

The active mode is carried on the Click context object (``ctx.obj``).
"""

from __future__ import annotations

import json as _json
import sys
from typing import Any, Optional, Sequence

import click
from rich.console import Console
from rich.table import Table

console = Console()
err_console = Console(stderr=True)

# Severity ordering + colors reused across scans / findings / pentest output.
SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SEVERITY_COLORS = {
    "critical": "bright_red",
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
    "info": "blue",
}
STATUS_COLORS = {
    "completed": "green",
    "approved": "green",
    "in_progress": "yellow",
    "pending": "yellow",
    "draft": "dim",
    "failed": "red",
    # A deliberate cancel is not a failure — the dashboard renders it muted, so
    # don't colour it like an error here either.
    "cancelled": "dim",
}


def severity_label(sev: Optional[str]) -> str:
    if not sev:
        return "[dim]-[/dim]"
    color = SEVERITY_COLORS.get(sev.lower(), "white")
    return f"[{color}]{sev.upper()}[/{color}]"


def status_label(status: Optional[str]) -> str:
    if not status:
        return "[dim]-[/dim]"
    color = STATUS_COLORS.get(status.lower(), "white")
    return f"[{color}]{status}[/{color}]"


def print_json(data: Any) -> None:
    """Emit raw JSON to stdout (machine mode)."""
    click.echo(_json.dumps(data, indent=2, default=str))


def emit(ctx_obj: dict, data: Any, render) -> None:
    """Print JSON when --json is set, otherwise call ``render(data)``."""
    if ctx_obj.get("json"):
        print_json(data)
    else:
        render(data)


def make_table(title: Optional[str], columns: Sequence[str]) -> Table:
    table = Table(title=title, title_justify="left", header_style="bold",
                  expand=False, pad_edge=False)
    for col in columns:
        table.add_column(col, overflow="fold")
    return table


def info(message: str) -> None:
    err_console.print(message)


def success(message: str) -> None:
    err_console.print(f"[green]✓[/green] {message}")


def warn(message: str) -> None:
    err_console.print(f"[yellow]![/yellow] {message}")


def error(message: str) -> None:
    err_console.print(f"[red]✗[/red] {message}")


def fail(message: str, code: int = 1) -> "click.ClickException":
    """Print an error and exit with a non-zero code."""
    error(message)
    sys.exit(code)


def short(value: Optional[str], length: int = 36) -> str:
    if not value:
        return "-"
    value = str(value)
    return value if len(value) <= length else value[: length - 1] + "…"
