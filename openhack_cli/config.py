"""Persistent CLI configuration: app URL, auth token, and active org/project context.

Stored as JSON at ``$XDG_CONFIG_HOME/openhack/config.json`` (falling back to
``~/.config/openhack/config.json``). The file is written with ``0600`` perms
since it holds a long-lived API token.

Every value can be overridden at runtime by an environment variable so the CLI
stays scriptable for agents and CI:

    OPENHACK_APP_URL   -> app_url
    OPENHACK_TOKEN     -> token
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

DEFAULT_APP_URL = "https://app.openhack.com"
LOCAL_APP_URL = "http://localhost:9080"

# Environment overrides take precedence over the on-disk config.
ENV_APP_URL = "OPENHACK_APP_URL"
ENV_TOKEN = "OPENHACK_TOKEN"
# Export OPENHACK_DEV=1 to target the local dev server without passing --local.
ENV_DEV = "OPENHACK_DEV"

_TRUTHY = {"1", "true", "yes", "on"}


def _truthy(value: Optional[str]) -> bool:
    return bool(value) and value.strip().lower() in _TRUTHY


def config_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or os.path.join(
        os.path.expanduser("~"), ".config"
    )
    return Path(base) / "openhack"


def config_path() -> Path:
    return config_dir() / "config.json"


class Config:
    """Thin wrapper over the JSON config file with env-var overrides."""

    def __init__(self, data: Optional[dict[str, Any]] = None):
        self._data: dict[str, Any] = data or {}
        # Set by CLI flags (--app-url/--local); wins over env and saved config.
        self._override_app_url: Optional[str] = None

    # ----- loading / saving -------------------------------------------------
    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if path.exists():
            try:
                data = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
        else:
            data = {}
        return cls(data)

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        # Write atomically-ish, then lock down perms (token lives here).
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self._data, indent=2) + "\n")
        os.chmod(tmp, 0o600)
        tmp.replace(path)
        os.chmod(path, 0o600)

    # ----- resolved accessors (env wins) -----------------------------------
    def set_override_app_url(self, url: str) -> None:
        """Force the app URL for this invocation (from a CLI flag)."""
        self._override_app_url = url.rstrip("/")

    @property
    def app_url(self) -> str:
        # Precedence (highest first):
        #   1. CLI flag (--app-url / --local)
        #   2. OPENHACK_APP_URL env
        #   3. OPENHACK_DEV=1 -> local dev server
        #   4. saved config (last login / `config set`)
        #   5. built-in production default
        if self._override_app_url:
            return self._override_app_url
        explicit = os.environ.get(ENV_APP_URL)
        if explicit:
            return explicit.rstrip("/")
        if _truthy(os.environ.get(ENV_DEV)):
            return LOCAL_APP_URL
        return (self._data.get("app_url") or DEFAULT_APP_URL).rstrip("/")

    @property
    def token(self) -> Optional[str]:
        return os.environ.get(ENV_TOKEN) or self._data.get("token")

    @property
    def user(self) -> Optional[dict[str, Any]]:
        return self._data.get("user")

    @property
    def org(self) -> Optional[dict[str, Any]]:
        return self._data.get("org")

    @property
    def project(self) -> Optional[dict[str, Any]]:
        return self._data.get("project")

    # ----- mutators ---------------------------------------------------------
    def set(self, key: str, value: Any) -> None:
        if value is None:
            self._data.pop(key, None)
        else:
            self._data[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def clear_auth(self) -> None:
        """Remove credentials and bound context (logout)."""
        for key in ("token", "user", "org", "project"):
            self._data.pop(key, None)

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)
