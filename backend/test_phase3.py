"""
Phase 3 tests: real-data adapters, multi-user auth, live-broker path.

All HTTP is mocked via the injectable `opener` in backend.core.http_client,
so these tests never touch the network.

Run:
  python3 -m pytest backend/test_phase3.py -v
"""

import io
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


# ─── Fake HTTP plumbing ───────────────────────────────────────────────────────


class _FakeResp:
    def __init__(self, status, body):
        self.status = status
        self._body = body

    def read(self):
        if isinstance(self._body, (bytes, bytearray)):
            return bytes(self._body)
        return json.dumps(self._body).encode("utf-8")

    def getcode(self):
        return self.status

    def close(self):
        pass


class _FakeHTTPError(Exception):
    """Stand-in for urllib.error.HTTPError with the shape http_client expects."""

    def __init__(self, code, reason, body):
        import urllib.error
        self._inner = urllib.error.HTTPError(
            url="http://x", code=code, msg=reason, hdrs={}, fp=io.BytesIO(body)
        )
        # Carry the same attributes for http_client.
        self.code = code
        self.reason = reason
        self._body = body

    def read(self):
        return self._body


def make_opener(routes):
    """Build an opener that dispatches by URL substring to a list of
    (status, body) tuples or a single (status, body) tuple.

    Each entry's first element is matched against `req.full_url`. The value
    may be:
      - dict: returned as JSON body with status 200
      - tuple (status, body_dict): returned as is
      - callable(req) -> _FakeResp
    """
    state = {"calls": []}

    def opener(req, timeout):
        state["calls"].append((req.get_method(), req.full_url, req.data))
        for substr, value in routes:
            if substr in req.full_url:
                if callable(value):
                    return value(req)
                if isinstance(value, tuple):
                    status, body = value
                    if status >= 400:
                        import urllib.error
                        raise urllib.error.HTTPError(
                            url=req.full_url, code=status, msg="err",
                            hdrs={}, fp=io.BytesIO(
                                json.dumps(body).encode() if isinstance(body, dict) else body
                            ),
                        )
                    return _FakeResp(status, body)
                return _FakeResp(200, value)
        raise AssertionError(f"no mocked route matched {req.full_url}")

    opener.state = state
    return opener


# ─── http_client retry/backoff tests ──────────────────────────────────────────


def test_http_client_retries_on_5xx_then_succeeds():
    from backend.core.http_client import request, RetryConfig

    attempts = {"n": 0}

    def opener(req, timeout):
        attempts["n"] += 1
        if attempts["n"] < 3:
            import urllib.error
            raise urllib.error.HTTPError(
                url=req.full_url, code=503, msg="busy", hdrs={},
                fp=io.BytesIO(b'{"err":"temp"}'),
            )
        return _FakeResp(200, {"ok": True})

    slept = []
    status, body = request(
        "GET", "http://host/x",
        retry=RetryConfig(max_attempts=4, base_delay=0.0, max_delay=0.0, jitter=0.0),
        opener=opener,
        sleep=slept.append,
    )
    assert status == 200 and body["ok"] is True
    assert attempts["n"] == 3
    assert len(slept) == 2  # slept between attempt 1→2 and 2→3


def test_http_client_auth_error_not_retried():
    from backend.core.http_client import request, HttpAuthError

    attempts = {"n": 0}

    def opener(req, timeout):
        attempts["n"] += 1
        import urllib.error
        raise urllib.error.HTTPError(
            url=req.full_url, code=401, msg="bad key", hdrs={},
            fp=io.BytesIO(b'{"err":"unauthorized"}'),
        )

    try:
        request("GET", "http://host/x", opener=opener, sleep=lambda _: None)
    except HttpAuthError as e:
        assert e.status == 401
    else:
        raise AssertionError("expected HttpAuthError")
    assert attempts["n"] == 1  # never retried


def test_http_client_4xx_client_error_not_retried():
    from backend.core.http_client import request, HttpClientError

    attempts = {"n": 0}

    def opener(req, timeout):
        attempts["n"] += 1
        import urllib.error
        raise urllib.error.HTTPError(
            url=req.full_url, code=400, msg="bad", hdrs={}, fp=io.BytesIO(b""),
        )

    try:
        request("GET", "http://host/x", opener=opener, sleep=lambda _: None)
    except HttpClientError:
        pass
    else:
        raise AssertionError("expected HttpClientError")
    assert attempts["n"] == 1


