"""`openhack-cli scans` — list scans, inspect a scan, and trigger full scans."""

from __future__ import annotations

import click

from .. import output
from ..context import get_client, resolve_project_id


@click.group()
def scans() -> None:
    """List and inspect security scans."""


@scans.command(name="list")
@click.argument("project", required=False)
@click.option("--limit", default=20, show_default=True, help="Max scans to return.")
@click.option("--offset", default=0, show_default=True, help="Pagination offset.")
@click.pass_context
def list_scans(ctx: click.Context, project: str | None, limit: int, offset: int) -> None:
    """List scans for a project (defaults to the active project)."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    data = client.get(
        f"/api/projects/{project_id}/scans",
        params={"limit": limit, "offset": offset},
    )

    def render(payload):
        scan_rows = payload.get("scans", []) if isinstance(payload, dict) else payload
        if not scan_rows:
            output.warn("No scans found.")
            return
        table = output.make_table(
            "Scans",
            ["#", "Type", "Status", "Branch/PR", "Findings",
             "C", "H", "M", "L", "Created"],
        )
        for s in scan_rows:
            ref = s.get("branch") or (
                f"PR #{s['prNumber']}" if s.get("prNumber") else "-"
            )
            table.add_row(
                str(s.get("number", "-")),
                s.get("scanType") or "-",
                output.status_label(s.get("scanStatus")),
                output.short(ref, 24),
                str(s.get("vulnerabilityCount", 0)),
                _count(s.get("criticalCount"), "bright_red"),
                _count(s.get("highCount"), "red"),
                _count(s.get("mediumCount"), "yellow"),
                _count(s.get("lowCount"), "cyan"),
                output.short(s.get("createdAt"), 19),
            )
        output.console.print(table)
        if isinstance(payload, dict) and payload.get("consolidatedCounts"):
            cc = payload["consolidatedCounts"]
            output.console.print(
                f"\n[dim]Consolidated:[/dim] {cc.get('total', 0)} total — "
                f"{output.severity_label('critical')} {cc.get('critical', 0)}  "
                f"{output.severity_label('high')} {cc.get('high', 0)}  "
                f"{output.severity_label('medium')} {cc.get('medium', 0)}  "
                f"{output.severity_label('low')} {cc.get('low', 0)}"
            )

    output.emit(ctx.obj, data, render)


@scans.command(name="get")
@click.argument("scan_id")
@click.option("--project", default=None, help="Project id (defaults to active).")
@click.option("--findings/--no-findings", default=True,
              help="Show the per-finding breakdown.")
@click.pass_context
def get_scan(ctx: click.Context, scan_id: str, project: str | None,
             findings: bool) -> None:
    """Show a single scan and its findings."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    data = client.get(f"/api/projects/{project_id}/scans/{scan_id}")

    def render(payload):
        s = payload.get("scan", payload) if isinstance(payload, dict) else payload
        output.console.print(
            f"[bold]Scan #{s.get('number')}[/bold]  "
            f"{output.status_label(s.get('scanStatus'))}"
        )
        if s.get("prNumber"):
            output.console.print(
                f"  PR:   #{s['prNumber']} {s.get('prTitle') or ''}"
            )
        output.console.print(
            f"  Findings: {s.get('vulnerabilityCount', 0)} — "
            f"{output.severity_label('critical')} {s.get('criticalCount', 0)}  "
            f"{output.severity_label('high')} {s.get('highCount', 0)}  "
            f"{output.severity_label('medium')} {s.get('mediumCount', 0)}  "
            f"{output.severity_label('low')} {s.get('lowCount', 0)}"
        )
        if s.get("failureReason"):
            output.error(f"  Failure: {s['failureReason']}")
        if findings and s.get("findings"):
            table = output.make_table(
                None, ["#", "Severity", "Title", "Location"]
            )
            for f in sorted(
                s["findings"],
                key=lambda f: output.SEVERITY_ORDER.get(
                    (f.get("severity") or "").lower(), 9
                ),
            ):
                loc = f.get("filePath") or "-"
                if f.get("lineNumber"):
                    loc = f"{loc}:{f['lineNumber']}"
                table.add_row(
                    str(f.get("number", "-")),
                    output.severity_label(f.get("severity")),
                    output.short(f.get("title"), 60),
                    output.short(loc, 40),
                )
            output.console.print(table)

    output.emit(ctx.obj, data, render)


@scans.command(name="trigger-full")
@click.argument("project", required=False)
@click.option("--branch", default=None,
              help="Branch to scan (defaults to the repo default branch).")
@click.pass_context
def trigger_full(ctx: click.Context, project: str | None, branch: str | None) -> None:
    """Trigger a full-repository scan."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    body = {}
    if branch:
        body["branch"] = branch
    data = client.post(f"/api/projects/{project_id}/scans/trigger-full", json=body)

    def render(payload):
        output.success(payload.get("message", "Full scan triggered."))
        if payload.get("scanId"):
            output.console.print(f"  Scan ID: {payload['scanId']}")
        if payload.get("branch"):
            output.console.print(f"  Branch:  {payload['branch']}")

    output.emit(ctx.obj, data, render)


def _count(value, color: str) -> str:
    value = value or 0
    if not value:
        return "[dim]0[/dim]"
    return f"[{color}]{value}[/{color}]"
