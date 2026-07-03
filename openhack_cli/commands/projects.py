"""`openhack-cli projects` — list, inspect, create, and select projects."""

from __future__ import annotations

import click

from .. import output
from ..context import get_client, get_config, match_resource, resolve_org_id


@click.group()
def projects() -> None:
    """List, create, and select projects."""


def _fetch_projects(ctx: click.Context) -> list[dict]:
    client = get_client(ctx)
    data = client.get("/api/projects")
    return data.get("projects", []) if isinstance(data, dict) else (data or [])


@projects.command(name="list")
@click.option("--org", default=None,
              help="Filter to a single org id (client-side).")
@click.pass_context
def list_projects(ctx: click.Context, org: str | None) -> None:
    """List your projects."""
    items = _fetch_projects(ctx)
    if org:
        items = [p for p in items if p.get("ownerOrg") == org]
    cfg = get_config(ctx)
    active_id = (cfg.project or {}).get("id")

    def render(rows):
        if not rows:
            output.warn("No projects found.")
            return
        table = output.make_table("Projects",
                                  ["", "Name", "Slug", "Repo", "ID"])
        for p in rows:
            marker = "[green]●[/green]" if p.get("id") == active_id else ""
            repo = "-"
            if p.get("githubRepoOwner") and p.get("githubRepoName"):
                repo = f"{p['githubRepoOwner']}/{p['githubRepoName']}"
            table.add_row(
                marker,
                p.get("name", "-"),
                p.get("slug") or "-",
                repo,
                output.short(p.get("id"), 38),
            )
        output.console.print(table)

    output.emit(ctx.obj, items, render)


@projects.command(name="get")
@click.argument("identifier", required=False)
@click.pass_context
def get_project(ctx: click.Context, identifier: str | None) -> None:
    """Show details for a project (defaults to the active project)."""
    items = _fetch_projects(ctx)
    if identifier:
        match = match_resource(items, identifier)
    else:
        cfg = get_config(ctx)
        active = cfg.project or {}
        match = match_resource(items, active.get("id", "")) if active else None
    if not match:
        raise click.ClickException(
            "Project not found. Pass an id/slug or run `openhack-cli projects use <id>`."
        )

    def render(p):
        output.console.print(f"[bold]{p.get('name')}[/bold]  "
                             f"[dim]{p.get('slug') or ''}[/dim]")
        output.console.print(f"  ID:    {p.get('id')}")
        output.console.print(f"  Org:   {p.get('ownerOrg')}")
        if p.get("githubRepoOwner") and p.get("githubRepoName"):
            output.console.print(
                f"  Repo:  {p['githubRepoOwner']}/{p['githubRepoName']}"
            )
        if p.get("createdAt"):
            output.console.print(f"  Created: {p.get('createdAt')}")

    output.emit(ctx.obj, match, render)


@projects.command()
@click.argument("identifier")
@click.pass_context
def use(ctx: click.Context, identifier: str) -> None:
    """Set the active project (by id, slug, or name)."""
    items = _fetch_projects(ctx)
    match = match_resource(items, identifier)
    if not match:
        raise click.ClickException(
            f"No project matching '{identifier}'. Try `openhack-cli projects list`."
        )
    cfg = get_config(ctx)
    cfg.set("project", {
        "id": match.get("id"),
        "slug": match.get("slug"),
        "name": match.get("name"),
    })
    cfg.save()
    output.success(f"Active project set to [bold]{match.get('name')}[/bold]")


@projects.command()
@click.option("--name", required=True, help="Project name.")
@click.option("--slug", default=None, help="Project slug (optional).")
@click.option("--org", default=None,
              help="Org id to create the project under (defaults to active org).")
@click.pass_context
def create(ctx: click.Context, name: str, slug: str | None, org: str | None) -> None:
    """Create a new project."""
    org_id = resolve_org_id(ctx, org)
    client = get_client(ctx)
    body = {"name": name, "orgId": org_id}
    if slug:
        body["slug"] = slug
    data = client.post("/api/projects", json=body)
    project = data.get("project", data) if isinstance(data, dict) else data

    def render(p):
        output.success(f"Created project [bold]{p.get('name')}[/bold]")
        output.console.print(f"  ID: {p.get('id')}")

    output.emit(ctx.obj, project, render)
