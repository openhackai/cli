"""Helpers that bridge Click context, config, and the API client."""

from __future__ import annotations

from typing import Any, Optional

import click

from .client import Client
from .config import Config


def get_config(ctx: click.Context) -> Config:
    return ctx.obj["config"]


def get_client(ctx: click.Context, require_auth: bool = True) -> Client:
    """Return a configured API client, optionally requiring a stored token."""
    cfg: Config = ctx.obj["config"]
    if require_auth and not cfg.token:
        raise click.ClickException(
            "Not logged in. Run `openhack-cli auth login` first."
        )
    if "client" not in ctx.obj:
        ctx.obj["client"] = Client(cfg.app_url, token=cfg.token)
    return ctx.obj["client"]


def is_json(ctx: click.Context) -> bool:
    return bool(ctx.obj.get("json"))


def resolve_org_id(ctx: click.Context, org: Optional[str]) -> str:
    """Resolve an org id from an explicit arg or the active context.

    ``org`` may be an org id (passed through as-is). When omitted we fall back
    to the org bound to the active context (set via `orgs use`, or the org the
    login token is bound to).
    """
    cfg: Config = ctx.obj["config"]
    if org:
        return org
    active = cfg.org
    if active and active.get("id"):
        return active["id"]
    raise click.ClickException(
        "No organization selected. Pass --org <id> or run `openhack-cli orgs use <id|slug>`."
    )


def resolve_project_id(ctx: click.Context, project: Optional[str]) -> str:
    """Resolve a project id from an explicit arg or the active context."""
    cfg: Config = ctx.obj["config"]
    if project:
        return project
    active = cfg.project
    if active and active.get("id"):
        return active["id"]
    raise click.ClickException(
        "No project selected. Pass a project id or run `openhack-cli projects use <id|slug>`."
    )


def match_resource(items: list[dict], needle: str,
                   keys: tuple[str, ...] = ("id", "slug", "name")) -> Optional[dict]:
    """Find a resource by id/slug/name (case-insensitive for slug/name)."""
    for item in items:
        if item.get("id") == needle:
            return item
    low = needle.lower()
    for item in items:
        for key in keys:
            val = item.get(key)
            if val and str(val).lower() == low:
                return item
    return None
