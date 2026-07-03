"""`openhack-cli auth` — device-code login, logout, and status.

Implements the same device-code flow the app exposes for the CLI:

  1. POST /api/cli/auth            -> { device_code, user_code, verification_url }
  2. open verification_url in the browser; user signs in + picks an org + approves
  3. POST /api/cli/auth/poll       -> { status: "pending" } ... until
                                      { status: "approved", token, org, user }

The returned ``token`` (``openhack_<hex>``) is a long-lived, org-scoped API key
sent as ``Authorization: Bearer`` on every later request.
"""

from __future__ import annotations

import time
import webbrowser

import click

from .. import output
from ..client import APIError, Client
from ..config import Config
from ..context import get_config

POLL_INTERVAL = 2.0  # seconds between poll attempts


@click.group()
def auth() -> None:
    """Log in to OpenHack and manage CLI credentials."""


@auth.command()
@click.option("--no-browser", is_flag=True,
              help="Don't auto-open the browser; just print the URL.")
@click.option("--app-url", default=None,
              help="Override the OpenHack app URL for this login.")
@click.pass_context
def login(ctx: click.Context, no_browser: bool, app_url: str | None) -> None:
    """Authorize this CLI against your OpenHack account."""
    cfg: Config = get_config(ctx)
    base_url = (app_url or cfg.app_url).rstrip("/")
    # The auth-start + poll endpoints are public (no token needed).
    client = Client(base_url, token=None)

    if cfg.is_authenticated:
        output.warn("Already logged in. Re-authorizing will replace the current token.")

    try:
        start = client.post("/api/cli/auth", auth=False)
    except APIError as exc:
        raise click.ClickException(f"Failed to start login: {exc.message}")

    device_code = start["device_code"]
    user_code = start["user_code"]
    verification_url = start["verification_url"]
    expires_in = int(start.get("expires_in", 900))

    output.console.print()
    output.console.print("To authorize the OpenHack CLI, visit:\n")
    output.console.print(f"  [bold cyan]{verification_url}[/bold cyan]\n")
    output.console.print("and confirm this code:\n")
    output.console.print(f"  [bold]{user_code}[/bold]\n")

    if not no_browser:
        try:
            webbrowser.open(verification_url)
        except Exception:
            pass

    output.info("Waiting for approval in the browser… (Ctrl-C to cancel)")

    deadline = time.time() + expires_in
    result = None
    while time.time() < deadline:
        time.sleep(POLL_INTERVAL)
        try:
            poll = client.post(
                "/api/cli/auth/poll", json={"device_code": device_code}, auth=False
            )
        except APIError as exc:
            if exc.status == 410:
                raise click.ClickException(
                    "Login session expired. Run `openhack-cli auth login` again."
                )
            raise click.ClickException(f"Login failed: {exc.message}")
        if poll.get("status") == "approved":
            result = poll
            break

    if not result:
        raise click.ClickException("Login timed out before approval.")

    # Persist the token + bound org/user context.
    cfg.set("app_url", base_url)
    cfg.set("token", result["token"])
    cfg.set("user", result.get("user"))
    cfg.set("org", result.get("org"))
    cfg.save()

    org = result.get("org") or {}
    user = result.get("user") or {}
    name = _display_name(user)
    output.console.print()
    output.success(
        f"Logged in as [bold]{name}[/bold]"
        + (f" — org [bold]{org.get('name')}[/bold]" if org.get("name") else "")
    )


@auth.command()
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Remove stored credentials from this machine."""
    cfg: Config = get_config(ctx)
    if not cfg.is_authenticated:
        output.warn("Not logged in.")
        return
    cfg.clear_auth()
    cfg.save()
    output.success("Logged out. Token removed from this machine.")
    output.info("(The API key still exists server-side; revoke it in org settings.)")


@auth.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show the current login status and active context."""
    cfg: Config = get_config(ctx)
    payload = {
        "authenticated": cfg.is_authenticated,
        "app_url": cfg.app_url,
        "user": cfg.user,
        "org": cfg.org,
        "project": cfg.project,
    }

    def render(_data):
        if not cfg.is_authenticated:
            output.warn("Not logged in. Run `openhack-cli auth login`.")
            output.console.print(f"App URL: [dim]{cfg.app_url}[/dim]")
            return
        user = cfg.user or {}
        output.success(f"Logged in as [bold]{_display_name(user)}[/bold]")
        if user.get("email"):
            output.console.print(f"  Email:   {user['email']}")
        output.console.print(f"  App URL: {cfg.app_url}")
        if cfg.org:
            output.console.print(
                f"  Org:     {cfg.org.get('name')} "
                f"[dim]({cfg.org.get('slug') or cfg.org.get('id')})[/dim]"
            )
        if cfg.project:
            output.console.print(
                f"  Project: {cfg.project.get('name')} "
                f"[dim]({cfg.project.get('slug') or cfg.project.get('id')})[/dim]"
            )

    output.emit(ctx.obj, payload, render)


@auth.command(name="whoami")
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Alias for `auth status`."""
    ctx.invoke(status)


@auth.command()
@click.pass_context
def token(ctx: click.Context) -> None:
    """Print the raw API token (for scripting). Keep it secret."""
    cfg: Config = get_config(ctx)
    if not cfg.token:
        raise click.ClickException("Not logged in.")
    click.echo(cfg.token)


def _display_name(user: dict) -> str:
    if not user:
        return "unknown"
    parts = [user.get("firstName"), user.get("lastName")]
    name = " ".join(p for p in parts if p).strip()
    return name or user.get("email") or "unknown"
