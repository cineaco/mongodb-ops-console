from typing import Optional
import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Cluster threshold alerting commands")


@app.command("list")
def list_alerts(
    cluster_id: Optional[str] = typer.Option(None, "--cluster-id", "-c", help="Filter by Cluster UUID"),
    resolved: Optional[bool] = typer.Option(False, "--resolved/--unresolved", help="Filter resolved vs active alerts"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """List active or historical cluster alerts."""
    client = APIClient()
    params = {}
    if cluster_id:
        params["cluster_id"] = cluster_id
    if resolved is not None:
        params["resolved"] = str(resolved).lower()

    alerts = client.get("/api/alerts", params=params)
    formatters.print_output(alerts, format_type=format_type, table_title="Cluster Alerts")


@app.command("ack")
def ack_alert(
    alert_id: str = typer.Argument(..., help="Alert UUID"),
):
    """Acknowledge an active alert."""
    client = APIClient()
    res = client.post(f"/api/alerts/{alert_id}/ack")
    formatters.print_success(f"Alert {alert_id} acknowledged.")


@app.command("resolve")
def resolve_alert(
    alert_id: str = typer.Argument(..., help="Alert UUID"),
):
    """Mark an alert as resolved."""
    client = APIClient()
    res = client.post(f"/api/alerts/{alert_id}/resolve")
    formatters.print_success(f"Alert {alert_id} resolved.")
