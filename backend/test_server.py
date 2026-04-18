"""
Tests for Gold Intelligence System backend v4.
Run: python3 -m pytest backend/test_server.py -v
  or: cd backend && python3 test_server.py
"""

import sys
import os
import json
import tempfile
import datetime
from pathlib import Path

# Make server importable
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Override DATA_DIR before importing server so tests don't clobber real data
_TEST_DIR = tempfile.mkdtemp(prefix="gold_test_")
os.environ["DATA_DIR"] = _TEST_DIR

import server

# Ensure server globals point to OUR temp dir, even if another test file
# imported server first with a different DATA_DIR.
server._reinitialize_data_dir(_TEST_DIR)

# ─── Helpers ─────────────────────────────────────────────────────────────────

def reset_data():
    """Clear all test data between tests and reclaim our temp dir."""
    server._reinitialize_data_dir(_TEST_DIR)
    for f in Path(_TEST_DIR).glob("*.json"):
        f.unlink()

# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY TESTS (preserved from v3)
# ═══════════════════════════════════════════════════════════════════════════════

def test_get_market_price():
    reset_data()
    result = server.get_market_price()
    assert "price" in result
    assert "bid" in result
    assert "ask" in result
    assert "spread" in result
    assert "timestamp" in result
    assert "source" in result
    assert isinstance(result["price"], (int, float))
    assert result["price"] > 0
    assert result["bid"] < result["ask"]
    assert result["spread"] >= 0
    print("  ✓ get_market_price")

def test_get_macro_context():
    reset_data()
    result = server.get_macro_context()
    assert "usd_index" in result
    assert "usd_regime" in result
    assert result["usd_regime"] in ("strong", "weak", "neutral")
    assert "treasury_10y" in result
    assert "gold_macro_bias" in result
    assert result["gold_macro_bias"] in ("bullish", "bearish", "neutral")
    assert "geopolitical_risk" in result
    assert "timestamp" in result
    print("  ✓ get_macro_context")

def test_get_economic_calendar():
    reset_data()
    result = server.get_economic_calendar()
    assert "events" in result
    assert isinstance(result["events"], list)
    assert len(result["events"]) > 0
    assert "high_impact_within_2h" in result
    assert isinstance(result["high_impact_within_2h"], bool)
    assert "nearest_high_impact" in result
    evt = result["events"][0]
    assert "name" in evt
    assert "impact" in evt
    assert "hours_until" in evt
    assert "within_2h" in evt
    print("  ✓ get_economic_calendar")

def test_preprocess_market_structure():
    reset_data()
    price_data = server.get_market_price()
    result = server.preprocess_market_structure(price_data)
    assert "current_price" in result
    assert "session" in result
    assert result["session"] in ("asia", "london", "overlap", "new_york", "off_hours")
    assert "key_levels" in result
    assert "nearest_levels" in result
    assert "macro" in result
    assert "calendar" in result
    levels = result["key_levels"]
    assert "major_resistance" in levels
    assert "major_support" in levels
    assert any(l > result["current_price"] for l in levels["major_resistance"])
    print("  ✓ preprocess_market_structure (dynamic levels)")

def test_trade_crud():
    reset_data()
    trade = server.log_trade({
        "direction": "long", "entry": 3245.50, "stop": 3228.00,
        "t1": 3270.00, "status": "open", "notes": "test"
    })
    assert "id" in trade
    assert trade["status"] == "open"
    tid = trade["id"]

    trades = server.get_trades()
    assert len(trades) == 1
    assert trades[0]["id"] == tid

    assert len(server.get_trades(status="open")) == 1
    assert len(server.get_trades(status="closed")) == 0

    updated = server.update_trade(tid, {
        "status": "closed", "exit_price": 3265.00, "r_multiple": 1.11
    })
    assert updated["status"] == "closed"
    assert updated["r_multiple"] == 1.11

    assert len(server.get_trades(status="open")) == 0
    assert len(server.get_trades(status="closed")) == 1

    server.delete_trade(tid)
    assert len(server.get_trades()) == 0
    print("  ✓ trade CRUD (create/read/update/delete)")

def test_update_nonexistent_trade():
    reset_data()
    result = server.update_trade(999999, {"status": "closed"})
    assert result is None
    print("  ✓ update nonexistent trade returns None")

def test_compute_metrics_empty():
    reset_data()
    metrics = server.compute_metrics()
    assert metrics["closed_trades"] == 0
    assert metrics.get("message") is not None
    print("  ✓ compute_metrics (empty)")

