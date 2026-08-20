import time
from typing import Optional
import typer

from app.cli import formatters
from app.cli.client import APIClient

app = typer.Typer(help="Job log inspection & real-time log streaming")


@app.command("show")
def logs(
    job_id: str = typer.Argument(..., help="Job UUID"),
    follow: bool = typer.Option(False, "--follow", "-f", help="Stream live job execution logs via SSE"),
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """View execution logs for a job. Use -f/--follow to stream live output."""
    client = APIClient()
    job = client.get(f"/api/jobs/{job_id}")

    if format_type in ("json", "yaml"):
        formatters.print_output(job, format_type=format_type)
        return

    formatters.console.print(f"[bold cyan]Job Overview ({job_id})[/bold cyan]")
    formatters.print_output(
        {
            "id": job["id"],
            "cluster_id": job["cluster_id"],
            "operation": job["operation"],
            "status": job["status"],
            "started_at": job.get("started_at") or "Pending",
            "completed_at": job.get("completed_at") or "-",
        },
        format_type="table",
    )

    result = job.get("result") or {}
    existing_log = result.get("log") or ""

    if existing_log:
        formatters.console.print("\n[bold yellow]--- Execution Logs ---[/bold yellow]")
        formatters.console.print(existing_log)

    if follow:
        if job.get("status") in ("completed", "failed", "cancelled"):
            formatters.print_info(f"Job is already finished with status: {job.get('status')}")
            return

        cluster_id = job["cluster_id"]
        formatters.console.print(f"\n[bold green]Streaming live logs for job {job_id}... (Press Ctrl+C to stop)[/bold green]\n")
        try:
            for line in client.stream_sse_logs(cluster_id, job_id):
                formatters.console.print(line, highlight=False)
        except KeyboardInterrupt:
            formatters.print_info("Detached from log stream.")
