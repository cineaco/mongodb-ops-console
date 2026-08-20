import typer

from app.cli import config
from app.cli.commands.alerts import app as alerts_app
from app.cli.commands.audit import app as audit_app
from app.cli.commands.auth import app as auth_app
from app.cli.commands.clusters import app as clusters_app
from app.cli.commands.logs import app as logs_app
from app.cli.commands.ops import app as ops_app
from app.cli.commands.status import app as status_app

app = typer.Typer(
    name="mgops",
    help="MongoDB Ops Console Command-Line Utility",
    no_args_is_help=True,
    add_completion=False,
)

# Attach top-level command groups
app.add_typer(auth_app, name="auth")
app.add_typer(clusters_app, name="clusters")
app.add_typer(logs_app, name="logs")
app.add_typer(ops_app, name="ops")
app.add_typer(alerts_app, name="alerts")
app.add_typer(audit_app, name="audit")

# Include direct top-level shortcuts for frequent commands
app.command("login")(auth_app.registered_commands[0].callback)
app.command("logout")(auth_app.registered_commands[1].callback)
app.command("whoami")(auth_app.registered_commands[2].callback)
app.command("status")(status_app.registered_commands[0].callback)


if __name__ == "__main__":
    app()
