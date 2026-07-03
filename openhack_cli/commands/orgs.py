"""`openhack-cli orgs` — list organizations and pick the active one."""

from __future__ import annotations

import click

from .. import output
from ..context import get_client, get_config, match_resource


@click.group()
def orgs() -> None:
    """List and select organizations."""


def _fetch_orgs(ctx: click.Context) -> list[dict]:
    client = get_client(ctx)
    data = client.get("/api/orgs")
    return data.get("orgs", []) if isinstance(data, dict) else (data or [])


@orgs.command(name="list")
@click.pass_context
def list_orgs(ctx: click.Context) -> None:
    """List organizations you belong to."""
    items = _fetch_orgs(ctx)
    cfg = get_config(ctx)
    active_id = (cfg.org or {}).get("id")

    def render(rows):
        if not rows:
            output.warn("No organizations found.")
            return
        table = output.make_table("Organizations",
                                  ["", "Name", "Slug", "Type", "Plan", "ID"])
        for o in rows:
            marker = "[green]●[/green]" if o.get("id") == active_id else ""
            table.add_row(
                marker,
                o.get("name", "-"),
                o.get("slug") or "-",
                o.get("orgType") or "-",
                o.get("subscriptionPlan") or "-",
                output.short(o.get("id"), 38),
            )
        output.console.print(table)

    output.emit(ctx.obj, items, render)


@orgs.command()
@click.argument("identifier")
@click.pass_context
def use(ctx: click.Context, identifier: str) -> None:
    """Set the active organization (by id, slug, or name)."""
    items = _fetch_orgs(ctx)
    match = match_resource(items, identifier)
    if not match:
        raise click.ClickException(
            f"No organization matching '{identifier}'. Try `openhack-cli orgs list`."
        )
    cfg = get_config(ctx)
    cfg.set("org", {
        "id": match.get("id"),
        "slug": match.get("slug"),
        "name": match.get("name"),
    })
    # Switching orgs invalidates the previously-selected project.
    cfg.set("project", None)
    cfg.save()
    output.success(f"Active org set to [bold]{match.get('name')}[/bold]")