def test_http_client_network_error_retries_then_raises():
    from backend.core.http_client import request, RetryConfig, HttpNetworkError
    import socket

    calls = {"n": 0}

    def opener(req, timeout):
        calls["n"] += 1
        raise socket.timeout("slow")

    try:
        request(
            "GET", "http://host/x",
            retry=RetryConfig(max_attempts=3, base_delay=0.0, max_delay=0.0, jitter=0.0),
            opener=opener,
            sleep=lambda _: None,
        )
    except HttpNetworkError:
        pass
    else:
        raise AssertionError("expected HttpNetworkError")
    assert calls["n"] == 3


def test_http_client_bearer_header_set():
    from backend.core.http_client import request

    seen = {}

    def opener(req, timeout):
        seen["auth"] = req.get_header("Authorization")
        return _FakeResp(200, {"ok": 1})

    request("GET", "http://h/x", bearer_token="tok-123", opener=opener)
    assert seen["auth"] == "Bearer tok-123"


def test_http_client_json_body_serialized():
    from backend.core.http_client import request

    seen = {}

    def opener(req, timeout):
        seen["data"] = req.data
        seen["ct"] = req.get_header("Content-type")
        return _FakeResp(200, {})

    request("POST", "http://h/x", json_body={"a": 1}, opener=opener)
    assert seen["data"] == b'{"a":1}'
    assert seen["ct"] == "application/json"


# ─── OANDA market adapter tests ───────────────────────────────────────────────


def _setup_oanda_env():
    os.environ["OANDA_API_KEY"] = "t"
    os.environ["OANDA_ACCOUNT_ID"] = "a"
    os.environ["OANDA_ENVIRONMENT"] = "practice"
    os.environ["OANDA_INSTRUMENT"] = "XAU_USD"


def test_oanda_market_quote_parses_bids_asks():
    _setup_oanda_env()
    from backend.providers.oanda_market import RealOandaMarketDataProvider

    opener = make_opener([
        ("/pricing", {"prices": [{
            "instrument": "XAU_USD",
            "time": "2026-04-17T12:00:00Z",
            "bids": [{"price": "2050.10"}],
            "asks": [{"price": "2050.50"}],
        }]}),
    ])
    p = RealOandaMarketDataProvider(opener=opener)
    q = p.get_quote()
    assert q["bid"] == 2050.10
    assert q["ask"] == 2050.50
    assert q["price"] == 2050.3
    assert q["spread"] == 0.4
    assert q["source"] == "oanda"
    assert q["is_simulated"] is False
    assert q["instrument"] == "XAU_USD"


def test_oanda_market_quote_falls_back_to_closeout():
    _setup_oanda_env()
    from backend.providers.oanda_market import RealOandaMarketDataProvider

    opener = make_opener([
        ("/pricing", {"prices": [{
            "instrument": "XAU_USD",
            "time": "2026-04-17T12:00:00Z",
            "closeoutBid": "2049.00",
            "closeoutAsk": "2049.60",
        }]}),
    ])
    p = RealOandaMarketDataProvider(opener=opener)
    q = p.get_quote()
    assert q["bid"] == 2049.0 and q["ask"] == 2049.6


def test_oanda_market_candles_skips_incomplete_and_maps_granularity():
    _setup_oanda_env()
    from backend.providers.oanda_market import RealOandaMarketDataProvider

    opener = make_opener([
        ("/candles", {"candles": [
            {"time": "t1", "complete": True, "volume": 1, "mid": {"o": "1", "h": "2", "l": "0.5", "c": "1.5"}},
            {"time": "t2", "complete": False, "volume": 1, "mid": {"o": "1", "h": "2", "l": "0.5", "c": "1.5"}},
            {"time": "t3", "complete": True, "volume": 2, "mid": {"o": "2", "h": "3", "l": "1.5", "c": "2.5"}},
        ]}),
    ])
    p = RealOandaMarketDataProvider(opener=opener)
    candles = p.get_candles("1h", count=10)
    assert len(candles) == 2  # incomplete skipped
    assert candles[0]["timestamp"] == "t1"
    assert candles[1]["open"] == 2.0

    # Check granularity string went into URL.
    urls = [c[1] for c in opener.state["calls"]]
    assert any("granularity=H1" in u for u in urls)