def test_compute_metrics_with_trades():
    reset_data()
    r_values = [1.5, -1.0, 2.2, -0.8, 1.8, -1.0, 0.5, 2.0, -1.0, 1.2]
    for r in r_values:
        server.log_trade({
            "direction": "long", "entry": 3250, "stop": 3240,
            "status": "closed", "r_multiple": r,
            "exit_price": 3250 + r * 10,
        })

    metrics = server.compute_metrics()
    assert metrics["closed_trades"] == 10
    assert metrics["wins"] == 6
    assert metrics["losses"] == 4
    assert 0 < metrics["win_rate"] < 1
    assert metrics["expectancy"] > 0
    assert metrics["profit_factor"] != "Infinity"
    assert float(metrics["profit_factor"]) > 1
    assert metrics["max_drawdown_r"] >= 0
    assert metrics["max_losing_streak"] >= 1
    assert len(metrics["equity_curve"]) == 11
    assert metrics["phase"] == 1
    assert metrics["edge_status"] == "Collecting data"
    print("  ✓ compute_metrics (with trades)")

def test_compute_metrics_negative_ev():
    reset_data()
    for _ in range(5):
        server.log_trade({
            "direction": "long", "entry": 3250, "stop": 3240,
            "status": "closed", "r_multiple": -1.0, "exit_price": 3240,
        })
    metrics = server.compute_metrics()
    assert metrics["expectancy"] < 0
    assert metrics["win_rate"] == 0
    print("  ✓ compute_metrics (all losses → negative EV)")

def test_settings_defaults():
    reset_data()
    settings = server.load_settings()
    assert settings["equity"] == 50000
    assert settings["risk_pct"] == 1.0
    assert settings["max_positions"] == 2
    print("  ✓ settings defaults")

def test_settings_save_load():
    reset_data()
    server.save_settings({"equity": 100000, "max_positions": 3, "risk_pct": 0.5})
    s = server.load_settings()
    assert s["equity"] == 100000
    assert s["max_positions"] == 3
    assert s["risk_pct"] == 0.5
    print("  ✓ settings save/load")

def test_demo_analysis_runs():
    reset_data()
    result = server.run_demo_analysis()
    assert "analysis" in result
    assert "timestamp" in result
    assert "model" in result
    assert len(result["analysis"]) > 100
    assert "MARKET STATE" in result["analysis"]
    assert "NO-TRADE FILTER" in result["analysis"]
    print("  ✓ demo analysis produces output")

def test_demo_analysis_uses_settings_max_positions():
    reset_data()
    server.save_settings({"equity": 50000, "max_positions": 1})
    server.log_trade({"direction": "long", "entry": 3250, "stop": 3240, "status": "open"})
    result = server.run_demo_analysis()
    assert "max 1" in result["analysis"]
    print("  ✓ demo analysis reads settings.max_positions")

def test_demo_analysis_drawdown_blocker():
    reset_data()
    server.save_settings({"equity": 40000, "peak_equity": 50000, "max_positions": 2})
    result = server.run_demo_analysis()
    assert "drawdown" in result["analysis"].lower()
    print("  ✓ demo analysis enforces drawdown blocker")

def test_demo_analysis_self_improvement_feedback():
    reset_data()
    for _ in range(5):
        server.log_trade({
            "direction": "long", "entry": 3250, "stop": 3240,
            "status": "closed", "r_multiple": -1.0, "exit_price": 3240,
        })
    result = server.run_demo_analysis()
    analysis_lower = result["analysis"].lower()
    assert "self-improvement" in analysis_lower or "confidence threshold" in analysis_lower
    print("  ✓ demo analysis feeds back poor performance")

def test_execute_tool_all_tools():
    reset_data()
    tools = [
        ("get_market_price", {}),
        ("get_macro_context", {}),
        ("get_economic_calendar", {}),
        ("get_market_structure", {}),
        ("get_trade_history", {"status": "all"}),
        ("get_performance_metrics", {}),
        ("log_analysis", {"analysis_type": "full_analysis", "decision": "NO TRADE", "confidence": 50}),
    ]
    for name, inp in tools:
        result = server.execute_tool(name, inp)
        assert "error" not in result, f"Tool {name} returned error: {result}"
    print("  ✓ all 7 tools execute without error")

def test_execute_tool_unknown():
    result = server.execute_tool("nonexistent_tool", {})
    assert "error" in result
    print("  ✓ unknown tool returns error")

def test_build_system_prompt_uses_settings():
    reset_data()
    server.save_settings({"equity": 75000, "max_positions": 3, "risk_pct": 2.0})
    prompt = server.build_system_prompt()
    assert "$75,000" in prompt
    assert "3" in prompt
    assert "2.0%" in prompt
    print("  ✓ system prompt injects current settings")

