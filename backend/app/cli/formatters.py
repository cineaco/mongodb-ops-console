import json
import sys
from typing import Any, Sequence
import yaml

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()
error_console = Console(stderr=True)


def format_status_badge(status: str) -> Text:
    status_lower = (status or "").lower()
    if status_lower in ("healthy", "completed", "ok", "active"):
        return Text(f"● {status}", style="bold green")
    elif status_lower in ("deploying", "running", "pending", "in_progress"):
        return Text(f"⟳ {status}", style="bold yellow")
    elif status_lower in ("failed", "error", "critical"):
        return Text(f"✖ {status}", style="bold red")
    elif status_lower in ("warning", "degraded"):
        return Text(f"▲ {status}", style="bold orange1")
    return Text(status or "unknown", style="dim")


def print_output(data: Any, format_type: str = "table", table_title: str = "", fields: Sequence[str] | None = None) -> None:
    if format_type == "json":
        console.print_json(data=data)
        return
    elif format_type == "yaml":
        yaml_str = yaml.dump(data, default_flow_style=False)
        console.print(yaml_str, end="")
        return

    # Table output
    if isinstance(data, list):
        if not data:
            console.print("[dim]No records found.[/dim]")
            return
        
        table = Table(title=table_title or None, show_header=True, header_style="bold cyan")
        
        # Determine columns
        sample = data[0] if isinstance(data[0], dict) else {}
        cols = list(fields) if fields else list(sample.keys())
        
        for col in cols:
            table.add_column(col.replace("_", " ").title())
            
        for row in data:
            if isinstance(row, dict):
                row_vals = []
                for col in cols:
                    val = row.get(col, "")
                    if col in ("status", "health", "state") and isinstance(val, str):
                        row_vals.append(format_status_badge(val))
                    elif isinstance(val, (dict, list)):
                        row_vals.append(json.dumps(val))
                    else:
                        row_vals.append(str(val) if val is not None else "")
                table.add_row(*row_vals)
        console.print(table)
    elif isinstance(data, dict):
        table = Table(title=table_title or None, show_header=True, header_style="bold cyan")
        table.add_column("Property", style="bold white")
        table.add_column("Value")
        
        for k, v in data.items():
            if k in ("status", "health", "state") and isinstance(v, str):
                val_rendered = format_status_badge(v)
            elif isinstance(v, (dict, list)):
                val_rendered = json.dumps(v, indent=2)
            else:
                val_rendered = str(v) if v is not None else ""
            table.add_row(k.replace("_", " ").title(), val_rendered)
        console.print(table)
    else:
        console.print(str(data))


def print_error(msg: str) -> None:
    error_console.print(f"[bold red]Error:[/bold red] {msg}")


def print_success(msg: str) -> None:
    console.print(f"[bold green]✓[/bold green] {msg}")


def print_info(msg: str) -> None:
    console.print(f"[bold blue]ℹ[/bold blue] {msg}")
