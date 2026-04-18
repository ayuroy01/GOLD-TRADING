"""
Phase 2 tests: real-data provider seam, historical import, live-readiness gating,
and the new /api/health + /api/readiness + /api/historical endpoints.

Run: python3 -m pytest backend/test_phase2.py -v
  or: cd backend && python3 test_phase2.py
"""

import sys
import os
import json
import socket
import tempfile
import threading
import time
import http.client
from pathlib import Path

# Setup before importing server
_TEST_DIR = tempfile.mkdtemp(prefix="gold_phase2_test_")
os.environ["DATA_DIR"] = _TEST_DIR
os.environ.pop("DATA_PROVIDER", None)
os.environ.pop("LIVE_BROKER_ENABLED", None)
os.environ.pop("OANDA_API_KEY", None)
os.environ.pop("OANDA_ACCOUNT_ID", None)

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from http.server import HTTPServer
import server
from server import GoldAgentHandler

from backend.providers import factory
from backend.providers import historical_data
from backend.execution import live_broker
from backend.execution import live_readiness
from backend.execution.live_readiness import (
    RULE_LIVE_DISABLED, RULE_SIMULATED_DATA, RULE_BROKER_NOT_IMPLEMENTED,
    RULE_PROVIDER_NOT_READY, RULE_STALE_DATA, RULE_SAFE_MODE,
    RULE_NOT_LIVE_MODE,
)


_PORT = None
_server = None
_thread = None


def _find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def setup_module():
    global _server, _thread, _PORT
    server._reinitialize_data_dir(_TEST_DIR)
    _PORT = _find_free_port()
    _server = HTTPServer(("127.0.0.1", _PORT), GoldAgentHandler)
    _server.allow_reuse_address = True
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    time.sleep(0.2)


def teardown_module():
    global _server
    if _server:
        _server.shutdown()
        _server.server_close()
        _server = None


def reset_data():
    server._reinitialize_data_dir(_TEST_DIR)
    for f in Path(_TEST_DIR).glob("*.json"):
        f.unlink()


def http_get(path, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=10)
    conn.request("GET", path, headers=headers or {})
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    conn.close()
    return resp.status, body


def http_post(path, data=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=20)
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request("POST", path, body=json.dumps(data or {}), headers=hdrs)
    resp = conn.getresponse()
    body = json.loads(resp.read().decode())
    conn.close()
    return resp.status, body


# ════════════════════════════════════════════════════════════════════════════════
# Provider factory
# ════════════════════════════════════════════════════════════════════════════════

def test_factory_default_is_simulated():
    p = factory.get_market_provider()
    s = p.get_status()
    assert s["name"] == "simulated"
    assert s["is_real"] is False
    assert s["ready"] is True
    print("  ✓ factory default is simulated, ready, not real")


def test_factory_unknown_raises():
    try:
        factory.get_market_provider("not_a_real_thing")
    except factory.ProviderConfigError as e:
        assert "Unknown DATA_PROVIDER" in str(e)
        print("  ✓ unknown provider name raises ProviderConfigError")
        return
    raise AssertionError("expected ProviderConfigError")


def test_factory_historical_must_be_built_directly():
    try:
        factory.get_market_provider("historical_csv")
    except factory.ProviderConfigError as e:
        assert "historical_csv" in str(e)
        print("  ✓ historical_csv cannot be selected via env (must use loader)")
        return
    raise AssertionError("expected ProviderConfigError")


def test_simulated_provider_quote_marks_freshness():
    p = factory.get_market_provider()
    q = p.get_quote()
    assert q["is_simulated"] is True
    assert q["source"] == "simulated"
    s = p.get_status()
    assert s["last_quote_age_seconds"] is not None
    assert s["last_quote_age_seconds"] >= 0
    print("  ✓ simulated provider records quote age + flags is_simulated")


def test_oanda_provider_missing_credentials():
    # Ensure env is clean
    for k in ("OANDA_API_KEY", "OANDA_ACCOUNT_ID"):
        os.environ.pop(k, None)
    p = factory.OandaMarketDataProvider()
    assert not p.is_ready()
    s = p.get_status()
    assert s["ready"] is False
    assert "Missing required env vars" in (s["reason"] or "")
    # Calling get_quote must NOT silently fall back to simulated.
    try:
        p.get_quote()
    except factory.ProviderConfigError as e:
        assert "OANDA provider not ready" in str(e)
        print("  ✓ oanda provider blocks on missing creds (no silent fallback)")
        return
    raise AssertionError("expected ProviderConfigError")


