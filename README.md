# OpenHack CLI

`openhack-cli` is the command-line interface for the [OpenHack](https://openhack.com)
security platform. It does one thing: talk to the OpenHack app in an
authenticated way, so that **humans and agents** can drive the platform from a
terminal or a script. No scanning happens in the CLI itself — it's a thin,
authenticated client over the OpenHack API.

## Install

```bash
pipx install openhack-cli        # recommended (isolated)
# or
pip install openhack-cli
```

From source:

```bash
git clone <this repo> && cd openhack-cli
pip install -e .
```

Requires Python 3.9+.

> **Driving the CLI from an automated agent?** See [`AGENT.md`](./AGENT.md) — an
> exhaustive, copy-pasteable command + field reference covering every command
> group, with allowed enum values and `--json` output for automation.

## Quick start

```bash
openhack-cli auth login          # device-code login in your browser
openhack-cli orgs list           # list your organizations
openhack-cli orgs use acme       # pick the active org
openhack-cli projects list       # list projects
openhack-cli projects use web    # pick the active project
openhack-cli scans list          # scans for the active project
openhack-cli vulns list          # vulnerabilities across recent scans
```

## Authentication

Login uses the same **device-code flow** as the OpenHack web app:

1. `auth login` calls `POST /api/cli/auth` and prints a short code + URL.
2. Your browser opens; you sign in, choose an organization, and approve.
3. The CLI polls `POST /api/cli/auth/poll` until approval, then stores the
   issued token.

The token is a long-lived, **org-scoped** API key sent as
`Authorization: Bearer openhack_…` on every request. It is stored at
`$XDG_CONFIG_HOME/openhack/config.json` (default `~/.config/openhack/config.json`)
with `0600` permissions.

```bash
openhack-cli auth status         # who am I / active context
openhack-cli auth token          # print the raw token (scripting)
openhack-cli auth logout         # remove local credentials
```

## Commands

| Group | Command | Description |
|-------|---------|-------------|
| `auth` | `login`, `logout`, `status`/`whoami`, `token` | Manage credentials |
| `orgs` | `list`, `use <id\|slug>` | List / select organizations |
| `projects` | `list`, `get`, `use`, `create` | Manage projects |
| `scans` | `list`, `get <scan_id>`, `trigger-full`, `cancel <scan_id>` | View, trigger, and cancel scans |
| `vulns` | `list`, `groups`, `report`, `get`, `edit` | View, report, and edit project vulnerabilities |
| `pentest` | `list`, `get`, `create` | Pentesting engagements |
| `pentest findings` | `[engagement]` | Findings in an engagement (defaults to latest) |
| `pentest finding` | `get`, `create`, `update`, `delete`, `link`, `unlink` | Single finding: view / create / patch / delete / cross-reference |
| `config` | `show`, `set`, `path` | CLI configuration |

For an exhaustive, example-driven command reference (aimed at automation and
agents), see [`AGENT.md`](./AGENT.md).

## Scripting & agents

Pass `--json` (global flag) to get machine-readable output from any command:

```bash
openhack-cli --json scans list
openhack-cli --json vulns list --severity critical
```

Configuration can be driven entirely by environment variables (handy in CI):

| Variable | Purpose |
|----------|---------|
| `OPENHACK_TOKEN` | API token (overrides stored credentials) |
| `OPENHACK_APP_URL` | App base URL (default `https://app.openhack.com`) |
| `OPENHACK_DEV` | Set to `1` to target the local dev server (`http://localhost:9080`) |
| `XDG_CONFIG_HOME` | Where the config file lives |

### Targeting an environment

Production (`https://app.openhack.com`) is the default. For local dev work
(`http://localhost:9080`), the easiest option is to export `OPENHACK_DEV` once —
then every command targets localhost with no flags:

```bash
export OPENHACK_DEV=1        # add to your ~/.zshrc for permanent dev mode
openhack-cli auth login      # now logs in against localhost:9080
openhack-cli scans list
```

Or use the `--local` flag per-command (shorthand for `--app-url
http://localhost:9080`):

```bash
openhack-cli --local auth login
```

The app URL is resolved with this precedence (highest first):

1. `--app-url` / `--local` flag
2. `OPENHACK_APP_URL` env var
3. `OPENHACK_DEV=1` → `http://localhost:9080`
4. saved config (last login, or `openhack-cli config set app_url <url>`)
5. built-in default `https://app.openhack.com`

Exit codes: `0` success, `1` API/usage error, `2` auth error, `130` interrupted.

## Configuration

```bash
openhack-cli config show
openhack-cli config set app_url https://your-openhack-host
openhack-cli config path
```
