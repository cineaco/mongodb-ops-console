from typing import Optional
import typer

from app.cli import config, formatters
from app.cli.client import APIClient

app = typer.Typer(help="Authentication & user session commands")


@app.command("login")
def login(
    username: Optional[str] = typer.Option(None, "--username", "-u", help="Username for authentication"),
    password: Optional[str] = typer.Option(None, "--password", "-p", help="Password for authentication"),
    url: Optional[str] = typer.Option(None, "--url", help="API base URL (default: http://localhost:8000)"),
):
    """Authenticate with MongoDB Ops Console API and save session token."""
    api_url = (url or config.load_config().get("api_url") or config.DEFAULT_API_URL).rstrip("/")

    if not username:
        username = typer.prompt("Username")
    if not password:
        password = typer.prompt("Password", hide_input=True)

    client = APIClient(override_url=api_url)
    res = client.post("/api/auth/login", json_body={"username": username, "password": password})
    
    access_token = res["access_token"]
    refresh_token = res.get("refresh_token")
    
    cfg = config.update_tokens(access_token, refresh_token, api_url=api_url)
    formatters.print_success(f"Successfully logged in as '{username}' to {api_url}")
    formatters.print_info(f"Session configuration saved to {config.get_config_path()}")


@app.command("logout")
def logout():
    """Logout and revoke session refresh token."""
    cfg = config.load_config()
    if cfg.get("refresh_token"):
        try:
            client = APIClient()
            client.post("/api/auth/logout", json_body={"refresh_token": cfg["refresh_token"]})
        except Exception:
            pass
    config.clear_tokens()
    formatters.print_success("Logged out successfully.")


@app.command("whoami")
def whoami(
    format_type: str = typer.Option("table", "--output", "-o", help="Output format: table, json, yaml"),
):
    """Show details of the currently authenticated user."""
    client = APIClient()
    me_data = client.get("/api/auth/me")
    formatters.print_output(me_data, format_type=format_type, table_title="Current User Profile")