def test_oanda_provider_with_creds_but_not_implemented():
    os.environ["OANDA_API_KEY"] = "fake"
    os.environ["OANDA_ACCOUNT_ID"] = "acct-1"
    try:
        p = factory.OandaMarketDataProvider()
        assert p.is_ready()  # config passes
        try:
            p.get_quote()
        except NotImplementedError as e:
            assert "not implemented" in str(e).lower()
            print("  ✓ oanda with creds raises NotImplementedError (no fake data)")
            return
        raise AssertionError("expected NotImplementedError")
    finally:
        os.environ.pop("OANDA_API_KEY", None)
        os.environ.pop("OANDA_ACCOUNT_ID", None)


def test_describe_configured_provider_when_oanda_unconfigured():
    os.environ["DATA_PROVIDER"] = "oanda"
    try:
        s = factory.describe_configured_provider()
        assert s["ready"] is False
        assert s["is_real"] is True
        assert "Missing" in (s["reason"] or "")
        print("  ✓ describe_configured_provider reports unconfigured oanda honestly")
    finally:
        os.environ.pop("DATA_PROVIDER", None)


# ════════════════════════════════════════════════════════════════════════════════
# Historical import
# ════════════════════════════════════════════════════════════════════════════════

def _write_csv(path, rows):
    lines = ["timestamp,open,high,low,close,volume"]
    for r in rows:
        lines.append(",".join(str(x) for x in r))
    Path(path).write_text("\n".join(lines))


def test_historical_csv_round_trip():
    p = Path(_TEST_DIR) / "ok.csv"
    _write_csv(p, [
        ("2024-01-01T00:00:00Z", 2050, 2055, 2049, 2052, 1000),
        ("2024-01-01T01:00:00Z", 2052, 2058, 2051, 2057, 1500),
    ])
    candles = historical_data.load_candles_csv(p, "1h")
    assert len(candles) == 2
    assert candles[0]["timeframe"] == "1h"
    assert candles[0]["timestamp"].startswith("2024-01-01T00:00:00")
    assert candles[1]["close"] == 2057
    print("  ✓ csv import round-trips, timestamps normalized")


def test_historical_csv_rejects_high_below_low():
    p = Path(_TEST_DIR) / "bad_hl.csv"
    _write_csv(p, [
        ("2024-01-01T00:00:00Z", 2050, 2040, 2049, 2052, 1000),  # high < low
    ])
    try:
        historical_data.load_candles_csv(p, "1h")
    except historical_data.HistoricalImportError as e:
        assert "high" in str(e) and "low" in str(e)
        print("  ✓ csv import rejects high < low")
        return
    raise AssertionError("expected HistoricalImportError")


def test_historical_csv_rejects_open_outside_range():
    p = Path(_TEST_DIR) / "bad_open.csv"
    _write_csv(p, [
        ("2024-01-01T00:00:00Z", 99999, 2055, 2049, 2052, 1000),
    ])
    try:
        historical_data.load_candles_csv(p, "1h")
    except historical_data.HistoricalImportError:
        print("  ✓ csv import rejects open outside [low,high]")
        return
    raise AssertionError("expected HistoricalImportError")


def test_historical_csv_rejects_duplicate_timestamps():
    p = Path(_TEST_DIR) / "dup.csv"
    _write_csv(p, [
        ("2024-01-01T00:00:00Z", 2050, 2055, 2049, 2052, 1000),
        ("2024-01-01T00:00:00Z", 2052, 2058, 2051, 2057, 1500),
    ])
    try:
        historical_data.load_candles_csv(p, "1h")
    except historical_data.HistoricalImportError as e:
        assert "duplicate" in str(e).lower()
        print("  ✓ csv import rejects duplicate timestamps")
        return
    raise AssertionError("expected HistoricalImportError")


def test_historical_csv_missing_columns():
    p = Path(_TEST_DIR) / "missing.csv"
    p.write_text("timestamp,open,high\n2024-01-01T00:00:00Z,1,2\n")
    try:
        historical_data.load_candles_csv(p, "1h")
    except historical_data.HistoricalImportError as e:
        assert "missing required fields" in str(e)
        print("  ✓ csv import rejects missing required columns")
        return
    raise AssertionError("expected HistoricalImportError")


def test_historical_json_import():
    p = Path(_TEST_DIR) / "ok.json"
    p.write_text(json.dumps([
        {"timestamp": "2024-01-01T00:00:00Z", "open": 2050, "high": 2055, "low": 2049, "close": 2052, "volume": 100},
        {"timestamp": 1704070800, "open": 2052, "high": 2058, "low": 2051, "close": 2057, "volume": 200},  # epoch sec
    ]))
    candles = historical_data.load_candles_json(p, "1h")
    assert len(candles) == 2
    print("  ✓ json import (mixed iso + epoch timestamps) works")


