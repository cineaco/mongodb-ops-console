import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Overview status of services, clusters, alerts, and pending jobs")


@app.command("status")
def status(
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Show operational status of MongoDB Ops Console, clusters, health, and active alerts."""
    client = APIClient()

    # 1. API Health
    health_data = {"status": "unreachable"}
    try:
        health_data = client.get("/api/health")
    except Exception as e:
        health_data = {"status": "unreachable", "error": str(e)}

    # 2. Clusters summary
    clusters = client.get("/api/clusters")
    healthy_count = sum(1 for c in clusters if c.get("status") == "healthy")
    deploying_count = sum(1 for c in clusters if c.get("status") == "deploying")
    failed_count = sum(1 for c in clusters if c.get("status") == "failed")

    # 3. Active alerts
    alerts = client.get("/api/alerts", params={"resolved": False})
    critical_alerts = sum(1 for a in alerts if a.get("severity") == "critical")
    warning_alerts = sum(1 for a in alerts if a.get("severity") == "warning")

    # 4. Profile
    user_me = client.get("/api/auth/me")

    summary_dict = {
        "api_health": health_data.get("status", "ok"),
        "authenticated_as": f"{user_me.get('username')} ({user_me.get('role')})",
        "total_clusters": len(clusters),
        "healthy_clusters": healthy_count,
        "deploying_clusters": deploying_count,
        "failed_clusters": failed_count,
        "active_alerts_total": len(alerts),
        "critical_alerts": critical_alerts,
        "warning_alerts": warning_alerts,
    }

    if format_type in ("json", "yaml"):
        summary_full = {
            "summary": summary_dict,
            "clusters": clusters,
            "active_alerts": alerts,
        }
        formatters.print_output(summary_full, format_type=format_type)
        return

    formatters.console.print("\n[bold cyan]═══ MongoDB Ops Console Operational Status ═══[/bold cyan]\n")
    formatters.print_output(summary_dict, format_type="table", table_title="System Overview")

    if clusters:
        formatters.console.print("\n[bold cyan]Managed Clusters:[/bold cyan]")
        cluster_summary = [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "topology": c.get("topology"),
                "version": c.get("mongodb_version"),
                "status": c.get("status"),
                "last_deployed": c.get("last_deployed_at") or "Never",
            }
            for c in clusters
        ]
        formatters.print_output(cluster_summary, format_type="table")

    if alerts:
        formatters.console.print("\n[bold red]Active Alerts:[/bold red]")
        alert_summary = [
            {
                "id": a.get("id"),
                "cluster_name": a.get("cluster_name"),
                "severity": a.get("severity"),
                "metric_type": a.get("metric_type"),
                "message": a.get("message"),
                "triggered_at": a.get("triggered_at"),
            }
            for a in alerts[:5]
        ]
        formatters.print_output(alert_summary, format_type="table")