def test_oanda_market_auth_error_raises_provider_config_error():
    _setup_oanda_env()
    from backend.providers.oanda_market import RealOandaMarketDataProvider
    from backend.providers.factory import ProviderConfigError

    def opener(req, timeout):
        import urllib.error
        raise urllib.error.HTTPError(
            url=req.full_url, code=401, msg="unauth", hdrs={},
            fp=io.BytesIO(b'{"errorMessage":"bad key"}'),
        )

    p = RealOandaMarketDataProvider(opener=opener, sleep=lambda _: None)
    try:
        p.get_quote()
    except ProviderConfigError:
        pass
    else:
        raise AssertionError("expected ProviderConfigError on 401")


def test_oanda_market_unsupported_timeframe_rejected():
    _setup_oanda_env()
    from backend.providers.oanda_market import RealOandaMarketDataProvider
    from backend.providers.factory import ProviderConfigError

    p = RealOandaMarketDataProvider(opener=lambda r, t: _FakeResp(200, {}))
    try:
        p.get_candles("7h", count=5)
    except ProviderConfigError:
        pass
    else:
        raise AssertionError("expected ProviderConfigError for unknown timeframe")


def test_oanda_market_not_ready_without_config():
    # Wipe env and force a fresh instance.
    for k in ("OANDA_API_KEY", "OANDA_ACCOUNT_ID"):
        os.environ.pop(k, None)
    from backend.providers.oanda_market import RealOandaMarketDataProvider
    from backend.providers.factory import ProviderConfigError

    p = RealOandaMarketDataProvider()
    assert p.is_ready() is False
    try:
        p.get_quote()
    except ProviderConfigError:
        pass
    else:
        raise AssertionError("expected ProviderConfigError when not ready")


# ─── OANDA broker tests ───────────────────────────────────────────────────────


def _enable_live_broker():
    os.environ["LIVE_BROKER_ENABLED"] = "true"
    os.environ["LIVE_BROKER"] = "oanda"
    _setup_oanda_env()


def _real_provider_status():
    return {
        "name": "oanda", "kind": "real", "is_real": True,
        "ready": True, "last_quote_age_seconds": 5, "reason": None,
    }


def test_oanda_broker_submit_order_filled():
    _enable_live_broker()
    from backend.execution.oanda_broker import OandaLiveBroker
    from backend.execution.broker_base import BrokerOrder

    opener = make_opener([
        ("/orders", {
            "orderCreateTransaction": {"id": "1001"},
            "orderFillTransaction": {
                "orderID": "1001", "price": "2050.25", "units": "100", "pl": "0",
                "tradeOpened": {"tradeID": "9001"},
            },
        }),
    ])
    br = OandaLiveBroker(
        provider_status=_real_provider_status(),
        settings={"system_mode": "live", "safe_mode": False},
        opener=opener,
    )
    order = BrokerOrder(
        direction="long", entry=2050, stop=2045, target_1=2060,
        position_lots=1.0, strategy="breakout", decision_id="d1",
    )
    result = br.submit_order(order)
    assert result["status"] == "filled"
    assert result["order_id"] == "1001"
    assert result["trade_id"] == "9001"
    assert result["units"] == 100.0

    # Confirm the request body carried the instrument + units + SL/TP.
    calls = opener.state["calls"]
    assert any("/v3/accounts/a/orders" in c[1] for c in calls)
    body = json.loads(calls[0][2].decode())
    assert body["order"]["instrument"] == "XAU_USD"
    assert body["order"]["units"] == "100"
    assert body["order"]["stopLossOnFill"]["price"] == "2045.00000"


def test_oanda_broker_short_uses_negative_units():
    _enable_live_broker()
    from backend.execution.oanda_broker import OandaLiveBroker
    from backend.execution.broker_base import BrokerOrder

    opener = make_opener([
        ("/orders", {"orderCreateTransaction": {"id": "x"}, "orderFillTransaction": {"orderID": "x", "price": "2000", "units": "-50", "tradeOpened": {"tradeID": "t"}}}),
    ])
    br = OandaLiveBroker(
        provider_status=_real_provider_status(),
        settings={"system_mode": "live"},
        opener=opener,
    )
    order = BrokerOrder(direction="short", entry=2000, stop=2005, target_1=1990, position_lots=0.5)
    br.submit_order(order)
    body = json.loads(opener.state["calls"][0][2].decode())
    assert body["order"]["units"] == "-50"


