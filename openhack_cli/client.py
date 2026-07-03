"""HTTP client for the OpenHack API.

Wraps ``requests`` with the CLI's Bearer-token auth and uniform error
handling. Every authenticated endpoint expects::

    Authorization: Bearer openhack_<hex>

which is the token issued by the device-code login flow.
"""

from __future__ import annotations

from typing import Any, Optional

import requests

from . import __version__

# Endpoints that the CLI talks to are JSON unless noted (e.g. PDF reports).
USER_AGENT = f"openhack-cli/{__version__}"
DEFAULT_TIMEOUT = 30


class APIError(Exception):
    """Raised when the API returns a non-2xx response."""

    def __init__(self, status: int, message: str, body: Any = None):
        self.status = status
        self.message = message
        self.body = body
        super().__init__(f"[{status}] {message}")


class AuthError(APIError):
    """Raised on 401/403 so the CLI can prompt the user to re-login."""


class Client:
    def __init__(self, app_url: str, token: Optional[str] = None,
                 timeout: int = DEFAULT_TIMEOUT):
        self.app_url = app_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self._session = requests.Session()

    # ----- low-level --------------------------------------------------------
    def _headers(self, extra: Optional[dict] = None, auth: bool = True) -> dict:
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
        if auth and self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if extra:
            headers.update(extra)
        return headers

    def request(
        self,
        method: str,
        path: str,
        *,
        json: Any = None,
        params: Optional[dict] = None,
        auth: bool = True,
        raw: bool = False,
    ) -> Any:
        """Perform a request and return parsed JSON (or the raw Response).

        ``raw=True`` returns the underlying ``requests.Response`` so callers can
        stream binary payloads (e.g. PDF reports).
        """
        url = path if path.startswith("http") else f"{self.app_url}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                json=json,
                params=params,
                headers=self._headers(auth=auth),
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise APIError(0, f"Network error: {exc}") from exc

        if resp.status_code >= 400:
            self._raise_for_status(resp)

        if raw:
            return resp
        if not resp.content:
            return None
        ctype = resp.headers.get("Content-Type", "")
        if "application/json" in ctype:
            return resp.json()
        return resp.content

    @staticmethod
    def _raise_for_status(resp: requests.Response) -> None:
        message = resp.reason or "Request failed"
        body: Any = None
        try:
            body = resp.json()
            if isinstance(body, dict):
                message = body.get("error") or body.get("message") or message
                if body.get("message") and body.get("error"):
                    message = f"{body['error']}: {body['message']}"
        except ValueError:
            text = resp.text.strip()
            if text:
                message = text[:300]
        if resp.status_code in (401, 403):
            raise AuthError(resp.status_code, message, body)
        raise APIError(resp.status_code, message, body)

    # ----- verb helpers -----------------------------------------------------
    def get(self, path: str, **kw) -> Any:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> Any:
        return self.request("POST", path, **kw)

    def patch(self, path: str, **kw) -> Any:
        return self.request("PATCH", path, **kw)

    def delete(self, path: str, **kw) -> Any:
        return self.request("DELETE", path, **kw)
