from typing import Optional
import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Cluster registry & topology commands")


@app.command("list")
def list_clusters(
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """List all registered MongoDB clusters."""
    client = APIClient()
    clusters = client.get("/api/clusters")
    formatters.print_output(clusters, format_type=format_type, table_title="Cluster Registry")


@app.command("get")
def get_cluster(
    cluster_id: str = typer.Argument(..., help="Cluster UUID"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Get detailed information for a specific MongoDB cluster."""
    client = APIClient()
    cluster = client.get(f"/api/clusters/{cluster_id}")
    formatters.print_output(cluster, format_type=format_type, table_title=f"Cluster Details: {cluster.get('name')}")


@app.command("hosts")
def list_hosts(
    cluster_id: str = typer.Argument(..., help="Cluster UUID"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """List all member nodes/hosts for a cluster."""
    client = APIClient()
    hosts = client.get(f"/api/clusters/{cluster_id}/hosts")
    formatters.print_output(hosts, format_type=format_type, table_title="Cluster Nodes & Hosts")


@app.command("metrics")
def get_metrics(
    cluster_id: str = typer.Argument(..., help="Cluster UUID"),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of telemetry data points to fetch"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Fetch telemetry metrics for a cluster."""
    client = APIClient()
    metrics = client.get(f"/api/clusters/{cluster_id}/metrics", params={"limit": limit})
    formatters.print_output(metrics, format_type=format_type, table_title="Recent Telemetry Metrics")