def test_oanda_broker_blocks_when_simulated_data():
    _enable_live_broker()
    from backend.execution.oanda_broker import OandaLiveBroker
    from backend.execution.broker_base import BrokerOrder
    from backend.execution.live_readiness import LiveExecutionBlocked

    sim_status = {"name": "simulated", "kind": "simulated", "is_real": False, "ready": True, "last_quote_age_seconds": 1, "reason": None}
    br = OandaLiveBroker(
        provider_status=sim_status,
        settings={"system_mode": "live"},
        opener=lambda r, t: _FakeResp(200, {}),
    )
    order = BrokerOrder(direction="long", entry=1, stop=0.9, target_1=1.1, position_lots=1.0)
    try:
        br.submit_order(order)
    except LiveExecutionBlocked as e:
        rules = {b.rule for b in e.report.blockers}
        assert "simulated_data" in rules
    else:
        raise AssertionError("expected LiveExecutionBlocked")


def test_oanda_broker_refuses_construction_when_disabled():
    os.environ.pop("LIVE_BROKER_ENABLED", None)
    from backend.execution.oanda_broker import OandaLiveBroker
    try:
        OandaLiveBroker()
    except RuntimeError:
        pass
    else:
        raise AssertionError("expected RuntimeError when live disabled")


def test_oanda_broker_get_account_parses_fields():
    _enable_live_broker()
    from backend.execution.oanda_broker import OandaLiveBroker

    opener = make_opener([
        ("/v3/accounts/a", ("/v3/accounts/a", (200, {
            "account": {
                "balance": "10000.50", "NAV": "10250.00", "unrealizedPL": "250.00",
                "marginUsed": "500.00", "currency": "USD", "openTradeCount": 2,
            }
        }))),  # will be re-flattened by callable
    ])
    # Re-define opener more explicitly, without the tuple nesting trick.
    def explicit(req, timeout):
        return _FakeResp(200, {
            "account": {
                "balance": "10000.50", "NAV": "10250.00", "unrealizedPL": "250.00",
                "marginUsed": "500.00", "currency": "USD", "openTradeCount": 2,
            }
        })
    br = OandaLiveBroker(
        provider_status=_real_provider_status(),
        settings={"system_mode": "live"},
        opener=explicit,
    )
    acct = br.get_account()
    assert acct["balance"] == 10000.5
    assert acct["equity"] == 10250.0
    assert acct["open_trade_count"] == 2


# ─── live-broker status tests ─────────────────────────────────────────────────


def test_live_broker_status_oanda_now_implemented():
    _enable_live_broker()
    os.environ.pop("LIVE_CUTOVER_ACKNOWLEDGED", None)
    from backend.execution.live_broker import get_live_broker_status
    s = get_live_broker_status()
    assert s["implemented"] is True
    assert s["ready"] is True  # practice + not-ack is still ready for dry-run
    assert "UNVALIDATED" in (s["reason"] or "")
    # New Phase 3 status fields:
    assert s["environment"] == "practice"
    assert s["practice_mode"] is True
    assert s["cutover_acknowledged"] is False
    assert s["validated"] is False
    assert s["live_cutover_allowed"] is False


def test_live_broker_status_disabled():
    os.environ.pop("LIVE_BROKER_ENABLED", None)
    from backend.execution.live_broker import get_live_broker_status
    s = get_live_broker_status()
    assert s["enabled"] is False
    assert s["ready"] is False


# ─── Live-cutover acknowledgement gate (Rule 6) ───────────────────────────────


def test_live_broker_status_live_env_without_ack_blocks_ready():
    """OANDA_ENVIRONMENT=live without LIVE_CUTOVER_ACKNOWLEDGED must NOT be ready."""
    _enable_live_broker()
    os.environ["OANDA_ENVIRONMENT"] = "live"
    os.environ.pop("LIVE_CUTOVER_ACKNOWLEDGED", None)
    from backend.execution.live_broker import get_live_broker_status
    s = get_live_broker_status()
    assert s["implemented"] is True
    assert s["environment"] == "live"
    assert s["practice_mode"] is False
    assert s["cutover_acknowledged"] is False
    assert s["ready"] is False
    assert s["live_cutover_allowed"] is False
    assert "cutover" in (s["reason"] or "").lower()


