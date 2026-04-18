"""
End-to-end integration tests: decision → paper trade → close → journal sync.
Tests the full pipeline using server.py functions directly (no HTTP).

Run: python3 -m pytest backend/test_e2e.py -v
  or: cd backend && python3 test_e2e.py
"""

import sys
import os
import json
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

_TEST_DIR = tempfile.mkdtemp(prefix="gold_e2e_test_")
os.environ["DATA_DIR"] = _TEST_DIR

import server
server._reinitialize_data_dir(_TEST_DIR)

from backend.agent.decision_engine import DecisionEngine
from backend.execution.broker_base import BrokerOrder
from backend.features.market_features import compute_all_features


def reset_data():
    server._reinitialize_data_dir(_TEST_DIR)
    for f in Path(_TEST_DIR).glob("*.json"):
        f.unlink()


def _make_features():
    """Build a features dict from simulated providers."""
    quote = server.market_provider.get_quote()
    candles = server.market_provider.get_candles("1h", 100)
    features = compute_all_features(
        candles_1h=candles,
        quote=quote,
        macro={
            "usd_regime": "neutral",
            "gold_macro_bias": "neutral",
            "geopolitical_risk": "moderate",
            "vix_regime": "low_vol",
        },
        calendar={"high_impact_within_2h": False, "nearest_high_impact": None},
    )
    return features, candles


# ═══════════════════════════════════════════════════════════════════════════════


def test_e2e_decision_to_journal():
    """Full pipeline: decision → paper trade → close → journal sync → verify.

    Always exercises the full trade path by using a synthetic trade decision
    when the simulated market doesn't produce a valid setup.
    """
    reset_data()

    features, candles = _make_features()
    engine = DecisionEngine(api_key="")
    result = engine.decide(features, {"1h": candles}, use_claude=False)

    assert "decision_id" in result
    assert result["trade_or_no_trade"] in ("trade", "no_trade")

    # Store decision
    server.decision_store.store(result)
    stored = server.decision_store.get_recent(100)
    assert len(stored) == 1
    assert stored[0]["id"] == result["decision_id"]

    # Use the engine's decision if it's a trade, otherwise build a synthetic
    # one so we always exercise the full open → close → journal path.
    if result["trade_or_no_trade"] == "trade":
        decision = result["decision"]
    else:
        decision = {
            "entry": 3250.00,
            "stop": 3240.00,
            "target_1": 3270.00,
            "target_2": 3290.00,
            "chosen_strategy": "trend_pullback",
            "confidence": 65,
            "trade_or_no_trade": "trade",
        }

    # --- Open paper position ---
    order = BrokerOrder(
        direction="long" if decision["entry"] > decision["stop"] else "short",
        entry=decision["entry"],
        stop=decision["stop"],
        target_1=decision["target_1"],
        target_2=decision.get("target_2"),
        position_lots=0.1,
        strategy=decision.get("chosen_strategy", "unknown"),
        decision_id=result["decision_id"],
    )
    broker = server.get_paper_broker()
    fill = broker.submit_order(order)
    assert fill["status"] == "filled"
    assert "position_id" in fill

    positions = broker.get_positions()
    assert len(positions) == 1
    pos = positions[0]
    assert pos.position_id == fill["position_id"]

    # --- Log journal entry (simulates HTTP handler logic) ---
    risk_dist = abs(decision["entry"] - decision["stop"])
    rr = abs(decision["target_1"] - decision["entry"]) / risk_dist if risk_dist > 0 else 0
    trade_entry = {
        "id": 1,
        "date": result["timestamp"],
        "direction": order.direction,
        "entry": decision["entry"],
        "stop": decision["stop"],
        "t1": decision["target_1"],
        "t2": decision.get("target_2"),
        "zone": "EMA",
        "trigger": "Bullish Engulfing" if order.direction == "long" else "Bearish Engulfing",
        "risk_distance": round(risk_dist, 2),
        "rr_to_t1": round(rr, 2),
        "position_oz": round(0.1 * 100, 2),
        "position_lots": 0.1,
        "risk_usd": round(risk_dist * 10, 2),
        "status": "open",
        "exit_price": None,
        "r_multiple": None,
        "error_type": "None",
        "notes": "e2e test",
        "source": "paper_broker",
        "paper_position_id": fill["position_id"],
    }
    server.save_json(server.TRADES_FILE, [trade_entry])

    # --- Close paper position ---
    close_price = decision["target_1"]
    close_result = broker.close_position(fill["position_id"], close_price)
    assert close_result["status"] == "closed"
    assert "r_multiple" in close_result
    assert "pnl" in close_result

    # --- Update journal entry with exit info (simulates HTTP handler) ---
    trades = server.load_json(server.TRADES_FILE, [])
    assert len(trades) == 1
    for t in trades:
        if t.get("paper_position_id") == fill["position_id"]:
            t["status"] = "closed"
            t["exit_price"] = close_result["exit_price"]
            t["r_multiple"] = close_result["r_multiple"]
            t["exit_reason"] = "target_1"
            break
    server.save_json(server.TRADES_FILE, trades)

    # --- Verify journal has both open and close data ---
    final_trades = server.load_json(server.TRADES_FILE, [])
    assert len(final_trades) == 1
    t = final_trades[0]
    assert t["status"] == "closed"
    assert t["entry"] == decision["entry"]
    assert t["exit_price"] == close_result["exit_price"]
    assert t["r_multiple"] == close_result["r_multiple"]
    assert t["paper_position_id"] == fill["position_id"]
    assert t["source"] == "paper_broker"

    # --- Verify paper broker account updated ---
    account = broker.get_account()
    assert account["open_positions"] == 0
    assert account["trades_today"] >= 1

    print("  ✓ e2e decision → paper trade → close → journal sync")


