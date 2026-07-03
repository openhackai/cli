"""`openhack-cli vulns` — view vulnerabilities (findings) and triage groups.

Actual finding details (title, severity, location) are sourced from scans, since
that's what the CLI token can read. `vulns list` aggregates findings across a
project's recent scans and de-duplicates by fingerprint, mirroring the dashboard
vulnerability view. `vulns groups` shows the triage-status groups.
"""

from __future__ import annotations

import json
import sys

import click

from .. import output
from ..context import get_client, resolve_project_id

VULN_SEVERITIES = ["critical", "high", "medium", "low", "info"]
VULN_STATUSES = ["new", "triaged", "in_progress", "fixed", "verified", "closed",
                 "wont_fix", "false_positive"]

# Scalar CLI flag (dest) -> API body field for report/edit.
VULN_SCALAR_FIELDS = {
    "title": "title",
    "severity": "severity",
    "description": "description",
    "impact": "impact",
    "poc": "poc",
    "recommendation": "recommendation",
    "category": "category",
    "affected_component": "affectedComponent",
    "cwe": "cweId",
    "cvss_score": "cvssScore",
    "cvss_vector": "cvssVector",
    "severity_justification": "severityJustification",
    "prerequisites": "prerequisites",
    "relevant_code": "relevantCode",
    "file_path": "filePath",
    "line_number": "lineNumber",
    "vulnerability_type": "vulnerabilityType",
    "status": "status",
}


@click.group()
def vulns() -> None:
    """List, report, and edit project vulnerabilities."""


@vulns.command(name="list")
@click.argument("project", required=False)
@click.option("--severity", default=None,
              type=click.Choice(["critical", "high", "medium", "low", "info"]),
              help="Filter by severity.")
@click.option("--scan-limit", default=20, show_default=True,
              help="How many recent scans to aggregate findings from.")
@click.pass_context
def list_vulns(ctx: click.Context, project: str | None, severity: str | None,
               scan_limit: int) -> None:
    """List vulnerabilities across a project's recent scans (de-duplicated)."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    data = client.get(
        f"/api/projects/{project_id}/scans", params={"limit": scan_limit}
    )
    scan_rows = data.get("scans", []) if isinstance(data, dict) else (data or [])

    # De-dupe findings across scans by fingerprint (fall back to id).
    seen: dict[str, dict] = {}
    for s in scan_rows:
        for f in s.get("findings", []) or []:
            key = f.get("fingerprint") or f.get("id")
            if key and key not in seen:
                enriched = dict(f)
                enriched["_scan"] = s.get("number")
                seen[key] = enriched
    items = list(seen.values())
    if severity:
        items = [f for f in items if (f.get("severity") or "").lower() == severity]
    items.sort(key=lambda f: output.SEVERITY_ORDER.get(
        (f.get("severity") or "").lower(), 9))

    def render(rows):
        if not rows:
            output.warn("No vulnerabilities found.")
            return
        table = output.make_table(
            "Vulnerabilities",
            ["Severity", "Title", "Location", "Category", "Scan"],
        )
        for f in rows:
            loc = f.get("filePath") or "-"
            if f.get("lineNumber"):
                loc = f"{loc}:{f['lineNumber']}"
            table.add_row(
                output.severity_label(f.get("severity")),
                output.short(f.get("title"), 56),
                output.short(loc, 36),
                output.short(f.get("category"), 18),
                f"#{f['_scan']}" if f.get("_scan") else "-",
            )
        output.console.print(table)
        output.console.print(f"\n[dim]{len(rows)} unique vulnerabilities[/dim]")

    output.emit(ctx.obj, items, render)


@vulns.command(name="groups")
@click.argument("project", required=False)
@click.pass_context
def list_groups(ctx: click.Context, project: str | None) -> None:
    """List vulnerability triage groups and their status."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    data = client.get(f"/api/projects/{project_id}/vulnerability-groups")
    groups = data.get("groups", []) if isinstance(data, dict) else (data or [])

    def render(rows):
        if not rows:
            output.warn("No vulnerability groups found.")
            return
        table = output.make_table(
            "Vulnerability Groups",
            ["Group", "Status", "Assignee", "Updated"],
        )
        for g in rows:
            assignee = (g.get("assignee") or {}).get("displayName") or "-"
            table.add_row(
                output.short(g.get("groupKey"), 40),
                output.status_label(g.get("status")),
                output.short(assignee, 20),
                output.short(g.get("updatedAt"), 19),
            )
        output.console.print(table)

    output.emit(ctx.obj, groups, render)


