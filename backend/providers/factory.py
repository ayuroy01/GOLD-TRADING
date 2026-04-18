"""
Provider factory + real-data provider seam.

Reads DATA_PROVIDER env var and returns the appropriate market data provider.
Supported provider kinds:
  - simulated      (default; safe for research/paper; NEVER acceptable for live)
  - historical_csv (replays imported OHLC files; safe for backtests; NOT live)
  - oanda          (real-data adapter skeleton; requires OANDA_API_KEY +
                    OANDA_ACCOUNT_ID; raises clean errors when not configured)

Every provider exposes get_status() so /api/health and /api/readiness can
report which provider is active, whether it is real or simulated, whether
it is ready, and how stale the most recent quote is.

NOTE: Live execution must NEVER be allowed against a simulated provider.
The live-readiness gate (execution/live_readiness.py) enforces that rule.
"""

import os
import time
from typing import Optional, Dict, Any
from backend.providers.market_data import (
    MarketDataProvider,
    SimulatedMarketDataProvider,
    HistoricalReplayProvider,
)


# Provider "kind" constants -- consumed by readiness gating.
KIND_SIMULATED = "simulated"
KIND_HISTORICAL = "historical_csv"
KIND_REAL = "real"


class ProviderConfigError(Exception):
    """Raised when a real-data provider is selected but cannot be configured."""


class _StatusMixin:
    """Adds a uniform get_status() shape to providers."""

    provider_name: str = "unknown"
    provider_kind: str = KIND_SIMULATED
    provider_is_real: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_quote_at: Optional[float] = None

    def _mark_quote_fetched(self):
        self._last_quote_at = time.time()

    def get_status(self) -> Dict[str, Any]:
        age = None
        if self._last_quote_at is not None:
            age = round(time.time() - self._last_quote_at, 2)
        return {
            "name": self.provider_name,
            "kind": self.provider_kind,
            "is_real": self.provider_is_real,
            "ready": True,
            "last_quote_age_seconds": age,
            "reason": None,
        }


class StatusSimulatedMarketDataProvider(_StatusMixin, SimulatedMarketDataProvider):
    """Simulated provider with status reporting."""

    provider_name = "simulated"
    provider_kind = KIND_SIMULATED
    provider_is_real = False

    def get_quote(self):
        q = super().get_quote()
        self._mark_quote_fetched()
        q.setdefault("source", "simulated")
        q["is_simulated"] = True
        return q


class StatusHistoricalReplayProvider(_StatusMixin, HistoricalReplayProvider):
    """Historical replay provider with status reporting."""

    provider_name = "historical_csv"
    provider_kind = KIND_HISTORICAL
    provider_is_real = False  # replayed history is real bars but not live data

    def get_quote(self):
        q = super().get_quote()
        self._mark_quote_fetched()
        q.setdefault("source", "historical_replay")
        q["is_simulated"] = False
        q["is_historical_replay"] = True
        return q