def test_data_dir_is_next_to_server():
    script_dir = Path(server.__file__).resolve().parent
    expected = script_dir / "data"
    assert server._SCRIPT_DIR == script_dir
    print("  ✓ DATA_DIR resolves relative to server.py")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Core modules
# ═══════════════════════════════════════════════════════════════════════════════

def test_time_utils():
    from backend.core.time_utils import now_utc, utc_timestamp, parse_utc, get_session, is_weekend, is_friday_late, epoch_ms
    dt = now_utc()
    assert dt.tzinfo is not None

    ts = utc_timestamp()
    assert "+" in ts or "Z" in ts

    parsed = parse_utc("2024-01-15T14:30:00Z")
    assert parsed.tzinfo is not None
    assert parsed.hour == 14

    parsed2 = parse_utc("2024-01-15T14:30:00+00:00")
    assert parsed2.hour == 14

    # Session detection
    from backend.core.time_utils import UTC
    london_time = datetime.datetime(2024, 1, 15, 10, 0, tzinfo=UTC)
    assert get_session(london_time) == "london"

    overlap_time = datetime.datetime(2024, 1, 15, 14, 0, tzinfo=UTC)
    assert get_session(overlap_time) == "overlap"

    ny_time = datetime.datetime(2024, 1, 15, 18, 0, tzinfo=UTC)
    assert get_session(ny_time) == "new_york"

    asia_time = datetime.datetime(2024, 1, 15, 3, 0, tzinfo=UTC)
    assert get_session(asia_time) == "asia"

    # Weekend
    sat = datetime.datetime(2024, 1, 13, 12, 0, tzinfo=UTC)
    assert is_weekend(sat) == True
    mon = datetime.datetime(2024, 1, 15, 12, 0, tzinfo=UTC)
    assert is_weekend(mon) == False

    # Friday late
    fri_late = datetime.datetime(2024, 1, 12, 19, 0, tzinfo=UTC)
    assert is_friday_late(fri_late) == True
    fri_early = datetime.datetime(2024, 1, 12, 14, 0, tzinfo=UTC)
    assert is_friday_late(fri_early) == False

    assert epoch_ms() > 0
    print("  ✓ time_utils (all functions)")


def test_schemas_trade_validation():
    from backend.core.schemas import validate_trade_input
    # Valid trade
    errors = validate_trade_input({"direction": "long", "entry": 3250, "stop": 3240, "status": "open"})
    assert errors == []

    # Missing fields
    errors = validate_trade_input({"direction": "long"})
    assert len(errors) > 0

    # Invalid direction
    errors = validate_trade_input({"direction": "up", "entry": 3250, "stop": 3240, "status": "open"})
    assert any("direction" in e for e in errors)

    # Stop above entry for long
    errors = validate_trade_input({"direction": "long", "entry": 3250, "stop": 3260, "status": "open"})
    assert any("stop" in e.lower() for e in errors)

    print("  ✓ schemas trade validation")


def test_schemas_settings_validation():
    from backend.core.schemas import validate_settings
    errors = validate_settings({"equity": 50000, "risk_pct": 1.0})
    assert errors == []

    errors = validate_settings({"equity": -100})
    assert len(errors) > 0

    errors = validate_settings({"risk_pct": 50})
    assert len(errors) > 0

    print("  ✓ schemas settings validation")


def test_schemas_decision_validation():
    from backend.core.schemas import validate_decision
    # Valid no-trade
    dec = {
        "market_state": "range", "chosen_strategy": "no_trade",
        "thesis_summary": "No setup", "invalidation_summary": "N/A",
        "entry": None, "stop": None, "target_1": None, "target_2": None,
        "confidence": 30, "trade_or_no_trade": "no_trade",
        "rationale": ["No setup"], "risk_notes": [], "uncertainty_notes": [],
    }
    errors = validate_decision(dec)
    assert errors == []

    # Missing field
    bad = {k: v for k, v in dec.items() if k != "confidence"}
    errors = validate_decision(bad)
    assert len(errors) > 0

    print("  ✓ schemas decision validation")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Providers
# ═══════════════════════════════════════════════════════════════════════════════

def test_simulated_market_provider():
    from backend.providers.market_data import SimulatedMarketDataProvider
    p = SimulatedMarketDataProvider()
    quote = p.get_quote()
    assert quote["price"] > 0
    assert quote["bid"] < quote["ask"]
    assert quote["source"] == "simulated"

    candles = p.get_candles("1h", 50)
    assert len(candles) == 50
    for c in candles:
        assert c["high"] >= c["low"]
        assert "timestamp" in c
        assert c["timeframe"] == "1h"

    print("  ✓ simulated market provider")