# --------------------------------------------------------------------------
# Reporting / editing manual vulnerabilities on a project's Vulnerabilities page
# --------------------------------------------------------------------------

def _vuln_field_options(fn):
    """Shared vulnerability-field flags for `vulns report` and `vulns edit`.

    ``--code-path``, ``--endpoint`` and ``--parameter`` are repeatable and map to
    the array fields ``codePaths`` / ``affectedEndpoints`` / ``affectedParameter``.
    """
    options = [
        click.option("--from-file", "from_file", default=None,
                     help="Load fields from a JSON file ('-' for stdin). "
                          "Keys are API field names (camelCase). Flags override."),
        click.option("--title", default=None, help="Vulnerability title."),
        click.option("--severity", default=None, type=click.Choice(VULN_SEVERITIES),
                     help="Severity (default: medium on create)."),
        click.option("--description", default=None),
        click.option("--impact", default=None),
        click.option("--poc", default=None, help="Proof of concept (markdown)."),
        click.option("--recommendation", default=None),
        click.option("--category", default=None,
                     help='Category label, e.g. "SQLi", "XSS", "IDOR".'),
        click.option("--code-path", "code_paths", multiple=True,
                     help="Source location as path:line (repeatable)."),
        click.option("--endpoint", "endpoints", multiple=True,
                     help="Affected endpoint/URL (repeatable)."),
        click.option("--parameter", "parameters", multiple=True,
                     help="Affected parameter (repeatable)."),
        click.option("--affected-component", default=None,
                     help='e.g. "API", "Frontend", "Database".'),
        click.option("--cwe", default=None, help="CWE id, e.g. CWE-89."),
        click.option("--cvss-score", default=None, help="CVSS 3.1 score, e.g. 8.6."),
        click.option("--cvss-vector", default=None),
        click.option("--severity-justification", default=None,
                     help="Reasoning when severity differs from the CVSS band."),
        click.option("--prerequisites", default=None,
                     help="What's needed to exploit this."),
        click.option("--relevant-code", default=None),
        click.option("--file-path", default=None),
        click.option("--line-number", default=None, type=int),
        click.option("--vulnerability-type", default=None),
        click.option("--status", default=None, type=click.Choice(VULN_STATUSES),
                     help="Workflow status (default: new on create)."),
    ]
    for option in reversed(options):
        fn = option(fn)
    return fn


def _build_vuln_body(from_file, flags, code_paths, endpoints, parameters) -> dict:
    """Assemble a vulnerability body from an optional JSON file + flag overrides."""
    body: dict = {}
    if from_file:
        try:
            raw = sys.stdin.read() if from_file == "-" else open(from_file).read()
        except OSError as exc:
            raise click.ClickException(f"Cannot read --from-file: {exc}")
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--from-file is not valid JSON: {exc}")
        if not isinstance(loaded, dict):
            raise click.ClickException("--from-file must contain a JSON object.")
        body.update(loaded)
    # Scalar flags override JSON.
    for dest, key in VULN_SCALAR_FIELDS.items():
        val = flags.get(dest)
        if val is not None:
            body[key] = val
    # Repeatable array flags.
    if code_paths:
        body["codePaths"] = list(code_paths)
    if endpoints:
        body["affectedEndpoints"] = list(endpoints)
    if parameters:
        # API expects affectedParameter as a JSON-encoded array string.
        body["affectedParameter"] = json.dumps(list(parameters))
    return body


