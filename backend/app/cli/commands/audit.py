from typing import Optional
import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Audit trail inspection commands")


@app.command("list")
def list_audit(
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Filter by username"),
    action: Optional[str] = typer.Option(None, "--action", "-a", help="Filter by action name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max records to return"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """View recent audit trail log events."""
    client = APIClient()
    params = {"limit": limit}
    if username:
        params["username"] = username
    if action:
        params["action"] = action

    audit_logs = client.get("/api/audit", params=params)
    formatters.print_output(audit_logs, format_type=format_type, table_title="Audit Trail Logs")
