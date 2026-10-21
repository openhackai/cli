# OpenHack CLI — Agent & Automation Guide

A complete, example-driven reference for driving the OpenHack CLI from scripts,
CI, or an autonomous agent. Every command supports machine-readable output via
the global `--json` flag — **always pass `--json` when parsing output.**

Human-oriented quickstart: [`README.md`](./README.md).

The CLI covers three areas:
- **Platform** — organizations, projects, scans (`orgs`, `projects`, `scans`).
- **Project vulnerabilities** — manual vulnerabilities on a project's
  Vulnerabilities page, alongside automated scan results (`vulns`).
- **Pentesting** — engagement-scoped findings with cross-references (`pentest`).

---

## 0. Conventions (read first)

- **`--json` everywhere.** Without it you get human tables; with it you get JSON
  on stdout. Status/progress lines are written to **stderr**, so `--json` stdout
  stays clean and parseable.
- **Exit codes:** `0` success · `1` API/usage error · `2` auth error · `130`
  interrupted. Always check the code; on non-zero, read the `Error:` line on stderr.
- **IDs are UUIDs.** Resolve names→ids once, then operate on ids.
- **Active context:** the CLI remembers an active **org** and **project**
  (`orgs use` / `projects use`). Commands that take `--org`/`--project` fall back
  to the active context when the flag is omitted. Pass the flag explicitly in
  automation to be deterministic.
- All markdown text fields (`description`, `impact`, `poc`, `recommendation`, …)
  accept GitHub-flavored markdown.

---

## 1. Authentication

The CLI authenticates with an account token obtained via a browser device-code
flow (like `gh auth login`). You log in once; the token is cached and reused.

```bash
openhack-cli auth login              # opens browser; sign in, pick an org, approve
openhack-cli auth login --no-browser # print the URL/code instead of opening a browser
openhack-cli auth status             # who am I + active context
openhack-cli auth whoami             # alias of status
openhack-cli auth token              # print the raw token (for scripting)
openhack-cli auth logout             # remove the cached token
```

`auth status --json`:
```json
{ "authenticated": true, "app_url": "https://app.openhack.com",
  "user": { "email": "...", "firstName": "...", "lastName": "..." },
  "org": { "id": "...", "slug": "...", "name": "..." },
  "project": { "id": "...", "slug": "...", "name": "..." } }
```

**Headless/CI:** provide the token via the `OPENHACK_TOKEN` environment variable
instead of an interactive login. If `authenticated` is `false` and no
`OPENHACK_TOKEN` is set, stop and have a human run `openhack-cli auth login`.

The token is stored at `$XDG_CONFIG_HOME/openhack/config.json` (default
`~/.config/openhack/config.json`) with `0600` permissions.

---

## 2. Choosing an environment

Production (`https://app.openhack.com`) is the default. Precedence, highest first:

1. `--app-url <url>` (or `--local`) flag
2. `OPENHACK_APP_URL` env var
3. `OPENHACK_DEV=1` env var → local dev server (`http://localhost:9080`)
4. saved config (last login / `config set app_url`)
5. built-in default (`https://app.openhack.com`)

```bash
openhack-cli --local orgs list                 # target localhost:9080 for one command
export OPENHACK_DEV=1                           # or make local the default for the shell
openhack-cli --app-url https://example.com ...  # arbitrary host
```

---

## 3. Global flags & config

Global flags (before the subcommand): `--json`, `--app-url <url>`, `--local`,
`--token <tok>`, `-v/--version`, `-h/--help`.

```bash
openhack-cli config show     # current config (token redacted)
openhack-cli config path     # path to the config file
openhack-cli config set app_url https://app.openhack.com
```

Environment variables: `OPENHACK_TOKEN`, `OPENHACK_APP_URL`, `OPENHACK_DEV`,
`XDG_CONFIG_HOME`.

---

## 4. Organizations