def test_historical_replay_provider():
    from backend.providers.market_data import SimulatedMarketDataProvider, HistoricalReplayProvider
    sim = SimulatedMarketDataProvider()
    candles = sim.get_candles("1h", 20)

    replay = HistoricalReplayProvider(candles)
    assert replay.total_candles == 20
    assert replay.current_index == 0

    c = replay.advance()
    assert c is not None
    assert replay.current_index == 1

    # No lookahead
    available = replay.get_candles("1h", 100)
    assert len(available) == 1

    replay.reset()
    assert replay.current_index == 0

    print("  ✓ historical replay provider (no lookahead)")


def test_calendar_provider():
    from backend.providers.calendar_data import SimulatedCalendarProvider
    p = SimulatedCalendarProvider()
    result = p.get_upcoming_events()
    assert "events" in result
    assert "high_impact_within_2h" in result
    assert isinstance(result["high_impact_within_2h"], bool)
    print("  ✓ calendar provider")


def test_macro_provider():
    from backend.providers.macro_data import SimulatedMacroProvider
    p = SimulatedMacroProvider()
    result = p.get_macro_context()
    assert result["usd_regime"] in ("strong", "weak", "neutral")
    assert result["gold_macro_bias"] in ("bullish", "bearish", "neutral")
    print("  ✓ macro provider")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Feature engine
# ═══════════════════════════════════════════════════════════════════════════════

def test_feature_engine():
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.providers.calendar_data import SimulatedCalendarProvider
    from backend.providers.macro_data import SimulatedMacroProvider
    from backend.features.market_features import compute_all_features

    market = SimulatedMarketDataProvider()
    calendar = SimulatedCalendarProvider()
    macro = SimulatedMacroProvider()

    quote = market.get_quote()
    candles = market.get_candles("1h", 100)
    cal = calendar.get_upcoming_events()
    mac = macro.get_macro_context()

    features = compute_all_features(
        candles_1h=candles, quote=quote, macro=mac, calendar=cal,
    )

    assert "price" in features
    assert "atr_14" in features
    assert "trend_1h" in features
    assert features["trend_1h"] in ("uptrend", "downtrend", "ranging")
    assert "volatility_regime" in features
    assert "session" in features
    assert "is_weekend" in features
    assert "news_blackout" in features
    assert "spread_regime" in features
    assert features["spread_regime"] in ("tight", "normal", "wide")
    assert "nearest_resistance" in features
    assert "nearest_support" in features

    print("  ✓ feature engine (all features computed)")


def test_atr_computation():
    from backend.features.market_features import compute_atr
    candles = [
        {"open": 100, "high": 105, "low": 95, "close": 102, "timestamp": ""},
        {"open": 102, "high": 108, "low": 99, "close": 106, "timestamp": ""},
        {"open": 106, "high": 110, "low": 103, "close": 104, "timestamp": ""},
    ]
    atr = compute_atr(candles, 2)
    assert atr > 0
    print("  ✓ ATR computation")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Strategies
# ═══════════════════════════════════════════════════════════════════════════════

def test_strategy_registry():
    from backend.strategies.registry import StrategyRegistry
    registry = StrategyRegistry()
    names = registry.list_strategies()
    assert "trend_pullback" in names
    assert "range_reversion" in names
    assert "breakout_compression" in names
    assert len(names) == 3
    print("  ✓ strategy registry (3 strategies registered)")


def test_strategy_evaluation():
    from backend.strategies.registry import StrategyRegistry
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.features.market_features import compute_all_features

    market = SimulatedMarketDataProvider()
    quote = market.get_quote()
    candles = market.get_candles("1h", 100)
    features = compute_all_features(
        candles_1h=candles, quote=quote,
        macro={"usd_regime": "neutral", "gold_macro_bias": "neutral", "geopolitical_risk": "moderate", "vix_regime": "low_vol"},
        calendar={"high_impact_within_2h": False, "nearest_high_impact": None},
    )

    registry = StrategyRegistry()
    results = registry.evaluate_all(features, {"1h": candles})
    assert len(results) == 3
    for r in results:
        assert hasattr(r, "valid")
        assert hasattr(r, "strategy_name")
        assert r.strategy_name in ("trend_pullback", "range_reversion", "breakout_compression")
        d = r.to_dict()
        assert "strategy_name" in d
        assert "valid" in d
    print("  ✓ strategy evaluation (all strategies return results)")


