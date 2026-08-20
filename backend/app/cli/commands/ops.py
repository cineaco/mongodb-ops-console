import time
from typing import Optional
import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Trigger Day-2 cluster operations (restarts, backups, users, deploys)")


def _handle_op_execution(
    client: APIClient,
    cluster_id: str,
    job_id: str,
    operation_name: str,
    async_mode: bool,
    format_type: str,
) -> None:
    if async_mode or format_type in ("json", "yaml"):
        formatters.print_output(
            {"job_id": job_id, "operation": operation_name, "status": "pending"},
            format_type=format_type,
        )
        if not async_mode:
            formatters.print_info(f"Job triggered in async mode. Run 'mgops logs show {job_id} --follow' to view output.")
        return

    formatters.print_success(f"Triggered operation '{operation_name}' (Job ID: {job_id})")
    formatters.console.print("[dim]Streaming execution progress...[/dim]\n")

    # 1. Stream live SSE logs
    try:
        for line in client.stream_sse_logs(cluster_id, job_id):
            formatters.console.print(line, highlight=False)
    except KeyboardInterrupt:
        formatters.print_info(f"Detached from log stream. Run 'mgops logs show {job_id}' to check status.")
        return

    # 2. Check final job state
    job_final = client.get(f"/api/jobs/{job_id}")
    status = job_final.get("status")
    if status == "completed":
        formatters.print_success(f"Operation '{operation_name}' completed successfully.")
    elif status == "failed":
        formatters.print_error(f"Operation '{operation_name}' failed.")
    else:
        formatters.print_info(f"Job finished with status: {status}")


@app.command("restart-node")
def restart_node(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    hostname: str = typer.Option(..., "--hostname", "-h", help="Target node hostname to restart"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Restart a specific MongoDB cluster node."""
    client = APIClient()
    res = client.post(f"/api/clusters/{cluster_id}/ops/restart-node", json_body={"hostname": hostname})
    _handle_op_execution(client, cluster_id, res["job_id"], "restart_node", async_mode, format_type)


@app.command("rolling-restart")
def rolling_restart(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Execute rolling restart across all nodes in the cluster."""
    client = APIClient()
    res = client.post(f"/api/clusters/{cluster_id}/ops/rolling-restart")
    _handle_op_execution(client, cluster_id, res["job_id"], "rolling_restart", async_mode, format_type)


@app.command("rotate-password")
def rotate_password(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    new_password: str = typer.Option(..., "--new-password", "-p", help="New admin password"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Rotate MongoDB admin database password."""
    client = APIClient()
    res = client.post(f"/api/clusters/{cluster_id}/ops/rotate-password", json_body={"new_password": new_password})
    _handle_op_execution(client, cluster_id, res["job_id"], "rotate_admin_password", async_mode, format_type)


@app.command("create-user")
def create_user(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    username: str = typer.Option(..., "--username", "-u", help="New database username"),
    password: str = typer.Option(..., "--password", "-p", help="Password for new user"),
    database: str = typer.Option("appdb", "--db", help="Target database name"),
    roles: str = typer.Option("readWrite", "--roles", help="Comma-separated roles (e.g. readWrite,dbAdmin)"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Create a new MongoDB application user."""
    client = APIClient()
    role_list = [r.strip() for r in roles.split(",")]
    res = client.post(
        f"/api/clusters/{cluster_id}/ops/create-user",
        json_body={"db_name": database, "username": username, "password": password, "roles": role_list},
    )
    _handle_op_execution(client, cluster_id, res["job_id"], "create_app_user", async_mode, format_type)


@app.command("delete-user")
def delete_user(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    username: str = typer.Option(..., "--username", "-u", help="Username to delete"),
    database: str = typer.Option("appdb", "--db", help="Database name"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Delete a MongoDB application user."""
    client = APIClient()
    res = client.post(
        f"/api/clusters/{cluster_id}/ops/delete-user",
        json_body={"db_name": database, "username": username},
    )
    _handle_op_execution(client, cluster_id, res["job_id"], "delete_app_user", async_mode, format_type)


@app.command("backup")
def backup(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Trigger a PBM (Percona Backup for MongoDB) snapshot backup."""
    client = APIClient()
    res = client.post(f"/api/clusters/{cluster_id}/ops/pbm-backup")
    _handle_op_execution(client, cluster_id, res["job_id"], "pbm_backup", async_mode, format_type)


@app.command("restore")
def restore(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    snapshot_name: str = typer.Option(..., "--snapshot", "-s", help="PBM backup snapshot name"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Restore a PBM backup snapshot."""
    client = APIClient()
    res = client.post(f"/api/clusters/{cluster_id}/ops/pbm-restore", json_body={"snapshot_name": snapshot_name})
    _handle_op_execution(client, cluster_id, res["job_id"], "pbm_restore", async_mode, format_type)


@app.command("deploy")
def deploy(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated Ansible tags (e.g. install,config,replication)"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Trigger full Ansible cluster deployment."""
    client = APIClient()
    tag_list = [t.strip() for t in tags.split(",")] if tags else None
    res = client.post(f"/api/clusters/{cluster_id}/ops/deploy", json_body={"tags": tag_list} if tag_list else {})
    _handle_op_execution(client, cluster_id, res["job_id"], "deploy", async_mode, format_type)


@app.command("rerun")
def rerun(
    cluster_id: str = typer.Option(..., "--cluster-id", "-c", help="Target Cluster UUID"),
    tags: str = typer.Option(..., "--tags", help="Comma-separated Ansible tags to rerun"),
    async_mode: bool = typer.Option(False, "--async", "--no-wait", help="Do not wait for job completion"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Re-run specific Ansible tags against an existing cluster."""
    client = APIClient()
    tag_list = [t.strip() for t in tags.split(",")]
    res = client.post(f"/api/clusters/{cluster_id}/ops/rerun", json_body={"tags": tag_list})
    _handle_op_execution(client, cluster_id, res["job_id"], "rerun", async_mode, format_type)