def test_e2e_journal_metrics_consistency():
    """Create journal entries and verify they round-trip correctly."""
    reset_data()

    trades = [
        {
            "id": 1, "direction": "long", "entry": 3250, "stop": 3240,
            "t1": 3270, "status": "closed", "exit_price": 3268,
            "r_multiple": 1.8, "error_type": "None", "notes": "win 1",
            "date": "2024-01-15T10:00:00Z", "risk_distance": 10,
            "rr_to_t1": 2.0, "position_lots": 0.1, "risk_usd": 100,
        },
        {
            "id": 2, "direction": "short", "entry": 3280, "stop": 3290,
            "t1": 3260, "status": "closed", "exit_price": 3262,
            "r_multiple": 1.8, "error_type": "None", "notes": "win 2",
            "date": "2024-01-15T11:00:00Z", "risk_distance": 10,
            "rr_to_t1": 2.0, "position_lots": 0.1, "risk_usd": 100,
        },
        {
            "id": 3, "direction": "long", "entry": 3260, "stop": 3250,
            "t1": 3280, "status": "closed", "exit_price": 3252,
            "r_multiple": -0.8, "error_type": "Timing", "notes": "loss",
            "date": "2024-01-15T14:00:00Z", "risk_distance": 10,
            "rr_to_t1": 2.0, "position_lots": 0.1, "risk_usd": 100,
        },
    ]
    server.save_json(server.TRADES_FILE, trades)

    loaded = server.load_json(server.TRADES_FILE, [])
    assert len(loaded) == 3

    closed = [t for t in loaded if t["status"] == "closed"]
    assert len(closed) == 3

    wins = [t for t in closed if t["r_multiple"] > 0]
    losses = [t for t in closed if t["r_multiple"] <= 0]
    assert len(wins) == 2
    assert len(losses) == 1

    for t in loaded:
        assert "id" in t
        assert "direction" in t
        assert "entry" in t
        assert "stop" in t
        assert "status" in t
        assert t["direction"] in ("long", "short")

    print("  ✓ e2e journal metrics consistency")


def test_e2e_decision_store_round_trip():
    """Decisions survive store → load cycle with all fields intact."""
    reset_data()

    features, candles = _make_features()
    engine = DecisionEngine(api_key="")

    results = []
    for _ in range(3):
        r = engine.decide(features, {"1h": candles}, use_claude=False)
        server.decision_store.store(r)
        results.append(r)

    stored = server.decision_store.get_recent(100)
    assert len(stored) == 3

    for i, s in enumerate(stored):
        assert s["id"] == results[i]["decision_id"]

    print("  ✓ e2e decision store round-trip")


# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [f for f in dir() if f.startswith("test_")]
    passed = 0
    failed = 0
    for name in sorted(tests):
        try:
            globals()[name]()
            passed += 1
        except Exception as e:
            print(f"  ✗ {name}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    total = passed + failed
    print(f"\n{'='*60}")
    print(f"E2E tests: {passed}/{total} passed" + (f", {failed} FAILED" if failed else ""))
    if failed:
        sys.exit(1)