```bash
openhack-cli --json orgs list          # [{ id, name, slug, orgType, subscriptionPlan }, ...]
openhack-cli orgs use "Acme, Inc."     # set active org (by id, slug, or name — case-insensitive)
```

You can switch orgs freely without re-logging-in; any org you're a member of
works. **Switching orgs clears the active project** (a project belongs to one
org), so set a project afterward.

---

## 5. Projects

```bash
openhack-cli --json projects list                 # [{ id, name, slug, ownerOrg, githubRepoOwner, ... }, ...]
openhack-cli --json projects list --org <orgId>    # filter to one org
openhack-cli projects get <id|slug|name>           # details (defaults to active project)
openhack-cli projects use <id|slug|name>           # set active project
openhack-cli --json projects create --name "My App" [--slug my-app] [--org <orgId>]
```

---

## 6. Scans

```bash
openhack-cli --json scans list [<projectId>] [--limit 20] [--offset 0]
openhack-cli --json scans get <scanId> [--project <projectId>] [--findings/--no-findings]
openhack-cli --json scans trigger-full [<projectId>] [--branch main]
openhack-cli --json scans cancel <scanId> [--project <projectId>] [--yes]
```

`scans list --json` returns `{ "scans": [...], "consolidatedCounts": {...},
"pagination": {...} }`; each scan carries `scanStatus`, per-severity counts, and a
`findings` array. `scans get` includes the full per-finding breakdown.

`scans cancel` stops a pending or running scan. Interactive output asks for
confirmation unless `--yes` is passed; `--json` never prompts, so automation
cannot hang waiting for hidden input. A completed scan cannot be cancelled.

---

## 7. Project vulnerabilities (`vulns`)

Report and manage manual vulnerabilities on a **project's** Vulnerabilities page.
Project-scoped (`--project`), distinct from pentesting.

### View
```bash
openhack-cli --json vulns list [<projectId>] [--severity high] [--scan-limit 20]
openhack-cli --json vulns groups [<projectId>]        # triage/status groups
```

### Report a vulnerability
```bash
openhack-cli --json vulns report --project <projectId> \
  --title "SQL Injection in User Search" \
  --severity high \
  --category "SQLi" \
  --description "The /api/users/search endpoint is injectable via q." \
  --impact "Extract all user records including password hashes." \
  --poc "GET /api/users/search?q=' OR 1=1--" \
  --recommendation "Use parameterized queries." \
  --code-path "src/api/users/search.ts:42" \
  --code-path "src/db/queries.ts:15" \
  --endpoint "GET /api/users/search" \
  --endpoint "POST /api/users/filter" \
  --parameter "q" --parameter "filter" \
  --affected-component "API" \
  --cwe "CWE-89" --cvss-score "8.6" \
  --cvss-vector "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:C/C:H/I:N/A:N" \
  --severity-justification "Unauthenticated access." \
  --prerequisites "No auth required." \
  --status new
# -> { "id", "number", "title", "severity" } ; appears immediately in the web UI
```
Only `--title` is required. `--severity` defaults to `medium`, `--status` to `new`.

**Repeatable / array flags:**
- `--code-path path:line` (repeat) → `codePaths[]` (also sets primary file/line)
- `--endpoint "GET /api/x"` (repeat) → `affectedEndpoints[]`
- `--parameter name` (repeat) → `affectedParameter` (JSON-encoded array string)

### Edit / get a vulnerability
```bash
openhack-cli --json vulns edit <findingId> --project <projectId> --severity critical --status triaged
openhack-cli --json vulns get  <findingId> --project <projectId>
```
`edit` is a partial update — only the fields you pass change; it refuses an empty
update. `get`'s `filePath` may be a plain string or a JSON-encoded array of
`path:line` entries (multiple code paths) — the CLI parses both for display.

