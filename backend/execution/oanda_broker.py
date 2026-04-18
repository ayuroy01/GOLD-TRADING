"""
Real OANDA REST v20 broker adapter (live execution).

Subclasses LiveBroker, so:
  - It refuses to construct unless LIVE_BROKER_ENABLED=true.
  - Every order goes through the readiness gate before any HTTP call.
  - It NEVER falls back to paper on failure -- raises instead.

Endpoints:
  POST /v3/accounts/{accountID}/orders
  PUT  /v3/accounts/{accountID}/trades/{tradeID}/close
  GET  /v3/accounts/{accountID}/openTrades
  GET  /v3/accounts/{accountID}                      (account summary)
  GET  /v3/accounts/{accountID}/transactions/sinceid (fills)

Honesty notes (must be read before any live use):
  - This adapter has NOT been validated against a real OANDA practice or
    live account in this build. The schemas and field names follow OANDA's
    documented v20 REST API but have not been observed against the live
    service in CI.
  - Before any real-money cutover REQUIRED steps:
      1. Run on a practice account for at least one full trading week.
      2. Manually reconcile every fill against the OANDA web UI.
      3. Verify stop/target placement matches expectations.
      4. Confirm position sizing and units conversion is correct for XAU_USD.
  - Units conversion: OANDA expresses XAU_USD position size in "units"
    (1 unit = 1 oz). This adapter converts our internal `lots` (100 oz/lot)
    to units via UNITS_PER_LOT = 100. Verify this matches OANDA's contract
    spec for your account before live use.

Configuration:
  All env vars from LiveBroker plus:
    OANDA_INSTRUMENT  default "XAU_USD"
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.core.http_client import (
    HttpError,
    HttpAuthError,
    HttpRateLimitError,
    HttpServerError,
    HttpNetworkError,
    request as http_request,
)
from backend.execution.broker_base import BrokerOrder, BrokerPosition
from backend.execution.live_broker import LiveBroker


# 1 standard lot of XAU_USD = 100 oz at OANDA. Verify per account before live.
UNITS_PER_LOT = 100

# OANDA base URLs by environment.
_BASE_URLS = {
    "practice": "https://api-fxpractice.oanda.com",
    "live": "https://api-fxtrade.oanda.com",
}


class OandaBrokerError(RuntimeError):
    """Raised when an OANDA API call fails after retries."""


class OandaLiveBroker(LiveBroker):
    """Live broker against OANDA REST v20.

    Keeps all of LiveBroker's gating: readiness check on every order,
    no silent paper fallback, no construction unless explicitly enabled.
    """

    def __init__(
        self,
        provider_status: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        risk_blockers: Optional[List[Dict[str, Any]]] = None,
        stale_data_seconds: int = 300,
        *,
        opener=None,
        sleep=None,
        timeout: float = 10.0,
    ):
        super().__init__(
            provider_status=provider_status,
            settings=settings,
            risk_blockers=risk_blockers,
            stale_data_seconds=stale_data_seconds,
        )
        self._api_key = os.environ.get("OANDA_API_KEY", "")
        self._account_id = os.environ.get("OANDA_ACCOUNT_ID", "")
        self._environment = os.environ.get("OANDA_ENVIRONMENT", "practice").lower()
        self._instrument = os.environ.get("OANDA_INSTRUMENT", "XAU_USD")
        self._opener = opener
        self._sleep = sleep
        self._timeout = timeout

    # ── HTTP helper ──────────────────────────────────────────────────────────

    def _base_url(self) -> str:
        return _BASE_URLS[self._environment]

    def _call(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Any] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url()}{path}"
        kwargs: Dict[str, Any] = {
            "headers": {"Accept": "application/json"},
            "params": params,
            "json_body": json_body,
            "bearer_token": self._api_key,
            "timeout": self._timeout,
        }
        if self._opener is not None:
            kwargs["opener"] = self._opener
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        try:
            _, body = http_request(method, url, **kwargs)
        except HttpAuthError as e:
            raise OandaBrokerError(
                f"OANDA auth failed ({e.status}): check OANDA_API_KEY/OANDA_ACCOUNT_ID."
            ) from e
        except HttpRateLimitError as e:
            raise OandaBrokerError(f"OANDA rate-limited after retries: {e}") from e
        except HttpServerError as e:
            raise OandaBrokerError(f"OANDA server error after retries: {e}") from e
        except HttpNetworkError as e:
            raise OandaBrokerError(f"OANDA network error: {e}") from e
        except HttpError as e:
            raise OandaBrokerError(f"OANDA HTTP error: {e}") from e
        return body

    # ── Order routing ────────────────────────────────────────────────────────

    def submit_order(self, order: BrokerOrder) -> dict:
        # Critical: gate first so a misconfigured env can't reach the network.
        self._enforce_readiness()

        units = self._lots_to_units(order.position_lots, order.direction)
        body = {
            "order": {
                "type": "MARKET",
                "instrument": self._instrument,
                "units": str(units),
                "timeInForce": "FOK",
                "positionFill": "DEFAULT",
                "stopLossOnFill": {"price": _fmt(order.stop)},
                "takeProfitOnFill": {"price": _fmt(order.target_1)},
                "clientExtensions": {
                    "id": order.decision_id or "gold-agent",
                    "tag": order.strategy or "manual",
                    "comment": "gold-agent live order",
                },
            }
        }
        resp = self._call(
            "POST",
            f"/v3/accounts/{self._account_id}/orders",
            json_body=body,
        )

        fill = resp.get("orderFillTransaction") or {}
        create = resp.get("orderCreateTransaction") or {}
        # OANDA returns a fill transaction only if the order filled immediately.
        if fill:
            return {
                "order_id": fill.get("orderID") or create.get("id"),
                "trade_id": _first_trade_id(fill),
                "status": "filled",
                "fill_price": _to_float(fill.get("price")),
                "units": _to_float(fill.get("units")),
                "raw": resp,
            }
        cancel = resp.get("orderCancelTransaction")
        if cancel:
            return {
                "order_id": create.get("id"),
                "status": "cancelled",
                "reason": cancel.get("reason"),
                "raw": resp,
            }
        return {
            "order_id": create.get("id"),
            "status": "submitted",
            "raw": resp,
        }

    def close_position(self, position_id: str, price: float = None) -> dict:
        self._enforce_readiness()
        # `position_id` here is the OANDA tradeID returned from submit_order.
        resp = self._call(
            "PUT",
            f"/v3/accounts/{self._account_id}/trades/{position_id}/close",
            json_body={"units": "ALL"},
        )
        close = resp.get("orderFillTransaction") or {}
        return {
            "position_id": position_id,
            "exit_price": _to_float(close.get("price")),
            "pnl": _to_float(close.get("pl")),
            "status": "closed" if close else "unknown",
            "raw": resp,
        }

    # ── Read-only queries ────────────────────────────────────────────────────

    def get_positions(self) -> List[BrokerPosition]:
        resp = self._call("GET", f"/v3/accounts/{self._account_id}/openTrades")
        out: List[BrokerPosition] = []
        for t in resp.get("trades") or []:
            units = _to_float(t.get("currentUnits")) or 0.0
            direction = "long" if units > 0 else "short"
            entry = _to_float(t.get("price")) or 0.0
            sl = (t.get("stopLossOrder") or {}).get("price")
            tp = (t.get("takeProfitOrder") or {}).get("price")
            out.append(BrokerPosition(
                position_id=str(t.get("id")),
                direction=direction,
                entry=entry,
                stop=_to_float(sl) or 0.0,
                target_1=_to_float(tp) or 0.0,
                target_2=None,
                lots=abs(units) / UNITS_PER_LOT,
                strategy=(t.get("clientExtensions") or {}).get("tag", ""),
                open_timestamp=t.get("openTime", ""),
                unrealized_pnl=_to_float(t.get("unrealizedPL")) or 0.0,
            ))
        return out

    def get_account(self) -> dict:
        resp = self._call("GET", f"/v3/accounts/{self._account_id}")
        acct = resp.get("account") or {}
        return {
            "balance": _to_float(acct.get("balance")) or 0.0,
            "equity": _to_float(acct.get("NAV")) or 0.0,
            "unrealized_pnl": _to_float(acct.get("unrealizedPL")) or 0.0,
            "margin_used": _to_float(acct.get("marginUsed")) or 0.0,
            "currency": acct.get("currency"),
            "open_trade_count": int(acct.get("openTradeCount") or 0),
        }

    def get_fills(self, limit: int = 50) -> List[dict]:
        # OANDA: GET /v3/accounts/{id}/transactions?type=ORDER_FILL&pageSize=N
        resp = self._call(
            "GET",
            f"/v3/accounts/{self._account_id}/transactions",
            params={"type": "ORDER_FILL", "pageSize": int(limit)},
        )
        out: List[dict] = []
        for tx in resp.get("transactions") or []:
            out.append({
                "id": tx.get("id"),
                "time": tx.get("time"),
                "instrument": tx.get("instrument"),
                "units": _to_float(tx.get("units")),
                "price": _to_float(tx.get("price")),
                "pnl": _to_float(tx.get("pl")),
                "reason": tx.get("reason"),
            })
        return out

    def is_live(self) -> bool:
        return True

    # ── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _lots_to_units(lots: float, direction: str) -> int:
        units = int(round(float(lots) * UNITS_PER_LOT))
        if units <= 0:
            raise OandaBrokerError(f"Position size {lots!r} lots resolves to {units} units")
        return units if direction.lower() == "long" else -units


def _fmt(price: float) -> str:
    """OANDA expects prices as strings with at least 1 decimal."""
    return f"{float(price):.5f}"


def _to_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _first_trade_id(fill: Dict[str, Any]) -> Optional[str]:
    """OANDA returns either tradeOpened.tradeID or tradesOpened[].tradeID."""
    opened = fill.get("tradeOpened")
    if isinstance(opened, dict):
        tid = opened.get("tradeID")
        if tid:
            return str(tid)
    arr = fill.get("tradesOpened") or []
    if arr and isinstance(arr, list):
        tid = arr[0].get("tradeID")
        if tid:
            return str(tid)
    return None
