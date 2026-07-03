"""`openhack-cli config` — inspect and set CLI configuration."""

from __future__ import annotations

import click

from .. import output
from ..config import config_path
from ..context import get_config

# Keys the user is allowed to set directly. `token` is managed by auth login.
SETTABLE = {"app_url"}


@click.group()
def config() -> None:
    """View and change CLI configuration."""


@config.command(name="path")
def show_path() -> None:
    """Print the path to the config file."""
    click.echo(str(config_path()))


@config.command(name="show")
@click.pass_context
def show(ctx: click.Context) -> None:
    """Show the current configuration (token redacted)."""
    cfg = get_config(ctx)
    data = cfg.as_dict()
    if data.get("token"):
        data["token"] = data["token"][:14] + "…"
    data["app_url"] = cfg.app_url  # resolved value (env may override)

    def render(d):
        for key, value in d.items():
            output.console.print(f"  [bold]{key}[/bold]: {value}")

    output.emit(ctx.obj, data, render)


@config.command(name="set")
@click.argument("key")
@click.argument("value")
@click.pass_context
def set_value(ctx: click.Context, key: str, value: str) -> None:
    """Set a config value (e.g. `config set app_url https://...`)."""
    if key not in SETTABLE:
        raise click.ClickException(
            f"'{key}' is not settable. Allowed: {', '.join(sorted(SETTABLE))}."
        )
    cfg = get_config(ctx)
    cfg.set(key, value.rstrip("/") if key == "app_url" else value)
    cfg.save()
    output.success(f"Set {key} = {value}")