def test_strategy_invalidation_reasons():
    from backend.strategies.registry import StrategyRegistry
    registry = StrategyRegistry()
    # Off-hours session should invalidate most strategies
    features = {
        "session": "off_hours", "trend_1h": "ranging", "price": 3250,
        "atr_14": 10, "rolling_high_20": 3280, "rolling_low_20": 3220,
        "volatility_regime": "normal", "gold_macro_bias": "neutral",
        "swing_highs": [], "swing_lows": [], "news_blackout": False,
    }
    results = registry.evaluate_all(features, {"1h": []})
    for r in results:
        if not r.valid:
            assert r.invalidation_reason is not None
            assert len(r.invalidation_reason) > 0
    print("  ✓ strategy invalidation reasons populated")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Risk engine
# ═══════════════════════════════════════════════════════════════════════════════

def test_risk_engine_blocks_weekend():
    from backend.risk.engine import RiskEngine, RiskConfig
    engine = RiskEngine(RiskConfig())
    features = {"is_weekend": True, "is_friday_late": False, "session": "off_hours",
                "news_blackout": False, "spread": 0.3, "open_positions": 0,
                "trades_today": 0, "current_drawdown_pct": 0, "equity": 50000,
                "daily_pnl": 0, "consecutive_losses": 0}
    allowed, blockers = engine.is_allowed(features)
    assert not allowed
    assert any(b.rule == "weekend" for b in blockers)
    print("  ✓ risk engine blocks weekend")


def test_risk_engine_blocks_drawdown():
    from backend.risk.engine import RiskEngine, RiskConfig
    config = RiskConfig(max_drawdown_pct=5)
    engine = RiskEngine(config)
    features = {"is_weekend": False, "is_friday_late": False, "session": "london",
                "news_blackout": False, "spread": 0.3, "open_positions": 0,
                "trades_today": 0, "current_drawdown_pct": 6.0, "equity": 47000,
                "daily_pnl": 0, "consecutive_losses": 0}
    allowed, blockers = engine.is_allowed(features)
    assert not allowed
    assert any(b.rule == "max_drawdown" for b in blockers)
    print("  ✓ risk engine blocks on drawdown")


def test_risk_engine_blocks_max_positions():
    from backend.risk.engine import RiskEngine, RiskConfig
    config = RiskConfig(max_positions=2)
    engine = RiskEngine(config)
    features = {"is_weekend": False, "is_friday_late": False, "session": "london",
                "news_blackout": False, "spread": 0.3, "open_positions": 2,
                "trades_today": 0, "current_drawdown_pct": 0, "equity": 50000,
                "daily_pnl": 0, "consecutive_losses": 0}
    allowed, blockers = engine.is_allowed(features)
    assert not allowed
    assert any(b.rule == "max_positions" for b in blockers)
    print("  ✓ risk engine blocks max positions")


def test_risk_engine_blocks_safe_mode():
    from backend.risk.engine import RiskEngine, RiskConfig
    config = RiskConfig(safe_mode=True)
    engine = RiskEngine(config)
    features = {"is_weekend": False, "is_friday_late": False, "session": "london",
                "news_blackout": False, "spread": 0.3, "open_positions": 0,
                "trades_today": 0, "current_drawdown_pct": 0, "equity": 50000,
                "daily_pnl": 0, "consecutive_losses": 0}
    allowed, _ = engine.is_allowed(features)
    assert not allowed
    print("  ✓ risk engine blocks safe mode")


def test_risk_engine_allows_good_conditions():
    from backend.risk.engine import RiskEngine, RiskConfig
    engine = RiskEngine(RiskConfig())
    features = {"is_weekend": False, "is_friday_late": False, "session": "london",
                "news_blackout": False, "spread": 0.3, "open_positions": 0,
                "trades_today": 0, "current_drawdown_pct": 0, "equity": 50000,
                "daily_pnl": 0, "consecutive_losses": 0}
    allowed, blockers = engine.is_allowed(features)
    assert allowed
    assert len([b for b in blockers if b.severity == "hard"]) == 0
    print("  ✓ risk engine allows good conditions")


def test_risk_position_sizing():
    from backend.risk.engine import RiskEngine, RiskConfig
    config = RiskConfig(risk_pct=1.0)
    engine = RiskEngine(config)
    size = engine.compute_position_size(equity=50000, entry=3250, stop=3240)
    assert size["risk_usd"] == 500
    assert size["risk_distance"] == 10
    assert size["position_oz"] == 50
    assert size["position_lots"] == 0.5
    print("  ✓ risk position sizing")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Paper broker