### From a file
`report` and `edit` accept `--from-file <file>` (or `-` for stdin). Keys are API
field names (camelCase); explicit flags override file keys.
```bash
openhack-cli --json vulns report --project <projectId> --from-file vuln.json
```
```json
{
  "title": "IDOR on User Profile API",
  "severity": "high",
  "category": "IDOR",
  "description": "GET /api/users/{id}/profile returns any user's data.",
  "recommendation": "Verify the requester owns the profile.",
  "codePaths": ["src/api/users/profile.ts:28"],
  "affectedEndpoints": ["GET /api/users/{id}/profile"],
  "cweId": "CWE-639",
  "cvssScore": "6.5"
}
```

### `vulns` field reference
| Flag | Field | Notes |
|------|-------|-------|
| `--title` | `title` | required on report |
| `--severity` | `severity` | `critical\|high\|medium\|low\|info` (default `medium`) |
| `--status` | `status` | `new\|triaged\|in_progress\|fixed\|verified\|closed\|wont_fix\|false_positive` (default `new`) |
| `--description` `--impact` `--poc` `--recommendation` | same | markdown |
| `--category` | `category` | free text, e.g. `SQLi`, `XSS`, `IDOR` |
| `--code-path` (repeat) | `codePaths[]` | `path:line` |
| `--endpoint` (repeat) | `affectedEndpoints[]` | e.g. `GET /api/x` |
| `--parameter` (repeat) | `affectedParameter` | JSON array string |
| `--affected-component` | `affectedComponent` | e.g. `API`, `Frontend`, `Database` |
| `--cwe` | `cweId` | e.g. `CWE-89` |
| `--cvss-score` `--cvss-vector` | `cvssScore` `cvssVector` | strings |
| `--severity-justification` | `severityJustification` | when severity ≠ CVSS band |
| `--prerequisites` | `prerequisites` | |
| `--relevant-code` `--file-path` `--line-number` `--vulnerability-type` | `relevantCode` `filePath` `lineNumber` `vulnerabilityType` | edit-oriented |

> There is no `vulns delete` — remove test/incorrect vulnerabilities from the web UI.

---

## 8. Pentesting (`pentest`)

Engagement-scoped findings for a pentest. Organization-scoped (`--org`), distinct
from project vulnerabilities.

### Engagements
```bash
openhack-cli --json pentest list --org <orgId>                       # [{ id, title, status, findingCount, ... }]
openhack-cli --json pentest get <engagementId> --org <orgId>         # { engagement, members }
openhack-cli --json pentest create --org <orgId> \
  --title "Acme Q3 External Pentest" --start-date 2026-07-01 --end-date 2026-07-15
```

### Findings — list & read
```bash
openhack-cli --json pentest findings [<engagementId>] --org <orgId> [--severity critical]
# no engagementId -> uses the most recent engagement in the org

openhack-cli --json pentest finding get <engagementId> <findingId> --org <orgId>
# -> { "finding": { ... }, "reporter": { id, displayName, email, profilePictureUrl } }
```

### Findings — create
```bash
openhack-cli --json pentest finding create <engagementId> --org <orgId> \
  --title "SQL Injection in /api/login" \
  --severity critical \
  --category SQLi --cwe CWE-89 \
  --description "The login endpoint concatenates user input into the query." \
  --impact "Full authentication bypass and DB read/write." \
  --poc "curl -X POST .../api/login -d \"username=admin'--\"" \
  --recommendation "Use parameterized queries." \
  --affected-url '["https://app.example.com/api/login"]' \
  --affected-parameter '["username"]' \
  --affected-component "API / REST Endpoint" \
  --cvss-vector "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" \
  --auth-required --no-unguessable-parameter-required \
  --prerequisites "None — endpoint is unauthenticated" \
  --internal-notes "Redaction: mask internal hostnames before the client report." \
  --status submitted
```
`title` + `severity` are required. `--status draft` may omit `--description`;
`submitted` requires it. Long content is easier via `--from-json <file>` (a single
finding object with camelCase keys; flags override file keys).