def test_historical_unsupported_extension():
    p = Path(_TEST_DIR) / "x.txt"
    p.write_text("nope")
    try:
        historical_data.load_candles(p)
    except historical_data.HistoricalImportError as e:
        assert "unsupported" in str(e).lower()
        print("  ✓ unsupported extension rejected")
        return
    raise AssertionError("expected HistoricalImportError")


def test_historical_unsupported_timeframe():
    p = Path(_TEST_DIR) / "ok.csv"
    _write_csv(p, [
        ("2024-01-01T00:00:00Z", 2050, 2055, 2049, 2052, 1000),
    ])
    try:
        historical_data.load_candles_csv(p, "13s")
    except historical_data.HistoricalImportError as e:
        assert "timeframe" in str(e)
        print("  ✓ unsupported timeframe rejected")
        return
    raise AssertionError("expected HistoricalImportError")


def test_backtest_consumes_imported_candles():
    """Generate ~120 candles, import them, and verify the backtest engine runs."""
    from backend.backtest.engine import BacktestEngine
    p = Path(_TEST_DIR) / "many.csv"
    rows = []
    base = 2050
    for i in range(120):
        ts = f"2024-01-{(i // 24) + 1:02d}T{(i % 24):02d}:00:00Z"
        o = base + i * 0.5
        h = o + 2
        l = o - 2
        c = o + 0.5
        rows.append((ts, o, h, l, c, 1000))
    _write_csv(p, rows)
    candles = historical_data.load_candles_csv(p, "1h")
    assert len(candles) == 120

    engine = BacktestEngine()
    result = engine.run(candles, warmup=30)
    assert "trade_log" in result
    assert "metrics" in result
    assert result["evaluated_candles"] == 90
    print("  ✓ backtest engine consumes imported historical candles")


# ════════════════════════════════════════════════════════════════════════════════
# Live-readiness gate
# ════════════════════════════════════════════════════════════════════════════════

def _ready_provider_status():
    return {
        "name": "oanda", "kind": "real", "is_real": True,
        "ready": True, "last_quote_age_seconds": 5, "reason": None,
    }


def _ready_broker_status():
    return {"enabled": True, "selected": "oanda", "implemented": True,
            "ready": True, "config_valid": True, "reason": None}


def test_readiness_blocks_when_simulated_data():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status={"name": "simulated", "kind": "simulated", "is_real": False,
                         "ready": True, "last_quote_age_seconds": 1},
        broker_status=_ready_broker_status(),
        settings={"system_mode": "live"},
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_SIMULATED_DATA in rules
    assert report.ready is False
    print("  ✓ readiness blocks live when data is simulated")


def test_readiness_blocks_when_live_disabled():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=False,
        provider_status=_ready_provider_status(),
        broker_status={"enabled": False, "implemented": False, "ready": False,
                       "reason": "disabled"},
        settings={"system_mode": "live"},
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_LIVE_DISABLED in rules
    assert report.ready is False
    print("  ✓ readiness blocks live when LIVE_BROKER_ENABLED is off")


def test_readiness_blocks_when_safe_mode():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status=_ready_provider_status(),
        broker_status=_ready_broker_status(),
        settings={"system_mode": "live", "safe_mode": True},
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_SAFE_MODE in rules
    print("  ✓ readiness blocks live when safe_mode is on")


def test_readiness_blocks_when_not_live_mode():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status=_ready_provider_status(),
        broker_status=_ready_broker_status(),
        settings={"system_mode": "paper_trading"},
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_NOT_LIVE_MODE in rules
    print("  ✓ readiness blocks live when system_mode != 'live'")


def test_readiness_blocks_when_data_stale():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status={"name": "oanda", "kind": "real", "is_real": True,
                         "ready": True, "last_quote_age_seconds": 9999},
        broker_status=_ready_broker_status(),
        settings={"system_mode": "live"},
        stale_data_seconds=60,
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_STALE_DATA in rules
    print("  ✓ readiness blocks live when data is stale")


def test_readiness_blocks_when_broker_not_implemented():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status=_ready_provider_status(),
        broker_status={"enabled": True, "implemented": False, "ready": False,
                       "reason": "skeleton only"},
        settings={"system_mode": "live"},
    )
    rules = [b.rule for b in report.blockers]
    assert RULE_BROKER_NOT_IMPLEMENTED in rules
    print("  ✓ readiness blocks live when broker is a skeleton")


