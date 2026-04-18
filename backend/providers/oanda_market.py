"""
Real OANDA REST v20 market data adapter.

Implements MarketDataProvider against the OANDA pricing/candles endpoints
using only the Python stdlib (via backend.core.http_client).

Endpoints used:
  GET /v3/accounts/{accountID}/pricing?instruments=XAU_USD
  GET /v3/instruments/{instrument}/candles?granularity=H1&count=N

Configuration (env vars):
  OANDA_API_KEY        required
  OANDA_ACCOUNT_ID     required
  OANDA_ENVIRONMENT    "practice" (default) or "live"
  OANDA_INSTRUMENT     default "XAU_USD"

Honesty notes:
  - This adapter has NOT been validated against a live OANDA account in this
    build. The schema and field names match OANDA's documented v20 REST API
    (https://developer.oanda.com/rest-live-v20/), and every HTTP path is
    mock-tested for correctness.
  - Before any live cutover, run a supervised dry run on a practice account
    and compare against the OANDA web UI for at least one trading session.
  - This adapter NEVER falls back to simulated data. If OANDA is unreachable
    or returns an error, the call raises -- callers (and the readiness gate)
    decide whether to block or downgrade to research-only mode.
"""

from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from backend.core.http_client import (
    HttpError,
    HttpAuthError,
    HttpRateLimitError,
    HttpServerError,
    HttpNetworkError,
    request as http_request,
)
from backend.core.time_utils import utc_timestamp, get_session, now_utc
from backend.providers.factory import (
    OandaMarketDataProvider as _OandaSkeleton,
    KIND_REAL,
    ProviderConfigError,
)


# OANDA granularity codes for the timeframes we care about.
# https://developer.oanda.com/rest-live-v20/instrument-df/#CandlestickGranularity
_GRANULARITY = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
}


class OandaApiError(ProviderConfigError):
    """Raised when an OANDA HTTP call fails for a non-config reason."""


class RealOandaMarketDataProvider(_OandaSkeleton):
    """OANDA REST v20 market data adapter using stdlib HTTP.

    Inherits config validation, status reporting, and the not-ready guard
    from the skeleton in factory.py; overrides the actual data methods
    with real HTTP calls.
    """

    provider_name = "oanda"
    provider_kind = KIND_REAL
    provider_is_real = True

    # http_client opener/sleep are injectable for testing.
    def __init__(self, *, opener=None, sleep=None, timeout: float = 10.0):
        super().__init__()
        self._opener = opener
        self._sleep = sleep
        self._timeout = timeout

    # ── HTTP helper ──────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        return self.BASE_URLS[self.environment]

    def _get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET against OANDA with bearer auth + retries.

        Translates http_client exceptions into ProviderConfigError /
        OandaApiError so callers don't need to import the http_client
        exception hierarchy.
        """
        url = f"{self._base_url()}{path}"
        kwargs: Dict[str, Any] = {
            "headers": {"Accept": "application/json"},
            "params": params,
            "bearer_token": self.api_key,
            "timeout": self._timeout,
        }
        if self._opener is not None:
            kwargs["opener"] = self._opener
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        try:
            _, body = http_request("GET", url, **kwargs)
        except HttpAuthError as e:
            raise ProviderConfigError(
                f"OANDA auth failed ({e.status}): check OANDA_API_KEY. {e.body[:200] if e.body else ''}"
            ) from e
        except HttpRateLimitError as e:
            raise OandaApiError(f"OANDA rate-limited after retries: {e}") from e
        except HttpServerError as e:
            raise OandaApiError(f"OANDA server error after retries: {e}") from e
        except HttpNetworkError as e:
            raise OandaApiError(f"OANDA network error after retries: {e}") from e
        except HttpError as e:
            raise OandaApiError(f"OANDA HTTP error: {e}") from e
        return body

    # ── Pricing ──────────────────────────────────────────────────────────────

    def get_quote(self) -> dict:
        if not self.is_ready():
            self._not_ready()
        body = self._get(
            f"/v3/accounts/{self.account_id}/pricing",
            params={"instruments": self.instrument},
        )
        prices = body.get("prices") or []
        if not prices:
            raise OandaApiError(
                f"OANDA pricing returned no prices for {self.instrument!r}"
            )
        p = prices[0]
        bid = _first_price(p.get("bids"))
        ask = _first_price(p.get("asks"))
        if bid is None or ask is None:
            # closeoutBid / closeoutAsk are top-level fallbacks per OANDA docs.
            bid = _to_float(p.get("closeoutBid"))
            ask = _to_float(p.get("closeoutAsk"))
        if bid is None or ask is None:
            raise OandaApiError(f"OANDA pricing payload missing bid/ask: {p}")

        mid = (bid + ask) / 2.0
        spread = ask - bid
        ts = p.get("time") or utc_timestamp()
        self._mark_quote_fetched()
        return {
            "price": round(mid, 2),
            "bid": round(bid, 2),
            "ask": round(ask, 2),
            "spread": round(spread, 2),
            "timestamp": ts,
            "source": "oanda",
            "is_simulated": False,
            "session": get_session(now_utc()),
            "instrument": self.instrument,
            "environment": self.environment,
        }

    def get_spread(self) -> float:
        return float(self.get_quote()["spread"])

    # ── Candles ──────────────────────────────────────────────────────────────

    def get_candles(
        self,
        timeframe: str = "1h",
        count: int = 100,
        end_time: Optional[datetime.datetime] = None,
    ) -> List[dict]:
        if not self.is_ready():
            self._not_ready()
        gran = _GRANULARITY.get(timeframe)
        if gran is None:
            raise ProviderConfigError(
                f"Unsupported timeframe {timeframe!r} for OANDA. "
                f"Supported: {sorted(_GRANULARITY)}"
            )
        # Clamp count to OANDA's documented per-request max (5000).
        count = max(1, min(int(count), 5000))
        params: Dict[str, Any] = {
            "granularity": gran,
            "count": count,
            "price": "M",  # midpoint candles
        }
        if end_time is not None:
            # OANDA accepts RFC3339 timestamps.
            if end_time.tzinfo is None:
                end_time = end_time.replace(tzinfo=datetime.timezone.utc)
            params["to"] = end_time.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

        body = self._get(f"/v3/instruments/{self.instrument}/candles", params=params)
        raw_candles = body.get("candles") or []

        out: List[dict] = []
        for c in raw_candles:
            if not c.get("complete", True):
                # Skip the still-forming candle to avoid lookahead.
                continue
            mid = c.get("mid") or {}
            try:
                o = float(mid["o"])
                h = float(mid["h"])
                l = float(mid["l"])
                cl = float(mid["c"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append({
                "timestamp": c.get("time"),
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(cl, 2),
                "volume": int(c.get("volume", 0)),
                "timeframe": timeframe,
                "source": "oanda",
            })
        # Mark as fetched too -- candles imply we reached OANDA.
        if out:
            self._mark_quote_fetched()
        return out


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_price(levels: Any) -> Optional[float]:
    """OANDA `bids`/`asks` are arrays of {price, liquidity}. Take the top level."""
    if not isinstance(levels, list) or not levels:
        return None
    return _to_float(levels[0].get("price"))
