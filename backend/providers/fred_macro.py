"""
Real macro provider backed by the FRED (St. Louis Fed) API.

FRED is free, requires only an API key, and exposes the canonical series we
need: DXY (DTWEXBGS as the broad dollar proxy), 10Y treasury (DGS10), CPI
(CPIAUCSL), VIX (VIXCLS).

Endpoint used:
  GET https://api.stlouisfed.org/fred/series/observations
      ?series_id=<id>&api_key=<key>&file_type=json&sort_order=desc&limit=5

Configuration:
  FRED_API_KEY         required for real data
  FRED_DXY_SERIES      default "DTWEXBGS"  (broad USD index)
  FRED_RATE10_SERIES   default "DGS10"
  FRED_CPI_SERIES      default "CPIAUCSL"
  FRED_VIX_SERIES      default "VIXCLS"

Honesty notes:
  - FRED publishes daily values with a lag of 1-2 business days for some
    series. This provider is fit for macro *context* (the thing the agent
    uses to sanity-check direction) -- it is NOT fit for intraday trading
    triggers.
  - This provider NEVER falls back to simulated data. If FRED fails, the
    call raises. Callers must decide whether to run without macro context
    or block.
  - Cache is best-effort and in-memory only (process lifetime). No disk,
    no cross-process coherence -- keep TTL short.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

from backend.core.http_client import (
    HttpError,
    HttpAuthError,
    HttpRateLimitError,
    HttpServerError,
    HttpNetworkError,
    request as http_request,
)
from backend.core.time_utils import utc_timestamp
from backend.providers.macro_data import MacroProvider


FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"


class FredConfigError(RuntimeError):
    """Raised when FRED is selected but not configured."""


class FredApiError(RuntimeError):
    """Raised when a FRED call fails after retries."""


class FredMacroProvider(MacroProvider):
    """Fetch the macro context from FRED. No silent fallback.

    Results are cached in-memory per series for `cache_ttl_seconds`
    (default 3600s) since FRED updates at most daily.
    """

    def __init__(
        self,
        *,
        cache_ttl_seconds: int = 3600,
        opener=None,
        sleep=None,
        timeout: float = 10.0,
    ):
        self.api_key = os.environ.get("FRED_API_KEY", "")
        self.series_dxy = os.environ.get("FRED_DXY_SERIES", "DTWEXBGS")
        self.series_rate10 = os.environ.get("FRED_RATE10_SERIES", "DGS10")
        self.series_cpi = os.environ.get("FRED_CPI_SERIES", "CPIAUCSL")
        self.series_vix = os.environ.get("FRED_VIX_SERIES", "VIXCLS")
        self._cache_ttl = max(0, int(cache_ttl_seconds))
        self._cache: Dict[str, Any] = {}
        self._opener = opener
        self._sleep = sleep
        self._timeout = timeout
        self._config_error: Optional[str] = None if self.api_key else "Missing FRED_API_KEY"

    # ── Status ───────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "name": "fred",
            "kind": "real",
            "is_real": True,
            "ready": self._config_error is None,
            "reason": self._config_error,
        }

    def is_ready(self) -> bool:
        return self._config_error is None

    # ── Fetch ────────────────────────────────────────────────────────────────

    def _fetch_latest(self, series_id: str) -> Optional[float]:
        """Return the most recent numeric observation for a series, or None."""
        if self._config_error:
            raise FredConfigError(self._config_error)

        cached = self._cache.get(series_id)
        if cached and (time.time() - cached["at"]) < self._cache_ttl:
            return cached["value"]

        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": 5,  # grab a few in case most recent is "."
        }
        kwargs: Dict[str, Any] = {
            "params": params,
            "timeout": self._timeout,
        }
        if self._opener is not None:
            kwargs["opener"] = self._opener
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep

        try:
            _, body = http_request("GET", FRED_BASE, **kwargs)
        except HttpAuthError as e:
            raise FredConfigError(f"FRED auth failed ({e.status}): check FRED_API_KEY.") from e
        except (HttpRateLimitError, HttpServerError, HttpNetworkError) as e:
            raise FredApiError(f"FRED fetch failed for {series_id}: {e}") from e
        except HttpError as e:
            raise FredApiError(f"FRED HTTP error for {series_id}: {e}") from e

        obs = body.get("observations") or []
        value = _first_numeric(obs)
        self._cache[series_id] = {"at": time.time(), "value": value}
        return value

    # ── MacroProvider contract ───────────────────────────────────────────────

    def get_macro_context(self) -> dict:
        dxy = self._fetch_latest(self.series_dxy)
        rate_10y = self._fetch_latest(self.series_rate10)
        cpi = self._fetch_latest(self.series_cpi)
        vix = self._fetch_latest(self.series_vix)

        # Derive regime tags with stable thresholds. These are intentionally
        # simple -- the signal module does the nuanced interpretation.
        if dxy is None:
            usd_regime = "unknown"
            gold_bias = "unknown"
        elif dxy > 105:
            usd_regime, gold_bias = "strong", "bearish"
        elif dxy < 103:
            usd_regime, gold_bias = "weak", "bullish"
        else:
            usd_regime, gold_bias = "neutral", "neutral"

        if rate_10y is None:
            rate_direction = "unknown"
        elif rate_10y > 4.3:
            rate_direction = "rising"
        elif rate_10y < 4.2:
            rate_direction = "falling"
        else:
            rate_direction = "stable"

        if vix is None:
            vix_regime = "unknown"
        elif vix > 20:
            vix_regime = "elevated"
        else:
            vix_regime = "low_vol"

        return {
            "timestamp": utc_timestamp(),
            "usd_index": dxy,
            "usd_regime": usd_regime,
            "treasury_10y": rate_10y,
            "rate_direction": rate_direction,
            "gold_macro_bias": gold_bias,
            "geopolitical_risk": "unknown",  # not derivable from FRED
            "inflation_expectation": "unknown" if cpi is None else "tracked",
            "cpi_level": cpi,
            "vix_level": vix,
            "vix_regime": vix_regime,
            "source": "fred",
        }


def _first_numeric(observations: List[Dict[str, Any]]) -> Optional[float]:
    """FRED uses '.' for missing values. Return first numeric value."""
    for o in observations:
        v = o.get("value")
        if v in (None, "", "."):
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


# ─── Factory helper ───────────────────────────────────────────────────────────


def get_macro_provider():
    """Return FRED-backed or simulated macro provider based on env.

    MACRO_PROVIDER=fred  -> FredMacroProvider (requires FRED_API_KEY)
    MACRO_PROVIDER=simulated (default) -> SimulatedMacroProvider
    """
    choice = (os.environ.get("MACRO_PROVIDER") or "simulated").lower()
    if choice == "fred":
        return FredMacroProvider()
    from backend.providers.macro_data import SimulatedMacroProvider
    return SimulatedMacroProvider()