class OandaMarketDataProvider(_StatusMixin, MarketDataProvider):
    """OANDA REST v20 adapter skeleton.

    Intentionally minimal: validates configuration up-front, exposes a clean
    not-ready status, and refuses to silently fall back. Actual HTTP calls
    require the `requests` library and a real account; this skeleton keeps
    the seam honest without pretending to be wired up.

    Required env vars:
      OANDA_API_KEY
      OANDA_ACCOUNT_ID
      OANDA_ENVIRONMENT  (practice | live; default practice)
      OANDA_INSTRUMENT   (default XAU_USD)
    """

    provider_name = "oanda"
    provider_kind = KIND_REAL
    provider_is_real = True

    BASE_URLS = {
        "practice": "https://api-fxpractice.oanda.com",
        "live": "https://api-fxtrade.oanda.com",
    }

    def __init__(self):
        super().__init__()
        self.api_key = os.environ.get("OANDA_API_KEY", "")
        self.account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
        self.environment = os.environ.get("OANDA_ENVIRONMENT", "practice").lower()
        self.instrument = os.environ.get("OANDA_INSTRUMENT", "XAU_USD")
        self._config_error: Optional[str] = self._validate_config()

    def _validate_config(self) -> Optional[str]:
        missing = []
        if not self.api_key:
            missing.append("OANDA_API_KEY")
        if not self.account_id:
            missing.append("OANDA_ACCOUNT_ID")
        if missing:
            return f"Missing required env vars: {', '.join(missing)}"
        if self.environment not in self.BASE_URLS:
            return f"OANDA_ENVIRONMENT must be 'practice' or 'live' (got {self.environment!r})"
        return None

    def is_ready(self) -> bool:
        return self._config_error is None

    def get_status(self):
        s = super().get_status()
        s["ready"] = self.is_ready()
        if not self.is_ready():
            s["reason"] = self._config_error
        s["environment"] = self.environment
        s["instrument"] = self.instrument
        return s

    def _not_ready(self):
        raise ProviderConfigError(
            f"OANDA provider not ready: {self._config_error}. "
            "Configure credentials or set DATA_PROVIDER=simulated."
        )

    def get_quote(self) -> dict:
        if not self.is_ready():
            self._not_ready()
        # Real implementation would: GET {base}/v3/accounts/{id}/pricing?instruments=XAU_USD
        # with Authorization: Bearer {api_key}, parse closeoutBid/closeoutAsk into our shape.
        # We do NOT fall back to simulated data here -- callers must handle the error.
        raise NotImplementedError(
            "OANDA quote fetching is not implemented in this build. "
            "The adapter exists as a configured seam; wire requests + parsing here."
        )

    def get_candles(self, timeframe="1h", count=100, end_time=None):
        if not self.is_ready():
            self._not_ready()
        raise NotImplementedError(
            "OANDA candle fetching is not implemented in this build."
        )

    def get_spread(self) -> float:
        if not self.is_ready():
            self._not_ready()
        raise NotImplementedError("OANDA spread query is not implemented in this build.")


# ─── Factory ───────────────────────────────────────────────────────────────────

def _resolve_oanda_provider():
    """Lazy-import the real OANDA adapter to avoid an import cycle.

    factory.py is imported at module load by many places; oanda_market.py
    imports back from factory.py for the skeleton class.
    """
    from backend.providers.oanda_market import RealOandaMarketDataProvider
    return RealOandaMarketDataProvider


_PROVIDER_REGISTRY = {
    KIND_SIMULATED: StatusSimulatedMarketDataProvider,
    # "oanda" is resolved lazily via _resolve_oanda_provider() to avoid
    # the factory <-> oanda_market import cycle.
}


def _registered_class(name: str):
    if name == "oanda":
        return _resolve_oanda_provider()
    return _PROVIDER_REGISTRY.get(name)


def get_market_provider(name: Optional[str] = None) -> MarketDataProvider:
    """Build the configured market data provider.

    Selection order:
      1. explicit `name` arg (used by tests)
      2. env var DATA_PROVIDER
      3. "simulated"

    Raises ProviderConfigError if a real provider is selected but its
    required configuration is missing. Callers may catch this and fall back
    to simulated *only* in research/paper mode -- live mode must propagate.
    """
    chosen = (name or os.environ.get("DATA_PROVIDER") or KIND_SIMULATED).lower()

    if chosen == KIND_HISTORICAL:
        # Historical replay requires explicit candle data -- the factory cannot
        # construct one without a file. Callers should build it directly via
        # backend.providers.historical_data.load_candles().
        raise ProviderConfigError(
            "historical_csv provider must be constructed via "
            "backend.providers.historical_data.load_candles(); not selectable from env."
        )

    cls = _registered_class(chosen)
    if cls is None:
        supported = sorted(set(_PROVIDER_REGISTRY.keys()) | {"oanda"})
        raise ProviderConfigError(
            f"Unknown DATA_PROVIDER {chosen!r}. "
            f"Supported: {supported} or 'historical_csv'."
        )

    instance = cls()
    return instance


def describe_configured_provider() -> Dict[str, Any]:
    """Best-effort status describe without raising. Used by /api/health."""
    chosen = (os.environ.get("DATA_PROVIDER") or KIND_SIMULATED).lower()
    try:
        provider = get_market_provider(chosen)
        return provider.get_status()
    except ProviderConfigError as e:
        return {
            "name": chosen,
            "kind": KIND_REAL if chosen != KIND_SIMULATED else KIND_SIMULATED,
            "is_real": chosen not in (KIND_SIMULATED, KIND_HISTORICAL),
            "ready": False,
            "last_quote_age_seconds": None,
            "reason": str(e),
        }