def test_readiness_passes_when_everything_ready():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status=_ready_provider_status(),
        broker_status=_ready_broker_status(),
        settings={"system_mode": "live"},
    )
    assert report.ready is True
    assert report.to_dict()["hard_blocker_count"] == 0
    print("  ✓ readiness passes when everything is configured + ready")


def test_readiness_forwards_risk_blockers():
    report = live_readiness.evaluate_live_readiness(
        live_enabled=True,
        provider_status=_ready_provider_status(),
        broker_status=_ready_broker_status(),
        settings={"system_mode": "live"},
        risk_blockers=[{"rule": "weekend", "reason": "market closed", "severity": "hard"}],
    )
    assert report.ready is False
    assert any("risk_blocked" in b.rule for b in report.blockers)
    print("  ✓ readiness forwards risk-engine hard blockers")


# ════════════════════════════════════════════════════════════════════════════════
# Live broker (with gating)
# ════════════════════════════════════════════════════════════════════════════════

def test_live_broker_construct_blocked_when_disabled():
    os.environ.pop("LIVE_BROKER_ENABLED", None)
    try:
        live_broker.LiveBroker()
    except RuntimeError as e:
        assert "disabled" in str(e).lower()
        print("  ✓ LiveBroker refuses to construct when LIVE_BROKER_ENABLED is off")
        return
    raise AssertionError("expected RuntimeError")


def test_live_broker_construct_blocked_on_bad_config():
    os.environ["LIVE_BROKER_ENABLED"] = "true"
    os.environ.pop("OANDA_API_KEY", None)
    os.environ.pop("OANDA_ACCOUNT_ID", None)
    try:
        try:
            live_broker.LiveBroker()
        except RuntimeError as e:
            assert "OANDA missing env vars" in str(e)
            print("  ✓ LiveBroker refuses to construct when broker config invalid")
            return
        raise AssertionError("expected RuntimeError")
    finally:
        os.environ.pop("LIVE_BROKER_ENABLED", None)


def test_live_broker_status_when_disabled():
    """When LIVE_BROKER_ENABLED is unset, status should report NOT enabled,
    NOT ready, regardless of whether any adapter subclass is wired up.
    Phase 3 landed an OANDA adapter, so `implemented` depends on LIVE_BROKER
    selection; we only assert the safety-critical fields here."""
    os.environ.pop("LIVE_BROKER_ENABLED", None)
    s = live_broker.get_live_broker_status()
    assert s["enabled"] is False
    assert s["ready"] is False
    assert s["config_valid"] is False
    print("  ✓ live broker status reports disabled honestly")


def test_live_broker_submit_order_blocked_via_readiness():
    """Phase 2 intent: the base LiveBroker class is an abstract skeleton and
    must NEVER actually route orders. Phase 3 added a concrete OandaLiveBroker
    subclass, so the base class's submit_order() now raises NotImplementedError
    (after readiness passes the broker gate for OANDA). Either outcome --
    LiveExecutionBlocked or NotImplementedError -- is acceptable here; what
    matters is that the base class cannot submit an order."""
    os.environ["LIVE_BROKER_ENABLED"] = "true"
    os.environ["OANDA_API_KEY"] = "fake"
    os.environ["OANDA_ACCOUNT_ID"] = "acct"
    try:
        broker = live_broker.LiveBroker(
            provider_status=_ready_provider_status(),
            settings={"system_mode": "live"},
            risk_blockers=[],
        )
        from backend.execution.broker_base import BrokerOrder
        order = BrokerOrder(direction="long", entry=2050, stop=2040,
                            target_1=2070, position_lots=0.1)
        try:
            broker.submit_order(order)
        except (live_readiness.LiveExecutionBlocked, NotImplementedError):
            print("  ✓ LiveBroker (abstract) refuses to route orders")
            return
        raise AssertionError("expected LiveExecutionBlocked or NotImplementedError")
    finally:
        for k in ("LIVE_BROKER_ENABLED", "OANDA_API_KEY", "OANDA_ACCOUNT_ID"):
            os.environ.pop(k, None)