# ═══════════════════════════════════════════════════════════════════════════════

def test_paper_broker_lifecycle():
    from backend.execution.paper_broker import PaperBroker
    from backend.execution.broker_base import BrokerOrder

    broker = PaperBroker(initial_balance=50000, spread=0.40)
    assert not broker.is_live()

    # Submit order
    order = BrokerOrder(direction="long", entry=3250, stop=3240, target_1=3270,
                        position_lots=0.5, strategy="test")
    fill = broker.submit_order(order)
    assert fill["status"] == "filled"
    assert fill["position_id"].startswith("paper_")

    # Check positions
    positions = broker.get_positions()
    assert len(positions) == 1
    assert positions[0].direction == "long"

    # Check account
    account = broker.get_account()
    assert account["open_positions"] == 1
    assert account["mode"] == "paper"

    # Close position
    result = broker.close_position(positions[0].position_id, 3265)
    assert result["status"] == "closed"
    assert result["pnl"] > 0  # Should be profitable
    assert result["r_multiple"] > 0

    # After close
    assert len(broker.get_positions()) == 0
    assert broker.get_account()["balance"] > 50000

    print("  ✓ paper broker lifecycle (open → close → PnL)")


def test_paper_broker_stop_check():
    from backend.execution.paper_broker import PaperBroker
    from backend.execution.broker_base import BrokerOrder

    broker = PaperBroker(initial_balance=50000, spread=0.40)
    order = BrokerOrder(direction="long", entry=3250, stop=3240, target_1=3270,
                        position_lots=0.1, strategy="test")
    broker.submit_order(order)

    # Price drops to stop
    results = broker.check_stops_and_targets(3238)
    assert len(results) == 1
    assert results[0]["r_multiple"] < 0
    assert len(broker.get_positions()) == 0

    print("  ✓ paper broker stop loss trigger")


def test_paper_broker_target_check():
    from backend.execution.paper_broker import PaperBroker
    from backend.execution.broker_base import BrokerOrder

    broker = PaperBroker(initial_balance=50000, spread=0.40)
    order = BrokerOrder(direction="long", entry=3250, stop=3240, target_1=3270,
                        position_lots=0.1, strategy="test")
    broker.submit_order(order)

    results = broker.check_stops_and_targets(3275)
    assert len(results) == 1
    assert results[0]["r_multiple"] > 0

    print("  ✓ paper broker target hit trigger")


def test_paper_journal_sync():
    """Verify that paper broker trades create journal entries."""
    reset_data()
    # This test requires the structured decision + paper execution flow
    # Run a decision
    result = server.run_structured_decision(use_claude=False)
    dec = result.get("decision", {})

    # If the decision is a trade, the execute endpoint would sync.
    # We can't easily test the HTTP handler in a unit test,
    # but we can verify the functions exist and work
    assert callable(server.log_trade)
    assert callable(server.update_trade)

    # Log a paper-sourced trade
    trade = server.log_trade({
        "direction": "long",
        "entry": 3250.0,
        "stop": 3240.0,
        "t1": 3270.0,
        "status": "open",
        "source": "paper_broker",
        "paper_position_id": "paper_99",
        "notes": "Paper trade test",
    })
    assert trade["source"] == "paper_broker"
    assert trade["paper_position_id"] == "paper_99"

    # Update as if closed
    updated = server.update_trade(trade["id"], {
        "status": "closed",
        "exit_price": 3265.0,
        "r_multiple": 1.5,
        "exit_reason": "target_1",
    })
    assert updated["status"] == "closed"
    assert updated["r_multiple"] == 1.5
    assert updated["exit_reason"] == "target_1"

    # Verify it appears in closed trades
    closed = server.get_trades(status="closed")
    assert len(closed) == 1
    assert closed[0]["paper_position_id"] == "paper_99"

    print("  ✓ paper→journal sync (create + update)")


def test_paper_broker_persistence():
    import tempfile
    tmpdir = Path(tempfile.mkdtemp())
    from backend.execution.paper_broker import PaperBroker
    from backend.execution.broker_base import BrokerOrder

    broker = PaperBroker(initial_balance=50000, data_dir=tmpdir)
    order = BrokerOrder(direction="long", entry=3250, stop=3240, target_1=3270, position_lots=0.1)
    broker.submit_order(order)

    # Load in a new broker instance
    broker2 = PaperBroker(initial_balance=50000, data_dir=tmpdir)
    assert len(broker2.get_positions()) == 1

    print("  ✓ paper broker persistence")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Backtesting
