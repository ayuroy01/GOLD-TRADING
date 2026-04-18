"""
API token authentication — single-user and multi-user modes.

Two ways to configure auth, in precedence order:

  1. API_TOKENS_FILE=<path>
     A JSON file listing tokens + principals. The file format is:

         [
           {"token": "abc123...", "principal": "alice", "scopes": ["read", "write"]},
           {"token": "def456...", "principal": "ops",   "scopes": ["read"]},
           {"token": "ghi789...", "principal": "admin", "scopes": ["read", "write", "admin"]}
         ]

     - token      must be unique, >= 16 chars (rejected otherwise).
     - principal  free-form identifier logged on every request.
     - scopes     optional list; unused by default, reserved for future
                  per-endpoint gating.

     Tokens are matched with constant-time comparison. File is re-read on
     every auth check so operators can rotate without restarting. If the
     file is missing or malformed, ALL requests are denied (fail-closed).

  2. API_AUTH_TOKEN=<token>  (legacy single-token mode; still supported)
     Kept for backwards compat with Phase 1/2 deployments.

If neither is set, auth is disabled (development default) -- a WARNING
is printed at startup by server.py.

This module has zero side effects at import time and is fully pure:
`authenticate(header, config)` takes the raw `Authorization:` header and
a config dict, returns a Principal or None.
"""

from __future__ import annotations

import hmac
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


MIN_TOKEN_LENGTH = 16


class AuthConfigError(RuntimeError):
    """Raised when a token file is present but invalid."""


class Principal:
    """Authenticated caller identity."""

    __slots__ = ("principal", "scopes", "token_hint")

    def __init__(self, principal: str, scopes: List[str], token_hint: str = ""):
        self.principal = principal
        self.scopes = list(scopes)
        self.token_hint = token_hint

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes or "admin" in self.scopes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "principal": self.principal,
            "scopes": self.scopes,
            "token_hint": self.token_hint,
        }


# ─── Token-file loader with mtime cache ───────────────────────────────────────


class _TokenFileCache:
    """Re-loads tokens when the file mtime changes. Fail-closed on error."""

    def __init__(self):
        self._path: Optional[Path] = None
        self._mtime: float = -1.0
        self._entries: List[Dict[str, Any]] = []
        self._error: Optional[str] = None

    def load(self, path: Path) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        try:
            stat = path.stat()
        except FileNotFoundError:
            self._error = f"Token file not found: {path}"
            self._entries = []
            self._mtime = -1.0
            return [], self._error

        # Re-read if mtime changed or file changed.
        if path != self._path or stat.st_mtime != self._mtime:
            try:
                raw = path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if not isinstance(data, list):
                    raise AuthConfigError("Token file must be a JSON list")
                cleaned: List[Dict[str, Any]] = []
                seen_tokens = set()
                for i, entry in enumerate(data):
                    if not isinstance(entry, dict):
                        raise AuthConfigError(f"Entry #{i} is not an object")
                    tok = entry.get("token")
                    princ = entry.get("principal")
                    if not isinstance(tok, str) or len(tok) < MIN_TOKEN_LENGTH:
                        raise AuthConfigError(
                            f"Entry #{i}: token missing or < {MIN_TOKEN_LENGTH} chars"
                        )
                    if not isinstance(princ, str) or not princ:
                        raise AuthConfigError(f"Entry #{i}: principal missing")
                    if tok in seen_tokens:
                        raise AuthConfigError(f"Entry #{i}: duplicate token")
                    seen_tokens.add(tok)
                    scopes = entry.get("scopes") or []
                    if not isinstance(scopes, list) or not all(isinstance(s, str) for s in scopes):
                        raise AuthConfigError(f"Entry #{i}: scopes must be list[str]")
                    cleaned.append({"token": tok, "principal": princ, "scopes": scopes})
                self._entries = cleaned
                self._path = path
                self._mtime = stat.st_mtime
                self._error = None
            except (OSError, ValueError, AuthConfigError) as e:
                self._error = str(e)
                self._entries = []
                return [], self._error
        return self._entries, None


_TOKEN_CACHE = _TokenFileCache()