def test_live_broker_submit_order_blocked_on_simulated_data():
    os.environ["LIVE_BROKER_ENABLED"] = "true"
    os.environ["OANDA_API_KEY"] = "fake"
    os.environ["OANDA_ACCOUNT_ID"] = "acct"
    try:
        broker = live_broker.LiveBroker(
            provider_status={"name": "simulated", "kind": "simulated",
                             "is_real": False, "ready": True,
                             "last_quote_age_seconds": 1},
            settings={"system_mode": "live"},
            risk_blockers=[],
        )
        from backend.execution.broker_base import BrokerOrder
        order = BrokerOrder(direction="long", entry=2050, stop=2040,
                            target_1=2070, position_lots=0.1)
        try:
            broker.submit_order(order)
        except live_readiness.LiveExecutionBlocked as e:
            rules = [b.rule for b in e.report.blockers]
            assert RULE_SIMULATED_DATA in rules
            print("  ✓ LiveBroker.submit_order blocked by readiness gate (simulated data)")
            return
        raise AssertionError("expected LiveExecutionBlocked")
    finally:
        for k in ("LIVE_BROKER_ENABLED", "OANDA_API_KEY", "OANDA_ACCOUNT_ID"):
            os.environ.pop(k, None)


# ════════════════════════════════════════════════════════════════════════════════
# HTTP — /api/health, /api/readiness, /api/historical, /api/backtest/historical
# ════════════════════════════════════════════════════════════════════════════════

def test_http_health_includes_phase2_fields():
    status, body = http_get("/api/health")
    assert status == 200
    for k in ("data_source", "data_is_real", "data_provider_ready",
              "live_ready", "live_blocker_rules", "live_broker_implemented",
              "claude_available", "paper_available"):
        assert k in body, f"missing field {k!r}"
    # Defaults: simulated data, live blocked.
    assert body["data_source"] == "simulated"
    assert body["data_is_real"] is False
    assert body["live_ready"] is False
    assert "simulated_data" in body["live_blocker_rules"] or \
           "live_disabled" in body["live_blocker_rules"]
    print("  ✓ /api/health surfaces phase 2 readiness fields")


def test_http_readiness_endpoint():
    status, body = http_get("/api/readiness")
    assert status == 200
    assert "report" in body
    assert "provider_status" in body
    assert "broker_status" in body
    assert body["report"]["ready"] is False  # default config
    assert body["report"]["blocker_count"] >= 1
    print("  ✓ /api/readiness returns full readiness report")


def test_http_historical_list_empty_or_present():
    status, body = http_get("/api/historical/list")
    assert status == 200
    assert "files" in body
    assert isinstance(body["files"], list)
    print("  ✓ /api/historical/list returns inventory")


def test_http_backtest_historical_round_trip():
    # Write a small file into the live DATA_DIR/historical/.
    hist_dir = Path(_TEST_DIR) / "historical"
    hist_dir.mkdir(exist_ok=True)
    fn = "test_xau.csv"
    rows = []
    for i in range(80):
        ts = f"2024-02-{(i // 24) + 1:02d}T{(i % 24):02d}:00:00Z"
        o = 2050 + i * 0.3
        rows.append(f"{ts},{o},{o+2},{o-2},{o+0.5},1000")
    (hist_dir / fn).write_text("timestamp,open,high,low,close,volume\n" + "\n".join(rows))

    # List should now show it
    _, listing = http_get("/api/historical/list")
    assert any(f["filename"] == fn for f in listing["files"])

    # Run backtest
    status, body = http_post("/api/backtest/historical", {"filename": fn, "timeframe": "1h"})
    assert status == 200, body
    assert body["source"] == "historical_import"
    assert body["candles_loaded"] == 80
    assert "backtest" in body and "metrics" in body["backtest"]
    print("  ✓ /api/backtest/historical loads and backtests imported data")


def test_http_backtest_historical_rejects_path_traversal():
    status, body = http_post("/api/backtest/historical", {"filename": "../../etc/passwd"})
    assert status == 400
    assert "path separators" in body.get("error", "")
    print("  ✓ /api/backtest/historical rejects path traversal")


def test_http_backtest_historical_missing_file():
    status, body = http_post("/api/backtest/historical", {"filename": "no_such_file.csv"})
    assert status == 404
    assert "not found" in body.get("error", "")
    print("  ✓ /api/backtest/historical reports missing file cleanly")


# ════════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    setup_module()
    try:
        tests = [name for name in dir() if name.startswith("test_")]
        passed = failed = 0
        for name in sorted(tests):
            try:
                globals()[name]()
                passed += 1
            except Exception as e:
                print(f"  ✗ {name}: {e}")
                import traceback
                traceback.print_exc()
                failed += 1
        print(f"\nPhase 2: {passed}/{passed+failed} passed" + (f", {failed} FAILED" if failed else ""))
        if failed:
            sys.exit(1)
    finally:
        teardown_module()