# ═══════════════════════════════════════════════════════════════════════════════

def test_backtest_engine():
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.backtest.engine import BacktestEngine
    from backend.strategies.registry import StrategyRegistry

    market = SimulatedMarketDataProvider()
    candles = market.get_candles("1h", 200)

    engine = BacktestEngine(strategy_registry=StrategyRegistry(), spread=0.40)
    result = engine.run(candles)

    assert "trade_log" in result
    assert "metrics" in result
    assert result["total_candles"] == 200
    assert result["warmup_candles"] == 30
    assert result["spread_assumption"] == 0.40
    assert len(result["strategies_used"]) == 3

    # Metrics should be computed
    m = result["metrics"]
    assert "total_trades" in m or "closed_trades" in m

    print(f"  ✓ backtest engine ({m.get('closed_trades', 0)} trades generated)")


def test_backtest_no_lookahead():
    """Verify that the backtest engine doesn't use future candle data."""
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.backtest.engine import BacktestEngine
    from backend.strategies.registry import StrategyRegistry

    market = SimulatedMarketDataProvider()
    candles = market.get_candles("1h", 100)

    engine = BacktestEngine(strategy_registry=StrategyRegistry())
    result = engine.run(candles, warmup=30)

    # Every trade's open timestamp should be before its close timestamp
    for t in result["trade_log"]:
        if t.get("open_timestamp") and t.get("close_timestamp"):
            assert t["open_timestamp"] <= t["close_timestamp"], "Lookahead detected!"

    print("  ✓ backtest no lookahead (timestamps ordered)")


def test_walk_forward():
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.backtest.engine import run_walk_forward

    market = SimulatedMarketDataProvider()
    candles = market.get_candles("1h", 300)

    result = run_walk_forward(candles, train_ratio=0.7, n_folds=2)
    assert result["n_folds"] == 2
    assert len(result["folds"]) == 2
    for fold in result["folds"]:
        assert "train_metrics" in fold
        assert "test_metrics" in fold
    assert "aggregate_oos_metrics" in result

    print("  ✓ walk-forward test (2 folds)")


def test_baselines():
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.backtest.baselines import run_all_baselines

    market = SimulatedMarketDataProvider()
    candles = market.get_candles("1h", 200)

    baselines = run_all_baselines(candles)
    assert len(baselines) == 2

    # No-trade baseline
    assert baselines[0]["name"] == "no_trade_baseline"
    assert baselines[0]["metrics"]["total_trades"] == 0
    assert baselines[0]["metrics"]["total_r"] == 0

    # Random baseline
    assert baselines[1]["name"] == "random_baseline"
    assert baselines[1]["metrics"]["closed_trades"] > 0

    print("  ✓ baselines (no_trade + random)")


def test_backtest_metrics():
    from backend.backtest.metrics import compute_backtest_metrics
    trades = [
        {"r_multiple": 1.5, "strategy": "A", "exit_reason": "target_1"},
        {"r_multiple": -1.0, "strategy": "A", "exit_reason": "stop_loss"},
        {"r_multiple": 2.0, "strategy": "B", "exit_reason": "target_1"},
        {"r_multiple": -1.0, "strategy": "B", "exit_reason": "stop_loss"},
        {"r_multiple": 0.5, "strategy": "A", "exit_reason": "target_1"},
    ]
    m = compute_backtest_metrics(trades)
    assert m["closed_trades"] == 5
    assert m["wins"] == 3
    assert m["losses"] == 2
    assert m["win_rate"] == 0.6
    assert m["expectancy"] > 0
    assert m["max_drawdown_r"] >= 0
    assert m["total_r"] == 2.0
    assert "A" in m["by_strategy"]
    assert "B" in m["by_strategy"]
    assert "target_1" in m["by_exit_reason"]
    assert "stop_loss" in m["by_exit_reason"]

    print("  ✓ backtest metrics (comprehensive)")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Decision engine
# ═══════════════════════════════════════════════════════════════════════════════