### Findings — update / delete
```bash
# Partial update (PATCH) — only the fields you pass change; refuses empty updates.
openhack-cli --json pentest finding update <engagementId> <findingId> --org <orgId> \
  --auth-required --no-unguessable-parameter-required \
  --prerequisites "Requires a valid authenticated session cookie"

openhack-cli pentest finding update <engagementId> <findingId> --org <orgId> --status submitted
openhack-cli --json pentest finding delete <engagementId> <findingId> --org <orgId> --yes
```
`--yes` is required for non-interactive delete (otherwise it prompts and hangs).

### Findings — cross-references (linking)
Connect related findings (e.g. Finding 12 *chains with* Findings 1 and 3). Links
are **bidirectional** — link once; the reverse side appears automatically.
```bash
openhack-cli --json pentest finding link <engagementId> <findingId> --org <orgId> \
  --to 1,3 --type chains --note "unauth account creation removes the MFA precondition"

openhack-cli --json pentest finding unlink <engagementId> <findingId> --org <orgId> --to 1
```
- `--to` — comma-separated finding **numbers** (preferred) or ids.
- `--type` — `related` (default) · `chains` · `duplicate` · `depends`.
- Returns per-ref `[{ ref, ok, error? }]`; exits non-zero if any ref failed.
  Self-links, dangling refs, and duplicates are rejected — surfaced cleanly.

**One-shot link on create/update:** the `--related <refs>` flag links in the same
call (type `related`; link results go to stderr and don't affect the exit code —
use the `link` command for strict per-link semantics).
```bash
openhack-cli --json pentest finding create <engagementId> --org <orgId> \
  --title "MFA bypass via account chain" --severity high --related 1,3
```

Linked findings appear in `pentest finding get` under a **Related findings**
section and in its `--json` as a `relatedFindings` array.

### `pentest finding` field reference
| Flag | Field | Notes |
|------|-------|-------|
| `--title` | `title` | required on create |
| `--severity` | `severity` | `critical\|high\|medium\|low\|info` (analyst-assigned) |
| `--severity-justification` | `severityJustification` | **required when severity's band ≠ the CVSS score's band** (server-enforced; retry with it on a 400) |
| `--description` `--impact` `--poc` `--recommendation` `--relevant-code` | same | markdown |
| `--category` | `category` | see list below (custom allowed) |
| `--cwe` | `cweId` | `CWE-<n>`, e.g. `CWE-89` |
| `--cvss-score` `--cvss-vector` | `cvssScore` `cvssVector` | strings |
| `--affected-url` | `affectedUrl` | JSON-array string, e.g. `'["https://app.example.com/api"]'` |
| `--affected-parameter` | `affectedParameter` | JSON-array string |
| `--affected-component` | `affectedComponent` | see list below (custom allowed) |
| `--auth-required` / `--no-auth-required` | `authRequired` | tri-state boolean |
| `--unguessable-parameter-required` / `--no-...` | `unguessableParameterRequired` | tri-state boolean |
| `--prerequisites` | `prerequisites` | other exploitation prerequisites |
| `--internal-notes` | `internalNotes` | **excluded from the PDF report** — private context |
| `--status` | `status` | `draft` (default) `\| submitted \| accepted \| disputed \| fixed \| wont_fix` |
| `--related` | (links) | comma-separated numbers/ids, type `related` |
| `--from-json` | (all) | load a finding object from a JSON file (`-` = stdin) |

> **Tri-state booleans:** pass `--auth-required` for true, `--no-auth-required` for
> false, or omit to leave unset/unchanged. On `update`, omitting means untouched.

**Finding severity:** `critical` `high` `medium` `low` `info` — analyst-assigned,
independent of CVSS. Provide `--severity-justification` when it differs from the
CVSS band (`critical` 9.0–10.0 · `high` 7.0–8.9 · `medium` 4.0–6.9 · `low`
0.1–3.9 · `info` 0.0).