# ─── Public API ───────────────────────────────────────────────────────────────


def resolve_auth_mode() -> Dict[str, Any]:
    """Inspect env and return the active auth mode descriptor.

    Returns a dict with:
      mode:          "disabled" | "single_token" | "multi_token"
      token_count:   int       (0 when disabled or single-token)
      file_error:    str|None  (set when multi_token but file invalid)
      warning:       str|None  (human-readable configuration warning)
    """
    token_file = os.environ.get("API_TOKENS_FILE", "").strip()
    single_token = os.environ.get("API_AUTH_TOKEN", "").strip()

    if token_file:
        entries, err = _TOKEN_CACHE.load(Path(token_file))
        if err:
            return {
                "mode": "multi_token",
                "token_count": 0,
                "file_error": err,
                "warning": f"API_TOKENS_FILE invalid: {err}. All requests will be denied.",
            }
        warning = None
        if single_token:
            warning = "Both API_TOKENS_FILE and API_AUTH_TOKEN set; file takes precedence."
        return {
            "mode": "multi_token",
            "token_count": len(entries),
            "file_error": None,
            "warning": warning,
        }
    if single_token:
        return {
            "mode": "single_token",
            "token_count": 1,
            "file_error": None,
            "warning": None,
        }
    return {
        "mode": "disabled",
        "token_count": 0,
        "file_error": None,
        "warning": "Auth is disabled (no API_TOKENS_FILE / API_AUTH_TOKEN).",
    }


def is_enabled() -> bool:
    return resolve_auth_mode()["mode"] != "disabled"


def authenticate(authorization_header: Optional[str]) -> Optional[Principal]:
    """Return Principal for valid Bearer tokens, None otherwise.

    Logic:
      - if auth is disabled, returns a synthetic 'anonymous' Principal
        (caller decides whether to short-circuit the check).
      - Constant-time compare protects against timing attacks.
      - Multi-token mode re-reads the file on every call (mtime-cached).
      - If the token file is malformed, every request is denied (no
        fall-through to single-token).
    """
    mode = resolve_auth_mode()
    if mode["mode"] == "disabled":
        return Principal("anonymous", ["read", "write"], token_hint="(auth disabled)")

    token = _extract_bearer(authorization_header)
    if not token:
        return None

    if mode["mode"] == "multi_token":
        if mode["file_error"]:
            return None  # fail-closed
        entries, _ = _TOKEN_CACHE.load(Path(os.environ["API_TOKENS_FILE"]))
        for e in entries:
            if hmac.compare_digest(e["token"], token):
                return Principal(
                    principal=e["principal"],
                    scopes=e["scopes"],
                    token_hint=_hint(token),
                )
        return None

    # single_token
    expected = os.environ.get("API_AUTH_TOKEN", "")
    if expected and hmac.compare_digest(expected, token):
        return Principal("shared", ["read", "write"], token_hint=_hint(token))
    return None


def _extract_bearer(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    parts = header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    tok = parts[1].strip()
    return tok or None


def _hint(token: str) -> str:
    """Redacted token hint for logs: first 4 + '...' + last 2."""
    if len(token) <= 8:
        return "***"
    return f"{token[:4]}...{token[-2:]}"


# ─── Audit log ────────────────────────────────────────────────────────────────


_AUDIT_LOG: List[Dict[str, Any]] = []
_AUDIT_LOG_MAX = 500


def record_auth_event(
    *,
    principal: Optional[str],
    path: str,
    method: str,
    result: str,
    reason: str = "",
) -> None:
    """Append an auth decision to the in-memory audit ring buffer."""
    _AUDIT_LOG.append({
        "at": int(time.time()),
        "principal": principal,
        "path": path,
        "method": method,
        "result": result,
        "reason": reason,
    })
    # Cap size so long-running servers don't leak memory.
    if len(_AUDIT_LOG) > _AUDIT_LOG_MAX:
        del _AUDIT_LOG[:-_AUDIT_LOG_MAX]


def recent_auth_events(limit: int = 50) -> List[Dict[str, Any]]:
    return _AUDIT_LOG[-int(limit):]
