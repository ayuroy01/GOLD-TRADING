"""
Tiny stdlib HTTP client used by real-data adapters (OANDA, FRED, etc.).

Goals:
  - No third-party dependencies. Uses urllib.request.
  - Bearer auth, JSON body in/out, configurable timeout.
  - Automatic retry with exponential backoff + jitter on 5xx and transient
    network errors (URLError, socket.timeout). 4xx errors are NEVER retried
    (they are deterministic and indicate a config/permission problem).
  - Clean exception hierarchy so callers can branch on auth vs rate-limit
    vs server vs network.
  - Fully mockable: pass a custom `opener` for tests.

This module is import-safe (no I/O at import time) and has zero side effects.
"""

import json
import time
import random
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional, Tuple, Callable


class HttpError(Exception):
    """Base class for HTTP client errors."""

    def __init__(self, message: str, status: Optional[int] = None,
                 body: Optional[str] = None, url: Optional[str] = None):
        super().__init__(message)
        self.status = status
        self.body = body
        self.url = url


class HttpAuthError(HttpError):
    """401 / 403 -- credentials problem, never retried."""


class HttpRateLimitError(HttpError):
    """429 -- caller should slow down. Retried with backoff."""


class HttpClientError(HttpError):
    """4xx other than 401/403/429 -- bad request, never retried."""


class HttpServerError(HttpError):
    """5xx -- transient server problem, retried with backoff."""


class HttpNetworkError(HttpError):
    """URLError / socket.timeout -- transient network problem, retried."""


# ─── Retry config ─────────────────────────────────────────────────────────────

class RetryConfig:
    __slots__ = ("max_attempts", "base_delay", "max_delay", "jitter")

    def __init__(self, max_attempts: int = 4, base_delay: float = 0.5,
                 max_delay: float = 8.0, jitter: float = 0.25):
        self.max_attempts = max(1, max_attempts)
        self.base_delay = max(0.0, base_delay)
        self.max_delay = max(self.base_delay, max_delay)
        self.jitter = max(0.0, jitter)

    def delay_for(self, attempt: int) -> float:
        """Exponential backoff with optional jitter. attempt is 1-indexed."""
        raw = self.base_delay * (2 ** (attempt - 1))
        capped = min(raw, self.max_delay)
        if self.jitter:
            capped = capped * (1.0 + random.uniform(-self.jitter, self.jitter))
        return max(0.0, capped)


_DEFAULT_RETRY = RetryConfig()
_RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


# ─── Core request ─────────────────────────────────────────────────────────────


def request(
    method: str,
    url: str,
    *,
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, Any]] = None,
    json_body: Optional[Any] = None,
    bearer_token: Optional[str] = None,
    timeout: float = 10.0,
    retry: RetryConfig = _DEFAULT_RETRY,
    opener: Optional[Callable[[urllib.request.Request, float], Any]] = None,
    sleep: Callable[[float], None] = time.sleep,
) -> Tuple[int, Dict[str, Any]]:
    """Perform an HTTP request and return (status, parsed_json_or_dict).

    Args:
        method:        "GET", "POST", "PUT", "DELETE"
        url:           full URL
        headers:       optional extra headers
        params:        appended as query string
        json_body:     dict/list serialized to JSON
        bearer_token:  Authorization: Bearer <token>
        timeout:       per-attempt timeout in seconds
        retry:         RetryConfig
        opener:        optional injectable opener for tests; signature
                       (Request, timeout) -> http.client.HTTPResponse-like
        sleep:         injectable sleep for tests

    Returns:
        (status_code, parsed_response_dict)

    Raises:
        HttpAuthError, HttpRateLimitError, HttpClientError,
        HttpServerError, HttpNetworkError
    """
    full_url = url
    if params:
        sep = "&" if "?" in url else "?"
        full_url = url + sep + urllib.parse.urlencode(params)

    body_bytes: Optional[bytes] = None
    final_headers = dict(headers or {})
    if bearer_token:
        final_headers["Authorization"] = f"Bearer {bearer_token}"
    if json_body is not None:
        body_bytes = json.dumps(json_body, separators=(",", ":")).encode("utf-8")
        final_headers.setdefault("Content-Type", "application/json")

    req = urllib.request.Request(
        full_url, data=body_bytes, headers=final_headers, method=method.upper()
    )

    open_fn = opener or (lambda r, t: urllib.request.urlopen(r, timeout=t))

    last_exc: Optional[Exception] = None
    for attempt in range(1, retry.max_attempts + 1):
        try:
            resp = open_fn(req, timeout)
            try:
                status = getattr(resp, "status", None) or resp.getcode()
                raw = resp.read()
            finally:
                if hasattr(resp, "close"):
                    resp.close()
            return status, _parse_body(raw)

        except urllib.error.HTTPError as e:
            # Server returned a non-2xx status with a body we can read.
            try:
                raw = e.read()
            except Exception:
                raw = b""
            text = raw.decode("utf-8", errors="replace") if raw else ""
            status = e.code

            if status in (401, 403):
                raise HttpAuthError(
                    f"{method} {full_url} -> {status} {e.reason}",
                    status=status, body=text, url=full_url,
                )
            if status == 429:
                last_exc = HttpRateLimitError(
                    f"{method} {full_url} -> 429 rate limited",
                    status=status, body=text, url=full_url,
                )
            elif 400 <= status < 500:
                raise HttpClientError(
                    f"{method} {full_url} -> {status} {e.reason}",
                    status=status, body=text, url=full_url,
                )
            elif status >= 500:
                last_exc = HttpServerError(
                    f"{method} {full_url} -> {status} {e.reason}",
                    status=status, body=text, url=full_url,
                )
            else:
                # Shouldn't happen, but be defensive.
                raise HttpError(
                    f"{method} {full_url} -> unexpected status {status}",
                    status=status, body=text, url=full_url,
                )

        except (urllib.error.URLError, socket.timeout, ConnectionError, OSError) as e:
            last_exc = HttpNetworkError(f"{method} {full_url} -> network error: {e}", url=full_url)

        # Retry?
        if last_exc is None or attempt >= retry.max_attempts:
            break
        sleep(retry.delay_for(attempt))

    assert last_exc is not None  # for type narrowing
    raise last_exc


def _parse_body(raw: bytes) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"_raw": raw.decode("utf-8", errors="replace")}


# ─── Convenience wrappers ─────────────────────────────────────────────────────


def get_json(url: str, **kwargs) -> Dict[str, Any]:
    _, body = request("GET", url, **kwargs)
    return body


def post_json(url: str, json_body: Any, **kwargs) -> Dict[str, Any]:
    _, body = request("POST", url, json_body=json_body, **kwargs)
    return body


def put_json(url: str, json_body: Any, **kwargs) -> Dict[str, Any]:
    _, body = request("PUT", url, json_body=json_body, **kwargs)
    return body