def _parse_paths(value) -> list[str]:
    """filePath may be a plain string or a JSON-encoded array; normalize to a list."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    s = str(value)
    if s.startswith("["):
        try:
            parsed = json.loads(s)
            return parsed if isinstance(parsed, list) else [s]
        except json.JSONDecodeError:
            return [s]
    return [s]


@vulns.command(name="report")
@click.option("--project", default=None,
              help="Project id (defaults to the active project).")
@_vuln_field_options
@click.pass_context
def report_vuln(ctx: click.Context, project: str | None, from_file: str | None,
                code_paths, endpoints, parameters, **flags) -> None:
    """Report a new vulnerability to a project's Vulnerabilities page.

    Provide fields via flags or --from-file (flags override file keys). The
    vulnerability appears immediately in the web UI with scanSource "manual".
    """
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)

    body = _build_vuln_body(from_file, flags, code_paths, endpoints, parameters)
    if not body.get("title"):
        raise click.ClickException("Title is required (--title or 'title' in --from-file).")

    res = client.post(f"/api/projects/{project_id}/vulnerabilities", json=body)
    created = res.get("finding", res) if isinstance(res, dict) else res

    def render(f):
        output.success(
            f"Reported vulnerability #{f.get('number')} "
            f"[bold]{f.get('title')}[/bold] {output.severity_label(f.get('severity'))}"
        )
        output.console.print(f"  ID: {f.get('id')}")
        output.console.print("  [dim]Now visible on the project's Vulnerabilities page.[/dim]")

    output.emit(ctx.obj, created, render)


@vulns.command(name="edit")
@click.argument("finding_id")
@click.option("--project", default=None,
              help="Project id (defaults to the active project).")
@_vuln_field_options
@click.pass_context
def edit_vuln(ctx: click.Context, finding_id: str, project: str | None,
              from_file: str | None, code_paths, endpoints, parameters,
              **flags) -> None:
    """Edit an existing vulnerability (PATCH; only sends the fields you pass)."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)

    body = _build_vuln_body(from_file, flags, code_paths, endpoints, parameters)
    if not body:
        raise click.ClickException(
            "Nothing to update. Pass at least one field flag or --from-file."
        )

    res = client.patch(
        f"/api/projects/{project_id}/findings/{finding_id}", json=body
    )
    updated = res.get("finding", res) if isinstance(res, dict) else res

    def render(f):
        output.success(
            f"Updated vulnerability #{f.get('number')} [bold]{f.get('title')}[/bold]"
        )
        output.console.print(f"  Fields changed: {', '.join(sorted(body.keys()))}")

    output.emit(ctx.obj, updated, render)


@vulns.command(name="get")
@click.argument("finding_id")
@click.option("--project", default=None,
              help="Project id (defaults to the active project).")
@click.pass_context
def get_vuln(ctx: click.Context, finding_id: str, project: str | None) -> None:
    """Show full details of a single vulnerability."""
    project_id = resolve_project_id(ctx, project)
    client = get_client(ctx)
    res = client.get(f"/api/projects/{project_id}/findings/{finding_id}")
    finding = res.get("finding", res) if isinstance(res, dict) else res

    def render(_payload):
        f = finding
        output.console.print(
            f"[bold]#{f.get('number')} {f.get('title')}[/bold]  "
            f"{output.severity_label(f.get('severity'))}  "
            f"{output.status_label(f.get('status'))}"
        )
        for label, key in [("Category", "category"), ("Component", "affectedComponent"),
                           ("CWE", "cweId"), ("CVSS", "cvssScore"),
                           ("Prerequisites", "prerequisites")]:
            if f.get(key):
                output.console.print(f"  {label}: {f[key]}")
        paths = _parse_paths(f.get("filePath"))
        if paths:
            output.console.print(f"  Code paths: {', '.join(paths)}")
        if f.get("affectedEndpoints"):
            eps = f["affectedEndpoints"]
            output.console.print(
                f"  Endpoints: {', '.join(eps) if isinstance(eps, list) else eps}"
            )
        for label, key in [("Description", "description"), ("Impact", "impact"),
                           ("PoC", "poc"), ("Recommendation", "recommendation"),
                           ("Severity justification", "severityJustification")]:
            if f.get(key):
                output.console.print(f"\n[bold]{label}[/bold]\n{f[key]}")

    output.emit(ctx.obj, res, render)