def test_live_broker_status_live_env_with_ack_ready():
    """OANDA_ENVIRONMENT=live + LIVE_CUTOVER_ACKNOWLEDGED=true passes status-level check."""
    _enable_live_broker()
    os.environ["OANDA_ENVIRONMENT"] = "live"
    os.environ["LIVE_CUTOVER_ACKNOWLEDGED"] = "true"
    try:
        from backend.execution.live_broker import get_live_broker_status
        s = get_live_broker_status()
        assert s["ready"] is True
        assert s["cutover_acknowledged"] is True
        assert s["validated"] is True
        assert s["live_cutover_allowed"] is True
    finally:
        os.environ.pop("LIVE_CUTOVER_ACKNOWLEDGED", None)
        os.environ["OANDA_ENVIRONMENT"] = "practice"


def test_readiness_blocks_live_env_without_cutover_ack():
    """evaluate_live_readiness must emit RULE_CUTOVER_NOT_ACKNOWLEDGED on live env."""
    from backend.execution.live_readiness import (
        evaluate_live_readiness, RULE_CUTOVER_NOT_ACKNOWLEDGED,
    )
    report = evaluate_live_readiness(
        live_enabled=True,
        provider_status=_real_provider_status(),
        broker_status={"implemented": True, "ready": False, "reason": "x"},
        settings={"system_mode": "live", "safe_mode": False},
        risk_blockers=[],
        broker_environment="live",
        cutover_acknowledged=False,
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_CUTOVER_NOT_ACKNOWLEDGED in rules
    assert report.ready is False


def test_readiness_practice_env_does_not_require_cutover_ack():
    """Practice mode is exempt from the cutover acknowledgement gate."""
    from backend.execution.live_readiness import (
        evaluate_live_readiness, RULE_CUTOVER_NOT_ACKNOWLEDGED,
    )
    report = evaluate_live_readiness(
        live_enabled=True,
        provider_status=_real_provider_status(),
        broker_status={"implemented": True, "ready": True, "reason": None},
        settings={"system_mode": "live", "safe_mode": False},
        risk_blockers=[],
        broker_environment="practice",
        cutover_acknowledged=False,
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_CUTOVER_NOT_ACKNOWLEDGED not in rules


def test_readiness_live_env_with_ack_clears_cutover_blocker():
    """Live env + acknowledgement must clear the cutover blocker specifically."""
    from backend.execution.live_readiness import (
        evaluate_live_readiness, RULE_CUTOVER_NOT_ACKNOWLEDGED,
    )
    report = evaluate_live_readiness(
        live_enabled=True,
        provider_status=_real_provider_status(),
        broker_status={"implemented": True, "ready": True, "reason": None},
        settings={"system_mode": "live", "safe_mode": False},
        risk_blockers=[],
        broker_environment="live",
        cutover_acknowledged=True,
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_CUTOVER_NOT_ACKNOWLEDGED not in rules
    assert report.ready is True


def test_oanda_broker_blocks_on_live_env_without_ack():
    """End-to-end: LiveBroker.submit_order must refuse on live env without ack."""
    _enable_live_broker()
    os.environ["OANDA_ENVIRONMENT"] = "live"
    os.environ.pop("LIVE_CUTOVER_ACKNOWLEDGED", None)
    try:
        from backend.execution.oanda_broker import OandaLiveBroker
        from backend.execution.broker_base import BrokerOrder
        from backend.execution.live_readiness import LiveExecutionBlocked

        br = OandaLiveBroker(
            provider_status=_real_provider_status(),
            settings={"system_mode": "live", "safe_mode": False},
            opener=make_opener([]),
        )
        order = BrokerOrder(
            direction="long", entry=2050, stop=2045, target_1=2060,
            position_lots=1.0, strategy="breakout", decision_id="d1",
        )
        try:
            br.submit_order(order)
        except LiveExecutionBlocked as e:
            rules = [b.rule for b in e.report.blockers]
            assert "cutover_not_acknowledged" in rules
        else:
            raise AssertionError("expected LiveExecutionBlocked on live env without ack")
    finally:
        os.environ["OANDA_ENVIRONMENT"] = "practice"


# ─── FRED macro tests ─────────────────────────────────────────────────────────


def test_fred_macro_combines_series_to_regime():
    os.environ["FRED_API_KEY"] = "fake"
    from backend.providers.fred_macro import FredMacroProvider

    def opener(req, timeout):
        url = req.full_url
        if "DTWEXBGS" in url:
            return _FakeResp(200, {"observations": [{"date": "2026-04-15", "value": "106.0"}]})
        if "DGS10" in url:
            return _FakeResp(200, {"observations": [{"date": "2026-04-15", "value": "4.40"}]})
        if "CPIAUCSL" in url:
            return _FakeResp(200, {"observations": [{"date": "2026-03-31", "value": "310.2"}]})
        if "VIXCLS" in url:
            return _FakeResp(200, {"observations": [{"date": "2026-04-15", "value": "22.5"}]})
        raise AssertionError(url)

    p = FredMacroProvider(opener=opener, cache_ttl_seconds=0)
    ctx = p.get_macro_context()
    assert ctx["usd_index"] == 106.0
    assert ctx["usd_regime"] == "strong"
    assert ctx["gold_macro_bias"] == "bearish"
    assert ctx["treasury_10y"] == 4.4
    assert ctx["rate_direction"] == "rising"
    assert ctx["vix_regime"] == "elevated"
    assert ctx["source"] == "fred"


def test_fred_macro_skips_missing_observations():
    os.environ["FRED_API_KEY"] = "fake"
    from backend.providers.fred_macro import FredMacroProvider

    def opener(req, timeout):
        return _FakeResp(200, {"observations": [
            {"date": "2026-04-16", "value": "."},   # missing
            {"date": "2026-04-15", "value": "104.0"},
        ]})

    p = FredMacroProvider(opener=opener, cache_ttl_seconds=0)
    ctx = p.get_macro_context()
    assert ctx["usd_index"] == 104.0


def test_fred_macro_without_key_raises():
    os.environ.pop("FRED_API_KEY", None)
    from backend.providers.fred_macro import FredMacroProvider, FredConfigError
    p = FredMacroProvider()
    assert p.is_ready() is False
    try:
        p.get_macro_context()
    except FredConfigError:
        pass
    else:
        raise AssertionError("expected FredConfigError")


# ─── File calendar tests ──────────────────────────────────────────────────────


def test_file_calendar_reads_and_filters():
    from backend.providers.calendar_file import FileCalendarProvider
    import datetime

    now = datetime.datetime.now(datetime.timezone.utc)
    future = (now + datetime.timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    soon = (now + datetime.timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
    past = (now - datetime.timedelta(days=2)).isoformat().replace("+00:00", "Z")

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump([
        {"name": "US CPI", "impact": "high", "datetime_utc": soon},
        {"name": "US PPI", "impact": "medium", "datetime_utc": future},
        {"name": "Old Event", "impact": "high", "datetime_utc": past},
    ], tmp)
    tmp.close()

    p = FileCalendarProvider(path=tmp.name, blackout_hours=2.0)
    assert p.is_ready()
    result = p.get_upcoming_events(hours_ahead=48)
    names = [e["name"] for e in result["events"]]
    assert "US CPI" in names
    assert "US PPI" in names
    assert "Old Event" not in names
    assert result["high_impact_within_2h"] is True
    assert p.is_news_blackout() is True

    os.unlink(tmp.name)


def test_file_calendar_malformed_fails_closed():
    from backend.providers.calendar_file import FileCalendarProvider, CalendarConfigError
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write("not json at all")
    tmp.close()
    p = FileCalendarProvider(path=tmp.name)
    assert p.is_ready() is False
    # blackout returns True conservatively
    assert p.is_news_blackout() is True
    try:
        p.get_upcoming_events()
    except CalendarConfigError:
        pass
    else:
        raise AssertionError("expected CalendarConfigError")
    os.unlink(tmp.name)


def test_file_calendar_missing_required_field_rejected():
    from backend.providers.calendar_file import FileCalendarProvider
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump([{"name": "X", "impact": "high"}], tmp)  # missing datetime_utc
    tmp.close()
    p = FileCalendarProvider(path=tmp.name)
    assert p.is_ready() is False
    assert "datetime_utc" in (p._load_error or "")
    os.unlink(tmp.name)


# ─── Auth tests ──────────────────────────────────────────────────────────────


def _reset_auth_env():
    for k in ("API_AUTH_TOKEN", "API_TOKENS_FILE"):
        os.environ.pop(k, None)


def test_auth_disabled_returns_anonymous():
    _reset_auth_env()
    from backend.core import auth
    assert auth.resolve_auth_mode()["mode"] == "disabled"
    p = auth.authenticate(None)
    assert p is not None and p.principal == "anonymous"


def test_auth_single_token_match_and_mismatch():
    _reset_auth_env()
    os.environ["API_AUTH_TOKEN"] = "single-secret-long-enough"
    from backend.core import auth
    # Force re-resolve.
    assert auth.resolve_auth_mode()["mode"] == "single_token"
    assert auth.authenticate("Bearer single-secret-long-enough").principal == "shared"
    assert auth.authenticate("Bearer wrong") is None
    assert auth.authenticate(None) is None
    _reset_auth_env()


def test_auth_multi_token_file_match_per_principal():
    _reset_auth_env()
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump([
        {"token": "alice-token-1234567890abcdef", "principal": "alice", "scopes": ["read", "write"]},
        {"token": "ops-token-1234567890abcdefgh", "principal": "ops", "scopes": ["read"]},
    ], tmp)
    tmp.close()
    os.environ["API_TOKENS_FILE"] = tmp.name
    from backend.core import auth
    mode = auth.resolve_auth_mode()
    assert mode["mode"] == "multi_token" and mode["token_count"] == 2
    p = auth.authenticate("Bearer alice-token-1234567890abcdef")
    assert p.principal == "alice" and "write" in p.scopes
    p = auth.authenticate("Bearer ops-token-1234567890abcdefgh")
    assert p.principal == "ops" and p.scopes == ["read"]
    assert auth.authenticate("Bearer bogus") is None
    os.unlink(tmp.name)
    _reset_auth_env()


def test_auth_multi_token_malformed_file_fails_closed():
    _reset_auth_env()
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    tmp.write("not json")
    tmp.close()
    os.environ["API_TOKENS_FILE"] = tmp.name
    from backend.core import auth
    mode = auth.resolve_auth_mode()
    assert mode["mode"] == "multi_token"
    assert mode["file_error"] is not None
    assert auth.authenticate("Bearer anything") is None
    os.unlink(tmp.name)
    _reset_auth_env()


def test_auth_rejects_short_tokens_in_file():
    _reset_auth_env()
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    json.dump([{"token": "short", "principal": "x"}], tmp)
    tmp.close()
    os.environ["API_TOKENS_FILE"] = tmp.name
    from backend.core import auth
    mode = auth.resolve_auth_mode()
    assert mode["file_error"] is not None
    _reset_auth_env()
    os.unlink(tmp.name)


def test_auth_rejects_duplicate_tokens_in_file():
    _reset_auth_env()
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
    dup = "same-token-long-enough-chars"
    json.dump([
        {"token": dup, "principal": "a"},
        {"token": dup, "principal": "b"},
    ], tmp)
    tmp.close()
    os.environ["API_TOKENS_FILE"] = tmp.name
    from backend.core import auth
    mode = auth.resolve_auth_mode()
    assert "duplicate" in (mode["file_error"] or "")
    _reset_auth_env()
    os.unlink(tmp.name)


def test_auth_audit_records_allow_and_deny():
    _reset_auth_env()
    os.environ["API_AUTH_TOKEN"] = "audit-token-long-enough"
    from backend.core import auth
    # Clear any previous events
    from backend.core.auth import _AUDIT_LOG
    _AUDIT_LOG.clear()
    p = auth.authenticate("Bearer audit-token-long-enough")
    auth.record_auth_event(principal=p.principal, path="/api/x", method="GET", result="allow")
    auth.record_auth_event(principal=None, path="/api/x", method="GET", result="deny", reason="bad token")
    events = auth.recent_auth_events(limit=10)
    assert len(events) >= 2
    assert events[-1]["result"] == "deny"
    _reset_auth_env()


if __name__ == "__main__":
    # Lightweight test runner when pytest isn't available.
    import traceback
    mod = sys.modules[__name__]
    failures = 0
    for name in sorted(dir(mod)):
        if not name.startswith("test_"):
            continue
        fn = getattr(mod, name)
        try:
            fn()
            print(f"PASS {name}")
        except Exception:
            failures += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\n{len([n for n in dir(mod) if n.startswith('test_')]) - failures} passed, {failures} failed")
    sys.exit(0 if failures == 0 else 1)