**Common categories** (custom values allowed): `XSS` `SQLi` `SSRF` `CSRF` `IDOR`
`Auth Bypass` `Authorization` `RCE` `LFI` `RFI` `XXE` `SSTI` `Command Injection`
`Path Traversal` `Info Disclosure` `Broken Auth` `Session Management`
`Cryptographic` `Business Logic` `DoS` `Open Redirect` `Clickjacking` `CORS`
`Misconfiguration` `Deserialization` `Race Condition` `File Upload`
`Mass Assignment` `GraphQL` `WebSocket`.

**Common components** (custom allowed): `Web Application` `API / REST Endpoint`
`GraphQL API` `Authentication System` `Authorization System` `Admin Panel`
`File Upload` `Payment / Billing` `User Profile` `Database` `Cloud Infrastructure`
`Mobile Application` `Email System` `Third-Party Integration` `WebSocket`
`CDN / Static Assets` `CI/CD Pipeline` `DNS` `Network Infrastructure` `Storage / S3`.

---

## 9. End-to-end examples

### Report a project vulnerability, then refine it
```bash
PROJ=<projectId>
FID=$(openhack-cli --json vulns report --project "$PROJ" \
        --title "Stored XSS in comments" --severity high --category XSS \
        --description "Comment body is rendered unsanitized." \
        --code-path "src/components/CommentForm.tsx:45" \
        --endpoint "POST /api/posts/{id}/comments" --parameter body \
        --cwe CWE-79 --cvss-score 6.1 \
      | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

openhack-cli --json vulns edit "$FID" --project "$PROJ" --status triaged --severity critical
openhack-cli --json vulns get  "$FID" --project "$PROJ"
```

### Pentest: report findings and cross-reference them
```bash
ORG=<orgId>; ENG=<engagementId>

# create two findings, capture ids
A=$(openhack-cli --json pentest finding create "$ENG" --org "$ORG" \
      --title "Unauthenticated account creation" --severity critical --status submitted \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
B=$(openhack-cli --json pentest finding create "$ENG" --org "$ORG" \
      --title "MFA bypass via account chain" --severity high --status submitted \
    | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")

# link B -> A (chains) with a note; the reverse link appears automatically
openhack-cli --json pentest finding link "$ENG" "$B" --org "$ORG" \
  --to "$A" --type chains --note "unauth account creation removes the MFA precondition"

# enrich all existing findings with exploitability metadata
for fid in $(openhack-cli --json pentest findings "$ENG" --org "$ORG" \
             | python3 -c "import sys,json;[print(f['id']) for f in json.load(sys.stdin)]"); do
  openhack-cli --json pentest finding update "$ENG" "$fid" --org "$ORG" \
    --auth-required --prerequisites "Requires valid session"
done
```

---

## 10. Gotchas

- **Always `--json`** when parsing; tables are for humans.
- **`--yes` on delete**, or it prompts interactively and hangs an agent.
- **Tri-state booleans** (`--auth-required`/`--no-auth-required`): omit to leave a
  field unchanged; pass one explicitly to set it.
- **Required on create:** `pentest finding` needs `title` + `severity`; `vulns
  report` needs `title`. `submitted` pentest findings also need a `description`.
- **Pentest vs project vulns are different:** `pentest finding …` is
  engagement-scoped (`--org` + `<engagementId>`); `vulns …` is project-scoped
  (`--project`). Different ids, different pages.
- **Severity vs CVSS** (pentest): severity is analyst-assigned; supply
  `--severity-justification` when it differs from the CVSS band or the request is
  rejected (retry with it).
- **Auth errors (exit 2):** the token is missing/invalid/expired or you lack access
  to the org/project — re-run `auth login` (or set `OPENHACK_TOKEN`) and check
  `--org`/`--project`.
- **Linking:** prefer finding **numbers** for `--to`/`--related`; links are
  bidirectional (link once); `unlink` works from either side.
