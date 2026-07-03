"""OpenHack CLI entrypoint.

Wires the command groups together, sets up the shared Click context (config +
output mode), and provides uniform error handling for API/auth failures.
"""

from __future__ import annotations

import sys

import click

from . import __version__, output
from .client import APIError, AuthError
from .commands.auth import auth
from .commands.config_cmd import config
from .commands.orgs import orgs
from .commands.pentest import pentest
from .commands.projects import projects
from .commands.scans import scans
from .commands.vulns import vulns
from .config import Config, LOCAL_APP_URL

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-v", "--version", prog_name="openhack-cli")
@click.option("--json", "json_output", is_flag=True,
              help="Output raw JSON (for scripts and agents).")
@click.option("--app-url", default=None, help="Override the OpenHack app URL.")
@click.option("--local", "use_local", is_flag=True,
              help=f"Target the local dev server ({LOCAL_APP_URL}).")
@click.option("--token", default=None,
              help="Override the API token (else uses stored credentials).")
@click.pass_context
def cli(ctx: click.Context, json_output: bool, app_url: str | None,
        use_local: bool, token: str | None) -> None:
    """OpenHack CLI — authenticated, programmatic access to OpenHack.

    Start with `openhack-cli auth login`, then explore `orgs`, `projects`,
    `scans`, `vulns`, and `pentest`.
    """
    cfg = Config.load()
    # --local is a shorthand for the dev server; --app-url wins if both given.
    # These are runtime overrides (beat OPENHACK_DEV / OPENHACK_APP_URL / config).
    if use_local:
        cfg.set_override_app_url(LOCAL_APP_URL)
    if app_url:
        cfg.set_override_app_url(app_url.rstrip("/"))
    if token:
        cfg.set("token", token)
    ctx.obj = {"config": cfg, "json": json_output}


cli.add_command(auth)
cli.add_command(orgs)
cli.add_command(projects)
cli.add_command(scans)
cli.add_command(vulns)
cli.add_command(pentest)
cli.add_command(config)


def main() -> None:
    try:
        cli(standalone_mode=False)
    except AuthError as exc:
        output.error(f"Authentication failed ({exc.status}): {exc.message}")
        output.info("Run `openhack-cli auth login` to (re)authorize, or check "
                    "that this endpoint accepts CLI tokens.")
        sys.exit(2)
    except APIError as exc:
        output.error(exc.message if exc.status else str(exc))
        sys.exit(1)
    except click.ClickException as exc:
        exc.show()
        sys.exit(exc.exit_code)
    except click.Abort:
        output.error("Aborted.")
        sys.exit(130)
    except KeyboardInterrupt:
        output.error("Interrupted.")
        sys.exit(130)


if __name__ == "__main__":
    main()