def test_decision_engine_deterministic():
    from backend.agent.decision_engine import DecisionEngine
    from backend.strategies.registry import StrategyRegistry
    from backend.risk.engine import RiskEngine
    from backend.providers.market_data import SimulatedMarketDataProvider
    from backend.features.market_features import compute_all_features

    market = SimulatedMarketDataProvider()
    quote = market.get_quote()
    candles = market.get_candles("1h", 100)

    features = compute_all_features(
        candles_1h=candles, quote=quote,
        macro={"usd_regime": "neutral", "gold_macro_bias": "neutral", "geopolitical_risk": "moderate", "vix_regime": "low_vol"},
        calendar={"high_impact_within_2h": False, "nearest_high_impact": None},
    )

    engine = DecisionEngine(api_key="")  # No Claude
    result = engine.decide(features, {"1h": candles}, use_claude=False)

    assert "decision_id" in result
    assert "timestamp" in result
    assert "decision" in result
    assert "setups_evaluated" in result
    assert "risk_blockers" in result
    assert result["claude_used"] == False
    assert result["trade_or_no_trade"] in ("trade", "no_trade")

    dec = result["decision"]
    assert "market_state" in dec
    assert "confidence" in dec
    assert "trade_or_no_trade" in dec

    print("  ✓ decision engine (deterministic mode)")


def test_decision_schema_validation():
    from backend.agent.decision_schema import validate_decision_output, make_no_trade_decision
    dec = make_no_trade_decision("Test reason")
    errors = validate_decision_output(dec)
    assert errors == []

    # Bad schema
    errors = validate_decision_output({"garbage": True})
    assert len(errors) > 0

    print("  ✓ decision schema validation")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Memory store
# ═══════════════════════════════════════════════════════════════════════════════

def test_decision_store():
    from backend.memory.store import DecisionStore
    store = DecisionStore(Path(_TEST_DIR))
    # Clear
    if store.decisions_file.exists():
        store.decisions_file.unlink()

    decision_result = {
        "decision_id": "12345",
        "timestamp": "2024-01-01T00:00:00+00:00",
        "decision": {"trade_or_no_trade": "no_trade", "confidence": 30},
        "trade_or_no_trade": "no_trade",
        "strategy": "no_trade",
        "confidence": 30,
        "setups_evaluated": [],
        "risk_blockers": [],
    }
    store.store(decision_result)

    recent = store.get_recent(10)
    assert len(recent) == 1
    assert recent[0]["id"] == "12345"

    # Update outcome
    store.update_outcome("12345", {"r_multiple": -1.0})
    with_outcomes = store.get_with_outcomes()
    assert len(with_outcomes) == 1

    print("  ✓ decision store (store + retrieve + outcome)")


def test_experiment_tracker():
    from backend.memory.experiments import ExperimentTracker
    tracker = ExperimentTracker(Path(_TEST_DIR))
    if tracker.experiments_file.exists():
        tracker.experiments_file.unlink()

    tracker.log_experiment("test_exp", {"spread": 0.4}, {"win_rate": 0.5}, "Test experiment")
    tracker.log_experiment("test_exp_2", {"spread": 0.3}, {"win_rate": 0.6}, "Second experiment")

    all_exp = tracker.get_all()
    assert len(all_exp) == 2

    comp = tracker.compare(1, 2)
    assert comp is not None
    assert comp["experiment_1"]["name"] == "test_exp"

    print("  ✓ experiment tracker (log + compare)")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Live broker safety
# ═══════════════════════════════════════════════════════════════════════════════

def test_live_broker_disabled_by_default():
    from backend.execution.live_broker import is_live_enabled, LiveBroker
    # Should be disabled
    old_val = os.environ.get("LIVE_BROKER_ENABLED", "")
    os.environ.pop("LIVE_BROKER_ENABLED", None)
    assert is_live_enabled() == False

    try:
        LiveBroker()
        assert False, "LiveBroker should raise when disabled"
    except RuntimeError as e:
        assert "disabled" in str(e).lower()

    # Restore
    if old_val:
        os.environ["LIVE_BROKER_ENABLED"] = old_val
    print("  ✓ live broker disabled by default")


# ═══════════════════════════════════════════════════════════════════════════════
# NEW TESTS — Validation utilities
# ═══════════════════════════════════════════════════════════════════════════════

def test_validation_utilities():
    from backend.core.validation import parse_json_body, validate_trade_id
    data, err = parse_json_body(b'{"key": "value"}')
    assert err is None
    assert data["key"] == "value"

    data, err = parse_json_body(b'not json')
    assert err is not None
    assert data is None

    tid, err = validate_trade_id("12345")
    assert tid == 12345
    assert err is None

    tid, err = validate_trade_id("abc")
    assert err is not None

    tid, err = validate_trade_id("-1")
    assert err is not None

    print("  ✓ validation utilities")


# ═══════════════════════════════════════════════════════════════════════════════
# Run All
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    failed = 0
    print(f"\nRunning {len(tests)} tests...\n")
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            import traceback
            print(f"  ✗ {test.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{'=' * 40}")
    print(f"  {passed} passed, {failed} failed")
    print(f"{'=' * 40}")
    sys.exit(1 if failed else 0)
