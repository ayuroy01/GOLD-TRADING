"""
HTTP-level tests for Gold Intelligence System backend v4.
Tests actual HTTP endpoints against the running server.

Run: python3 -m pytest backend/test_http.py -v
  or: cd backend && python3 test_http.py
"""

import sys
import os
import json
import tempfile
import threading
import time
import socket
import http.client
from pathlib import Path

# Setup before importing server
_TEST_DIR = tempfile.mkdtemp(prefix="gold_http_test_")
os.environ["DATA_DIR"] = _TEST_DIR

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from http.server import HTTPServer
import server
from server import GoldAgentHandler

_PORT = None  # Assigned dynamically in setup_module
_server = None
_thread = None


def _find_free_port():
    """Ask the OS for an ephemeral port that is guaranteed free right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def setup_module():
    """Start HTTP server on an ephemeral port in a background thread."""
    global _server, _thread, _PORT
    server._reinitialize_data_dir(_TEST_DIR)
    _PORT = _find_free_port()
    _server = HTTPServer(("127.0.0.1", _PORT), GoldAgentHandler)
    _server.allow_reuse_address = True
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    time.sleep(0.2)


def teardown_module():
    """Fully stop and close the HTTP server socket."""
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
    status = resp.status
    conn.close()
    return status, body


def http_post(path, data=None, raw_body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=30)
    hdrs = {"Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    if raw_body is not None:
        body = raw_body
    elif data is not None:
        body = json.dumps(data)
    else:
        body = "{}"
    conn.request("POST", path, body=body, headers=hdrs)
    resp = conn.getresponse()
    raw = resp.read().decode()
    status = resp.status
    conn.close()
    result = json.loads(raw)
    return status, result


def http_put(path, data):
    conn = http.client.HTTPConnection("127.0.0.1", _PORT, timeout=10)
    headers = {"Content-Type": "application/json"}
    conn.request("PUT", path, body=json.dumps(data), headers=headers)
    resp = conn.getresponse()
    result = json.loads(resp.read().decode())
    status = resp.status
    conn.close()
    return status, result


# ═══════════════════════════════════════════════════════════════════════════════
# GET endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_http_health():
    """GET /api/health returns status ok, version 4.0, strategies, system_mode, live_enabled=False."""
    reset_data()
    status, body = http_get("/api/health")
    assert status == 200
    assert body["status"] == "ok"
    assert body["version"] == "4.0"
    assert isinstance(body["strategies"], list)
    assert len(body["strategies"]) >= 1
    assert "system_mode" in body
    assert body["live_enabled"] is False
    print("  OK test_http_health")


def test_http_features():
    """GET /api/features returns dict with price, atr_14, trend_1h, session, etc."""
    reset_data()
    status, body = http_get("/api/features")
    assert status == 200
    assert "price" in body
    assert isinstance(body["price"], (int, float))
    assert body["price"] > 0
    assert "atr_14" in body
    assert "trend_1h" in body
    assert body["trend_1h"] in ("uptrend", "downtrend", "ranging")
    assert "session" in body
    assert "is_weekend" in body
    assert "spread_regime" in body
    print("  OK test_http_features")


def test_http_strategies():
    """GET /api/strategies returns strategies list with 3 entries."""
    reset_data()
    status, body = http_get("/api/strategies")
    assert status == 200
    assert "strategies" in body
    assert isinstance(body["strategies"], list)
    assert len(body["strategies"]) == 3
    for s in body["strategies"]:
        assert "strategy_name" in s
        assert "valid" in s
    print("  OK test_http_strategies")


def test_http_risk():
    """GET /api/risk returns trading_allowed (bool), blockers (list), config."""
    reset_data()
    status, body = http_get("/api/risk")
    assert status == 200
    assert "trading_allowed" in body
    assert isinstance(body["trading_allowed"], bool)
    assert "blockers" in body
    assert isinstance(body["blockers"], list)
    assert "config" in body
    assert isinstance(body["config"], dict)
    print("  OK test_http_risk")


def test_http_paper_account():
    """GET /api/paper/account returns balance, equity, mode='paper'."""
    reset_data()
    status, body = http_get("/api/paper/account")
    assert status == 200
    assert "balance" in body
    assert "equity" in body
    assert body["mode"] == "paper"
    print("  OK test_http_paper_account")


def test_http_paper_positions():
    """GET /api/paper/positions returns list (initially empty)."""
    reset_data()
    status, body = http_get("/api/paper/positions")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 0
    print("  OK test_http_paper_positions")


def test_http_paper_fills():
    """GET /api/paper/fills returns list (initially empty)."""
    reset_data()
    status, body = http_get("/api/paper/fills")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 0
    print("  OK test_http_paper_fills")


def test_http_decisions():
    """GET /api/decisions returns empty list after reset."""
    reset_data()
    status, body = http_get("/api/decisions")
    assert status == 200
    assert isinstance(body, list)
    assert len(body) == 0
    print("  OK test_http_decisions")


def test_http_decisions_analysis():
    """GET /api/decisions/analysis returns claude_stats, deterministic_stats."""
    reset_data()
    status, body = http_get("/api/decisions/analysis")
    assert status == 200
    assert "claude_stats" in body
    assert "deterministic_stats" in body
    assert "total_decisions" in body
    assert "decisions_with_outcomes" in body
    print("  OK test_http_decisions_analysis")


def test_http_experiments():
    """GET /api/experiments returns list."""
    reset_data()
    status, body = http_get("/api/experiments")
    assert status == 200
    assert isinstance(body, list)
    print("  OK test_http_experiments")


# ═══════════════════════════════════════════════════════════════════════════════
# POST endpoint tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_http_decide():
    """POST /api/decide with use_claude=false returns structured decision."""
    reset_data()
    status, body = http_post("/api/decide", {"use_claude": False})
    assert status == 200
    assert "decision_id" in body
    assert "decision" in body
    assert isinstance(body["decision"], dict)
    assert "setups_evaluated" in body
    assert isinstance(body["setups_evaluated"], list)
    assert body["claude_used"] is False
    assert "trade_or_no_trade" in body
    assert body["trade_or_no_trade"] in ("trade", "no_trade")
    assert "risk_blockers" in body
    assert "timestamp" in body
    dec = body["decision"]
    assert "market_state" in dec
    assert "confidence" in dec
    assert "trade_or_no_trade" in dec
    print("  OK test_http_decide")


def test_http_backtest():
    """POST /api/backtest returns backtest.metrics and baselines."""
    reset_data()
    status, body = http_post("/api/backtest", {"candles": 100, "spread": 0.40})
    assert status == 200
    assert "backtest" in body
    bt = body["backtest"]
    assert "metrics" in bt
    assert "trade_log" in bt
    assert "total_candles" in bt
    assert bt["total_candles"] == 100
    assert "baselines" in body
    assert isinstance(body["baselines"], list)
    assert len(body["baselines"]) == 2
    print("  OK test_http_backtest")


def test_http_walk_forward():
    """POST /api/backtest/walk-forward with folds=2 returns n_folds=2, folds list, aggregate_oos_metrics."""
    reset_data()
    status, body = http_post("/api/backtest/walk-forward", {"candles": 200, "folds": 2})
    assert status == 200
    assert body["n_folds"] == 2
    assert "folds" in body
    assert isinstance(body["folds"], list)
    assert len(body["folds"]) == 2
    for fold in body["folds"]:
        assert "train_metrics" in fold
        assert "test_metrics" in fold
    assert "aggregate_oos_metrics" in body
    print("  OK test_http_walk_forward")


# ═══════════════════════════════════════════════════════════════════════════════
# Validation failure tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_http_malformed_json():
    """POST /api/trades with body 'not json' returns 400."""
    reset_data()
    status, body = http_post("/api/trades", raw_body="not json")
    assert status == 400
    assert "error" in body
    print("  OK test_http_malformed_json")


def test_http_missing_required_fields():
    """POST /api/trades with {} returns 400 with error about missing fields."""
    reset_data()
    status, body = http_post("/api/trades", data={})
    assert status == 400
    assert "error" in body
    error_lower = body["error"].lower()
    assert "missing" in error_lower or "field" in error_lower
    print("  OK test_http_missing_required_fields")


def test_http_invalid_trade_id():
    """PUT /api/trades/abc returns 400."""
    reset_data()
    status, body = http_put("/api/trades/abc", {"status": "closed"})
    assert status == 400
    assert "error" in body
    print("  OK test_http_invalid_trade_id")


def test_http_invalid_settings():
    """POST /api/settings with equity=-100 returns 400."""
    reset_data()
    status, body = http_post("/api/settings", {"equity": -100})
    assert status == 400
    assert "error" in body
    print("  OK test_http_invalid_settings")


def test_http_paper_execute_no_decision():
    """POST /api/paper/execute with nonexistent decision_id returns 404."""
    reset_data()
    status, body = http_post("/api/paper/execute", {"decision_id": "nonexistent123"})
    assert status == 404
    assert "error" in body
    print("  OK test_http_paper_execute_no_decision")


def test_http_not_found():
    """GET /api/nonexistent returns 404."""
    reset_data()
    status, body = http_get("/api/nonexistent")
    assert status == 404
    assert "error" in body
    print("  OK test_http_not_found")


# ═══════════════════════════════════════════════════════════════════════════════
# Paper trade flow
# ═══════════════════════════════════════════════════════════════════════════════


def test_http_paper_execute_flow():
    """Full flow: POST /api/decide then POST /api/paper/execute."""
    reset_data()

    # Step 1: Get a decision
    status, decision_result = http_post("/api/decide", {"use_claude": False})
    assert status == 200
    assert "decision_id" in decision_result
    assert "trade_or_no_trade" in decision_result

    decision_id = decision_result["decision_id"]
    trade_or_no = decision_result["trade_or_no_trade"]

    if trade_or_no == "trade":
        # The decision was a trade, so execute it
        status, exec_result = http_post("/api/paper/execute", {"decision_id": decision_id})
        assert status == 200
        assert "fill" in exec_result
        assert "position_size" in exec_result
        fill = exec_result["fill"]
        assert fill["status"] == "filled"
        assert "position_id" in fill
        print("  OK test_http_paper_execute_flow (trade executed)")
    else:
        # Decision was no_trade -- executing it should fail with 400
        status, exec_result = http_post("/api/paper/execute", {"decision_id": decision_id})
        assert status == 400
        assert "error" in exec_result
        assert "no_trade" in exec_result["error"].lower() or "no_trade" in json.dumps(exec_result).lower()

        # Also verify that execute without decision_id creates its own decision.
        # Since the market state is the same, this will likely also be no_trade,
        # but either outcome is valid.
        status2, exec_result2 = http_post("/api/paper/execute", {"use_claude": False})
        if status2 == 200:
            # It generated a trade decision on the fly and executed it
            assert "fill" in exec_result2
        else:
            # It generated a no_trade decision -> returned 400
            assert status2 == 400
            assert "error" in exec_result2
        print("  OK test_http_paper_execute_flow (no_trade handled)")


# ═══════════════════════════════════════════════════════════════════════════════
# Auth tests
# ═══════════════════════════════════════════════════════════════════════════════


def test_http_auth_health_always_public():
    """GET /api/health must be accessible even when auth is enabled."""
    old_token = server.API_AUTH_TOKEN
    try:
        server.API_AUTH_TOKEN = "test-secret-token"
        status, body = http_get("/api/health")
        assert status == 200
        assert body["status"] == "ok"
        assert body["auth_enabled"] is True
        print("  OK test_http_auth_health_always_public")
    finally:
        server.API_AUTH_TOKEN = old_token


def test_http_auth_rejects_without_token():
    """Protected endpoints return 401 when auth is enabled and no token is sent."""
    old_token = server.API_AUTH_TOKEN
    try:
        server.API_AUTH_TOKEN = "test-secret-token"
        status, body = http_get("/api/price")
        assert status == 401
        assert "error" in body
        print("  OK test_http_auth_rejects_without_token")
    finally:
        server.API_AUTH_TOKEN = old_token


def test_http_auth_accepts_valid_token():
    """Protected endpoints return 200 with valid Bearer token."""
    old_token = server.API_AUTH_TOKEN
    try:
        server.API_AUTH_TOKEN = "test-secret-token"
        status, body = http_get("/api/price", headers={"Authorization": "Bearer test-secret-token"})
        assert status == 200
        assert "price" in body
        print("  OK test_http_auth_accepts_valid_token")
    finally:
        server.API_AUTH_TOKEN = old_token


def test_http_auth_rejects_wrong_token():
    """Protected endpoints return 401 with wrong Bearer token."""
    old_token = server.API_AUTH_TOKEN
    try:
        server.API_AUTH_TOKEN = "test-secret-token"
        status, body = http_get("/api/price", headers={"Authorization": "Bearer wrong-token"})
        assert status == 401
        assert "error" in body
        print("  OK test_http_auth_rejects_wrong_token")
    finally:
        server.API_AUTH_TOKEN = old_token


def test_http_auth_post_requires_token():
    """POST endpoints return 401 when auth is enabled and no token is sent."""
    old_token = server.API_AUTH_TOKEN
    try:
        server.API_AUTH_TOKEN = "test-secret-token"
        status, body = http_post("/api/decide", {"use_claude": False})
        assert status == 401
        assert "error" in body
        print("  OK test_http_auth_post_requires_token")
    finally:
        server.API_AUTH_TOKEN = old_token


# ═══════════════════════════════════════════════════════════════════════════════
# Run All
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    print(f"\nRunning {len(tests)} HTTP tests...\n")
    setup_module()
    try:
        for test in tests:
            try:
                test()
                passed += 1
            except Exception as e:
                failed += 1
                import traceback
                print(f"  FAIL {test.__name__}: {e}")
                traceback.print_exc()
    finally:
        teardown_module()
    print(f"\n{'=' * 40}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'=' * 40}")
    sys.exit(1 if failed else 0)
