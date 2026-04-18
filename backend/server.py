"""
Gold Market Intelligence System — Backend Server v4.0 (Phase 3).

Local research, paper-trading, and (after supervised validation) live-trading
candidate platform.

Real integrations (OANDA market data, OANDA live broker, FRED macro) are
implemented in code and mock-tested but have NOT been validated against live
external services in this build. Default posture is still simulated data +
paper trading; real-money live execution is blocked by default and requires
explicit operator acknowledgement after a supervised practice-account run.

Integrates: providers, features, strategies, risk, execution, decisioning,
backtesting.
"""

import os
import sys
import json
import traceback
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─── Path setup ──────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ─── Configuration ──────────────────────────────────────────────────────────────

PORT = int(os.environ.get("PORT", 8888))
BIND_HOST = os.environ.get("BIND_HOST", "127.0.0.1")
DATA_DIR = Path(os.environ.get("DATA_DIR", str(_SCRIPT_DIR / "data")))
DATA_DIR.mkdir(parents=True, exist_ok=True)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-sonnet-4-20250514"

API_AUTH_TOKEN = os.environ.get("API_AUTH_TOKEN", "")
CORS_ALLOWED_ORIGINS = os.environ.get("CORS_ALLOWED_ORIGINS", "")
DATA_PROVIDER = os.environ.get("DATA_PROVIDER", "simulated")

# ─── Core imports ───────────────────────────────────────────────────────────────

from backend.core.time_utils import now_utc, utc_timestamp, epoch_ms, get_session, is_weekend, is_friday_late
from backend.core.schemas import validate_trade_input, validate_settings
from backend.core.validation import parse_json_body, validate_trade_id
from backend.core import auth as auth_module

from backend.providers.market_data import SimulatedMarketDataProvider
from backend.providers.calendar_data import SimulatedCalendarProvider
from backend.providers.macro_data import SimulatedMacroProvider
from backend.providers.factory import (
    get_market_provider,
    describe_configured_provider,
    ProviderConfigError,
    KIND_SIMULATED,
)
from backend.providers import historical_data as historical_import
from backend.features.market_features import compute_all_features
from backend.strategies.registry import StrategyRegistry
from backend.risk.engine import RiskEngine, RiskConfig
from backend.execution.paper_broker import PaperBroker
from backend.execution.live_broker import (
    is_live_enabled,
    get_live_broker_status,
    selected_live_broker,
    broker_environment,
    is_cutover_acknowledged,
)
from backend.execution.live_readiness import evaluate_live_readiness
from backend.agent.decision_engine import DecisionEngine
from backend.agent.decision_schema import make_no_trade_decision
from backend.memory.store import DecisionStore
from backend.memory.experiments import ExperimentTracker
from backend.backtest.engine import BacktestEngine, run_walk_forward
from backend.backtest.baselines import run_all_baselines

# ─── Persistent Storage ────────────────────────────────────────────────────────

TRADES_FILE = DATA_DIR / "trades.json"
METRICS_FILE = DATA_DIR / "metrics.json"
ANALYSIS_LOG = DATA_DIR / "analysis_log.json"
SETTINGS_FILE = DATA_DIR / "settings.json"


def load_json(path, default=None):
    if default is None:
        default = []
    try:
        if path.exists():
            return json.loads(path.read_text())
    except Exception:
        pass
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, default=str))


# ─── Settings ───────────────────────────────────────────────────────────────────

DEFAULT_SETTINGS = {
    "equity": 50000,
    "risk_pct": 1.0,
    "max_positions": 2,
    "peak_equity": 50000,
    "max_daily_loss_pct": 3.0,
    "max_drawdown_pct": 5.0,
    "max_trades_per_day": 5,
    "friday_cutoff_hour": 18,
    "cooloff_after_losses": 3,
    "max_spread": 0.60,
    "min_risk_reward": 1.5,
    "min_confidence": 50,
    "safe_mode": False,
    "system_mode": "paper_trading",
}


def load_settings():
    stored = load_json(SETTINGS_FILE, {})
    return {**DEFAULT_SETTINGS, **stored}


def save_settings(settings):
    save_json(SETTINGS_FILE, settings)


# ─── Initialize components ─────────────────────────────────────────────────────

# Market provider is built via the factory so DATA_PROVIDER env selects
# between simulated / oanda / etc. If a real provider is requested but its
# config is missing, we fall back to simulated *for research/paper only* and
# record the reason. Live execution still blocks via live-readiness gating
# (it never trusts a simulated provider).
_PROVIDER_FALLBACK_REASON = None


def _build_market_provider():
    global _PROVIDER_FALLBACK_REASON
    try:
        provider = get_market_provider()
        _PROVIDER_FALLBACK_REASON = None
        return provider
    except ProviderConfigError as e:
        _PROVIDER_FALLBACK_REASON = str(e)
        # Fail safe to simulated -- research/paper continues, live still blocks.
        from backend.providers.factory import StatusSimulatedMarketDataProvider
        return StatusSimulatedMarketDataProvider()


market_provider = _build_market_provider()


def _build_macro_provider():
    """Build macro provider honoring MACRO_PROVIDER env; never silently falls
    back from 'fred' to simulated -- if FRED is misconfigured the provider is
    constructed but get_macro_context() will raise, which the caller surfaces.
    """
    try:
        from backend.providers.fred_macro import get_macro_provider
        return get_macro_provider()
    except Exception:
        # Module import failure should never silently mask -- but if it does,
        # fall back to simulated and let /api/health show the reason below.
        return SimulatedMacroProvider()


def _build_calendar_provider():
    try:
        from backend.providers.calendar_file import get_calendar_provider
        return get_calendar_provider()
    except Exception:
        return SimulatedCalendarProvider()


calendar_provider = _build_calendar_provider()
macro_provider = _build_macro_provider()
strategy_registry = StrategyRegistry()
decision_store = DecisionStore(DATA_DIR)
experiment_tracker = ExperimentTracker(DATA_DIR)


def _reinitialize_data_dir(new_dir):
    """Reinitialize all DATA_DIR-dependent globals.

    Used by test harnesses to ensure proper isolation when multiple test
    files run in the same process (e.g. ``pytest test_server.py test_http.py``).
    """
    global DATA_DIR, TRADES_FILE, METRICS_FILE, ANALYSIS_LOG, SETTINGS_FILE
    global decision_store, experiment_tracker
    DATA_DIR = Path(new_dir)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TRADES_FILE = DATA_DIR / "trades.json"
    METRICS_FILE = DATA_DIR / "metrics.json"
    ANALYSIS_LOG = DATA_DIR / "analysis_log.json"
    SETTINGS_FILE = DATA_DIR / "settings.json"
    decision_store = DecisionStore(DATA_DIR)
    experiment_tracker = ExperimentTracker(DATA_DIR)


def get_paper_broker():
    """Get or create the paper broker with current settings."""
    settings = load_settings()
    return PaperBroker(
        initial_balance=settings.get("equity", 50000),
        spread=0.40,
        data_dir=DATA_DIR,
    )


def get_provider_status():
    """Status of the active market provider (source, freshness, ready)."""
    try:
        status = market_provider.get_status()
    except Exception as e:
        status = {
            "name": "unknown", "kind": "unknown", "is_real": False,
            "ready": False, "last_quote_age_seconds": None,
            "reason": f"status query failed: {e}",
        }
    if _PROVIDER_FALLBACK_REASON:
        status["fallback_reason"] = _PROVIDER_FALLBACK_REASON
        status["selected_provider"] = os.environ.get("DATA_PROVIDER", KIND_SIMULATED)
    return status


def get_live_readiness():
    """Compute live-readiness from provider, broker, settings, and risk."""
    settings = load_settings()
    provider_status = get_provider_status()
    broker_status = get_live_broker_status()

    # Best-effort risk snapshot. If feature computation fails we still want a
    # readiness answer (with a "could not evaluate risk" note rather than 500).
    risk_blockers = []
    try:
        quote = market_provider.get_quote()
        candles_1h = market_provider.get_candles("1h", 100)
        macro = macro_provider.get_macro_context()
        calendar = calendar_provider.get_upcoming_events()
        broker = get_paper_broker()
        features = compute_all_features(
            candles_1h=candles_1h, quote=quote, macro=macro,
            calendar=calendar, account_state=broker.get_account_features(),
        )
        engine = get_risk_engine()
        risk_blockers = [b.to_dict() for b in engine.evaluate(features)]
    except Exception as e:
        risk_blockers = [{
            "rule": "risk_eval_error",
            "reason": f"could not evaluate risk: {e}",
            "severity": "hard",
        }]

    report = evaluate_live_readiness(
        live_enabled=is_live_enabled(),
        provider_status=provider_status,
        broker_status=broker_status,
        settings=settings,
        risk_blockers=risk_blockers,
        stale_data_seconds=int(settings.get("stale_data_seconds", 300)),
        broker_environment=broker_environment(),
        cutover_acknowledged=is_cutover_acknowledged(),
    )
    return {
        "report": report.to_dict(),
        "provider_status": provider_status,
        "broker_status": broker_status,
        "risk_blockers": risk_blockers,
    }


def get_risk_engine():
    """Get risk engine with current settings."""
    settings = load_settings()
    config = RiskConfig.from_settings(settings)
    return RiskEngine(config)


def get_decision_engine():
    """Get decision engine with current config."""
    return DecisionEngine(
        strategy_registry=strategy_registry,
        risk_engine=get_risk_engine(),
        api_key=ANTHROPIC_API_KEY,
        model=CLAUDE_MODEL,
    )


# ─── Legacy compatibility functions ────────────────────────────────────────────
# These maintain backward compat with existing tests while using new providers

def get_market_price():
    return market_provider.get_quote()


def get_macro_context():
    return macro_provider.get_macro_context()


def get_economic_calendar():
    return calendar_provider.get_upcoming_events()


def preprocess_market_structure(price_data):
    """Legacy market structure — now wraps feature engine."""
    price = price_data.get("price", 0)
    macro = get_macro_context()
    calendar = get_economic_calendar()

    price_round_100 = round(price / 100) * 100
    price_round_50 = round(price / 50) * 50
    major_resistance = sorted(set([
        price_round_100 + 100, price_round_100 + 200,
        price_round_50 + 50 if price_round_50 + 50 > price else price_round_50 + 100,
    ]))
    major_support = sorted(set([
        price_round_100 - 100, price_round_100 - 200,
        price_round_50 - 50 if price_round_50 - 50 < price else price_round_50 - 100,
    ]), reverse=True)
    psychological = sorted(set([price_round_100 - 50, price_round_100, price_round_100 + 50]))
    key_levels = {"major_resistance": major_resistance, "major_support": major_support, "psychological": psychological}
    all_levels = key_levels["major_resistance"] + key_levels["major_support"]
    nearest = sorted(all_levels, key=lambda l: abs(l - price))[:4]
    above_levels = [l for l in all_levels if price > l]
    below_levels = [l for l in all_levels if price < l]

    now = now_utc()
    session = get_session(now)

    return {
        "current_price": price,
        "spread": price_data.get("spread", 0),
        "session": session,
        "key_levels": key_levels,
        "nearest_levels": nearest,
        "price_above_supports": len(above_levels),
        "price_below_resistances": len(below_levels),
        "macro": macro,
        "calendar": calendar,
        "timestamp": price_data.get("timestamp"),
    }


# ─── Trade Storage ──────────────────────────────────────────────────────────────

def log_trade(trade):
    trades = load_json(TRADES_FILE, [])
    trade["id"] = trade.get("id", epoch_ms())
    trade["logged_at"] = utc_timestamp()
    trades.append(trade)
    save_json(TRADES_FILE, trades)
    return trade


def update_trade(trade_id, updates):
    trades = load_json(TRADES_FILE, [])
    for i, t in enumerate(trades):
        if t.get("id") == trade_id:
            trades[i] = {**t, **updates, "updated_at": utc_timestamp()}
            save_json(TRADES_FILE, trades)
            return trades[i]
    return None


def get_trades(status=None):
    trades = load_json(TRADES_FILE, [])
    if status:
        trades = [t for t in trades if t.get("status") == status]
    return trades


def delete_trade(trade_id):
    trades = load_json(TRADES_FILE, [])
    trades = [t for t in trades if t.get("id") != trade_id]
    save_json(TRADES_FILE, trades)
    return True


# ─── Analytics Engine ───────────────────────────────────────────────────────────

def compute_metrics():
    trades = get_trades(status="closed")
    r_multiples = [t["r_multiple"] for t in trades if t.get("r_multiple") is not None]

    if not r_multiples:
        return {
            "total_trades": len(get_trades()),
            "closed_trades": 0,
            "open_trades": len(get_trades(status="open")),
            "metrics": None,
            "message": "No closed trades with R-multiples yet"
        }

    n = len(r_multiples)
    wins = [r for r in r_multiples if r > 0]
    losses = [r for r in r_multiples if r <= 0]

    win_rate = len(wins) / n if n else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0
    ev = win_rate * avg_win - (1 - win_rate) * avg_loss
    avg_r = sum(r_multiples) / n

    curve = [0]
    cum = 0
    for r in r_multiples:
        cum += r
        curve.append(round(cum, 2))

    peak = 0
    max_dd = 0
    for val in curve:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0)

    mean = avg_r
    variance = sum((r - mean) ** 2 for r in r_multiples) / n if n > 1 else 0
    std = variance ** 0.5
    sharpe = ev / std if std > 0 else 0

    max_streak = 0
    current_streak = 0
    for r in r_multiples:
        if r <= 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    phase = 1 if n < 50 else (2 if n < 150 else 3)
    se = (win_rate * (1 - win_rate) / n) ** 0.5 if n > 0 else 0
    ci_low = max(0, win_rate - 1.96 * se)
    ci_high = min(1, win_rate + 1.96 * se)
    ev_at_ci_low = ci_low * avg_win - (1 - ci_low) * avg_loss

    if phase >= 3:
        if ev > 0.20 and ev_at_ci_low > 0 and pf > 1.3:
            edge_status = "EDGE VALIDATED"
        elif ev > 0 and ev_at_ci_low > -0.3:
            edge_status = "Preliminary positive"
        else:
            edge_status = "EDGE NOT CONFIRMED"
    elif phase == 2:
        edge_status = "On track" if ev > 0 else "Warning"
    else:
        edge_status = "Collecting data"

    metrics = {
        "total_trades": len(get_trades()),
        "closed_trades": n,
        "open_trades": len(get_trades(status="open")),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "avg_win_r": round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "expectancy": round(ev, 4),
        "ev_at_ci_low": round(ev_at_ci_low, 4),
        "avg_r": round(avg_r, 4),
        "profit_factor": round(pf, 2) if pf != float('inf') else "Infinity",
        "sharpe": round(sharpe, 2),
        "std_dev": round(std, 4),
        "max_drawdown_r": round(max_dd, 2),
        "max_losing_streak": max_streak,
        "equity_curve": curve,
        "r_multiples": r_multiples,
        "phase": phase,
        "edge_status": edge_status,
    }

    save_json(METRICS_FILE, {**metrics, "computed_at": utc_timestamp()})
    return metrics


# ─── Tool execution (legacy Claude tool-calling compat) ────────────────────────

CLAUDE_TOOLS = [
    {"name": "get_market_price", "description": "Get current XAU/USD price with bid/ask/spread.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_macro_context", "description": "Get macroeconomic context for gold analysis.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_economic_calendar", "description": "Get upcoming economic events.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_market_structure", "description": "Get preprocessed market structure.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "get_trade_history", "description": "Get past trade records.",
     "input_schema": {"type": "object", "properties": {"status": {"type": "string", "enum": ["all", "open", "closed"]}, "limit": {"type": "integer"}}, "required": []}},
    {"name": "get_performance_metrics", "description": "Get performance analytics.",
     "input_schema": {"type": "object", "properties": {}, "required": []}},
    {"name": "log_analysis", "description": "Log a market analysis for review.",
     "input_schema": {"type": "object", "properties": {"analysis_type": {"type": "string"}, "market_state": {"type": "string"}, "decision": {"type": "string"}, "confidence": {"type": "integer"}, "key_factors": {"type": "array", "items": {"type": "string"}}}, "required": ["analysis_type", "decision", "confidence"]}},
]


def execute_tool(tool_name, tool_input):
    if tool_name == "get_market_price":
        return get_market_price()
    elif tool_name == "get_macro_context":
        return get_macro_context()
    elif tool_name == "get_economic_calendar":
        return get_economic_calendar()
    elif tool_name == "get_market_structure":
        price_data = get_market_price()
        return preprocess_market_structure(price_data)
    elif tool_name == "get_trade_history":
        status = tool_input.get("status", "all")
        limit = tool_input.get("limit", 20)
        trades = get_trades(status if status != "all" else None)
        return {"trades": trades[-limit:], "total": len(trades)}
    elif tool_name == "get_performance_metrics":
        return compute_metrics()
    elif tool_name == "log_analysis":
        log = load_json(ANALYSIS_LOG, [])
        entry = {**tool_input, "id": epoch_ms(), "timestamp": utc_timestamp()}
        log.append(entry)
        save_json(ANALYSIS_LOG, log)
        return {"status": "logged", "id": entry["id"]}
    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ─── System prompt builder ──────────────────────────────────────────────────────

def build_system_prompt():
    settings = load_settings()
    max_pos = settings.get("max_positions", 2)
    equity = settings.get("equity", 50000)
    risk_pct = settings.get("risk_pct", 1.0)

    return f"""You are the Gold Market Intelligence System v4 — a structured, probabilistic trading decision engine for XAU/USD.

## Current Account Settings
- Equity: ${equity:,.0f}
- Risk per trade: {risk_pct}%
- Max open positions: {max_pos}

## Analysis Framework
1. Call tools for data: get_market_price, get_macro_context, get_economic_calendar, get_market_structure, get_performance_metrics
2. Classify market state
3. Apply no-trade filters
4. Score confidence (0-100)
5. Output structured decision
6. Log via log_analysis tool

## Hard Rules
- R:R >= 1.5:1, NO TRADE is default
- Never assume prices — always fetch via tools
- Log every analysis
- This is an ANALYSIS system — it does not execute orders"""


# ─── Analysis (legacy + new structured) ─────────────────────────────────────────

def run_demo_analysis():
    """Rule-based analysis for demo mode — preserved from v3."""
    price_data = get_market_price()
    structure = preprocess_market_structure(price_data)
    metrics = compute_metrics()
    calendar = get_economic_calendar()

    price = price_data["price"]
    macro = structure["macro"]
    nearest = structure["nearest_levels"]
    session = structure["session"]
    news_block = calendar["high_impact_within_2h"]
    spread_ok = price_data["spread"] <= 0.50

    open_trades = len(get_trades(status="open"))
    settings = load_settings()
    max_pos = settings.get("max_positions", 2)

    equity = settings.get("equity", 50000)
    peak = settings.get("peak_equity", equity)
    drawdown_pct = ((peak - equity) / peak * 100) if peak > 0 else 0

    now = now_utc()
    friday_late = is_friday_late(now)
    weekend = is_weekend(now)

    if macro["gold_macro_bias"] == "bullish":
        bias, state = "BULLISH", "bullish_trend"
    elif macro["gold_macro_bias"] == "bearish":
        bias, state = "BEARISH", "bearish_trend"
    else:
        bias, state = "NEUTRAL", "range"

    blockers = []
    if session == "off_hours":
        blockers.append("Outside active trading sessions")
    if weekend:
        blockers.append("Weekend — market closed")
    if friday_late:
        blockers.append("Friday after 18:00 UTC — weekend gap risk")
    if news_block:
        blockers.append("High-impact news within 2 hours")
    if not spread_ok:
        blockers.append(f"Spread ${price_data['spread']:.2f} exceeds $0.50 limit")
    if open_trades >= max_pos:
        blockers.append(f"Already holding {open_trades} positions (max {max_pos})")
    if drawdown_pct > 5:
        blockers.append(f"Account drawdown {drawdown_pct:.1f}% exceeds 5% limit")

    confidence_floor = 60
    if metrics.get("closed_trades", 0) > 0:
        wr = metrics.get("win_rate", 0)
        ev = metrics.get("expectancy", 0)
        if wr < 0.40 or ev < 0:
            confidence_floor = 75
            blockers.append(f"Self-improvement: win rate {wr:.0%} / EV {ev:.3f}R — confidence threshold raised to {confidence_floor}")

    decision = "NO TRADE" if blockers else "MONITORING"
    confidence = 0 if blockers else 45

    supports = sorted([l for l in nearest if l < price], reverse=True)
    resistances = sorted([l for l in nearest if l >= price])

    analysis = f"""## MARKET STATE: {state}

**Current Price:** ${price:.2f} | **Spread:** ${price_data['spread']:.2f} | **Session:** {session.upper().replace('_', ' ')}
**Source:** {price_data['source']} | **Mode:** {settings.get('system_mode', 'paper_trading').replace('_', ' ').title()}

---

### KEY LEVELS
- **Nearest Resistance:** {', '.join(f'${r}' for r in resistances[:2]) if resistances else 'None identified'}
- **Nearest Support:** {', '.join(f'${s}' for s in supports[:2]) if supports else 'None identified'}

### MACRO CONTEXT
- **USD Index:** {macro['usd_index']} ({macro['usd_regime']})
- **10Y Treasury:** {macro['treasury_10y']}% ({macro['rate_direction']})
- **Geopolitical Risk:** {macro['geopolitical_risk']}
- **Gold Macro Bias:** {bias}

### ECONOMIC CALENDAR
- **High-impact within 2h:** {'YES — TRADE BLOCKED' if news_block else 'No'}
- **Nearest event:** {calendar['nearest_high_impact']['name'] if calendar['nearest_high_impact'] else 'None'} ({calendar['nearest_high_impact']['hours_until']:.1f}h away)

### NO-TRADE FILTER
{chr(10).join(f'- BLOCKED: {b}' for b in blockers) if blockers else '- No blockers active'}

### TRADE SIGNAL: **{decision}**
### CONFIDENCE: **{confidence}/100**

### REASONING
{'Trade blocked due to: ' + '; '.join(blockers) if blockers else 'No clear setup identified. Monitoring for pullback to key support/resistance levels.'}

---
*{'Demo mode — set ANTHROPIC_API_KEY for AI-powered analysis' if not ANTHROPIC_API_KEY else 'Analysis powered by Claude'}*
"""

    if metrics.get("closed_trades", 0) > 0:
        analysis += f"""
### SELF-IMPROVEMENT CHECK
- **Win Rate:** {metrics.get('win_rate', 0):.1%}
- **Expectancy:** {metrics.get('expectancy', 0):.3f}R
- **Edge Status:** {metrics.get('edge_status', 'Collecting data')}
- **Phase:** {metrics.get('phase', 1)}
"""

    log = load_json(ANALYSIS_LOG, [])
    log.append({
        "id": epoch_ms(),
        "timestamp": utc_timestamp(),
        "analysis_type": "full_analysis",
        "market_state": state,
        "decision": decision,
        "confidence": confidence,
        "price": price,
        "blockers": blockers,
        "mode": "demo" if not ANTHROPIC_API_KEY else "claude",
    })
    save_json(ANALYSIS_LOG, log)

    return {
        "analysis": analysis,
        "iterations": 1,
        "timestamp": utc_timestamp(),
        "model": "rule-based (demo)" if not ANTHROPIC_API_KEY else CLAUDE_MODEL,
        "market_data": {"price": price_data, "macro": macro, "calendar": calendar, "structure": structure},
    }


def run_claude_analysis(user_context=""):
    """Claude tool-calling analysis — legacy compat."""
    if not ANTHROPIC_API_KEY:
        return run_demo_analysis()

    from urllib.request import Request, urlopen

    messages = [{"role": "user", "content": f"Run a complete XAU/USD analysis now.\n{f'Context: {user_context}' if user_context else ''}\nFollow the full pipeline. NO TRADE is the default."}]
    headers = {"Content-Type": "application/json", "x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01"}

    max_iterations = 10
    iteration = 0
    final_response = ""

    while iteration < max_iterations:
        iteration += 1
        payload = {"model": CLAUDE_MODEL, "max_tokens": 4096, "system": build_system_prompt(), "tools": CLAUDE_TOOLS, "messages": messages}

        try:
            req = Request("https://api.anthropic.com/v1/messages", data=json.dumps(payload).encode(), headers=headers, method="POST")
            with urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read().decode())
        except Exception as e:
            return {"error": f"Claude API call failed: {str(e)}", "iteration": iteration}

        stop_reason = result.get("stop_reason", "end_turn")
        content_blocks = result.get("content", [])
        tool_uses = []

        for block in content_blocks:
            if block.get("type") == "text":
                final_response += block.get("text", "")
            elif block.get("type") == "tool_use":
                tool_uses.append(block)

        if stop_reason == "end_turn" or not tool_uses:
            break

        messages.append({"role": "assistant", "content": content_blocks})
        tool_results = []
        for tool_use in tool_uses:
            tool_result = execute_tool(tool_use["name"], tool_use.get("input", {}))
            tool_results.append({"type": "tool_result", "tool_use_id": tool_use["id"], "content": json.dumps(tool_result, default=str)})
        messages.append({"role": "user", "content": tool_results})

    return {"analysis": final_response, "iterations": iteration, "timestamp": utc_timestamp(), "model": CLAUDE_MODEL}


# ─── Structured Decision Pipeline ──────────────────────────────────────────────

def run_structured_decision(use_claude: bool = True) -> dict:
    """Run the new structured decision pipeline.
    Returns full decision with audit trail.
    """
    quote = market_provider.get_quote()
    macro = macro_provider.get_macro_context()
    calendar = calendar_provider.get_upcoming_events()
    candles_1h = market_provider.get_candles("1h", 100)
    candles_15m = market_provider.get_candles("15m", 100)
    candles_4h = market_provider.get_candles("4h", 50)

    settings = load_settings()
    broker = get_paper_broker()
    account_state = broker.get_account_features()

    features = compute_all_features(
        candles_1h=candles_1h, quote=quote, macro=macro,
        calendar=calendar, account_state=account_state,
        candles_15m=candles_15m, candles_4h=candles_4h,
    )

    candles_dict = {"1h": candles_1h, "15m": candles_15m, "4h": candles_4h}
    metrics = compute_metrics()

    engine = get_decision_engine()
    result = engine.decide(
        features=features, candles=candles_dict,
        settings=settings, metrics=metrics,
        use_claude=use_claude and bool(ANTHROPIC_API_KEY),
    )

    # Audit: persist data provenance alongside the decision so future
    # analysis can distinguish simulated-data decisions from real-data ones.
    provider_status = get_provider_status()
    result["data_provenance"] = {
        "provider": provider_status.get("name"),
        "kind": provider_status.get("kind"),
        "is_real": provider_status.get("is_real"),
        "quote_timestamp": quote.get("timestamp"),
        "quote_source": quote.get("source"),
    }
    decision_store.store(result)
    return result


# ─── HTTP Server ────────────────────────────────────────────────────────────────

class GoldAgentHandler(BaseHTTPRequestHandler):

    def _cors_headers(self):
        if CORS_ALLOWED_ORIGINS:
            origin = self.headers.get("Origin", "")
            allowed = [o.strip() for o in CORS_ALLOWED_ORIGINS.split(",")]
            if origin in allowed:
                self.send_header("Access-Control-Allow-Origin", origin)
            # If origin not in list, omit the header (browser blocks the request)
        else:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")

    def _check_auth(self):
        """Return True if request is authorized. Sends 401 and returns False otherwise.

        Supports:
          - Disabled (no API_TOKENS_FILE / API_AUTH_TOKEN)    -> always allowed
          - Single-token legacy mode (API_AUTH_TOKEN)         -> match exactly
          - Multi-token mode (API_TOKENS_FILE=<path>)         -> match any entry

        The authenticated principal is attached to the handler as self._principal
        so downstream handlers can log who made the request. Auth decisions are
        recorded to the audit ring buffer.
        """
        # Legacy compat: if callers mutated module-level API_AUTH_TOKEN directly
        # (existing tests do this), propagate to env so auth_module picks it up.
        # We sync BOTH directions: empty string clears env, non-empty sets it.
        global API_AUTH_TOKEN
        if API_AUTH_TOKEN:
            if os.environ.get("API_AUTH_TOKEN") != API_AUTH_TOKEN:
                os.environ["API_AUTH_TOKEN"] = API_AUTH_TOKEN
        else:
            # server.API_AUTH_TOKEN was cleared -- ensure env agrees.
            os.environ.pop("API_AUTH_TOKEN", None)

        principal = auth_module.authenticate(self.headers.get("Authorization"))
        if principal is not None:
            self._principal = principal
            auth_module.record_auth_event(
                principal=principal.principal,
                path=self.path,
                method=self.command,
                result="allow",
            )
            return True

        # Drain any unread request body to prevent broken pipe on the client.
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        auth_module.record_auth_event(
            principal=None,
            path=self.path,
            method=self.command,
            result="deny",
            reason="invalid or missing bearer token",
        )
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps({
            "error": "Unauthorized — set Authorization: Bearer <token>",
            "auth_mode": auth_module.resolve_auth_mode()["mode"],
        }).encode())
        return False

    def _json_response(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self._cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data, default=str).encode())

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            raw = self.rfile.read(length)
            data, err = parse_json_body(raw)
            if err:
                return None, err
            return data, None
        return {}, None

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        # Health endpoint is always public (load balancers, monitoring)
        if path == "/api/health":
            # Sync legacy server.API_AUTH_TOKEN to env so tests that mutate
            # the module-level var see accurate auth state in the response.
            global API_AUTH_TOKEN
            if API_AUTH_TOKEN:
                os.environ["API_AUTH_TOKEN"] = API_AUTH_TOKEN
            else:
                os.environ.pop("API_AUTH_TOKEN", None)
            settings = load_settings()
            provider_status = get_provider_status()
            broker_status = get_live_broker_status()
            # Cheap readiness summary -- skip risk eval for speed in health pings.
            quick = evaluate_live_readiness(
                live_enabled=is_live_enabled(),
                provider_status=provider_status,
                broker_status=broker_status,
                settings=settings,
                risk_blockers=[],
                stale_data_seconds=int(settings.get("stale_data_seconds", 300)),
                broker_environment=broker_environment(),
                cutover_acknowledged=is_cutover_acknowledged(),
            )
            # Macro/calendar source labels (best-effort, safe if get_status absent).
            macro_source = "simulated"
            calendar_source = "simulated"
            try:
                if hasattr(macro_provider, "get_status"):
                    macro_source = macro_provider.get_status().get("name", macro_source)
            except Exception:
                pass
            try:
                if hasattr(calendar_provider, "get_status"):
                    calendar_source = calendar_provider.get_status().get("name", calendar_source)
            except Exception:
                pass

            self._json_response({
                "status": "ok",
                "version": "4.0",
                "phase": 3,
                "has_api_key": bool(ANTHROPIC_API_KEY),
                "claude_available": bool(ANTHROPIC_API_KEY),
                "auth_enabled": auth_module.is_enabled(),
                "auth_mode": auth_module.resolve_auth_mode()["mode"],
                "cors_restricted": bool(CORS_ALLOWED_ORIGINS),
                "bind_host": BIND_HOST,
                "data_provider": DATA_PROVIDER,
                "data_source": provider_status.get("kind"),
                "data_is_real": provider_status.get("is_real", False),
                "data_provider_ready": provider_status.get("ready", False),
                "data_last_quote_age_seconds": provider_status.get("last_quote_age_seconds"),
                "macro_source": macro_source,
                "calendar_source": calendar_source,
                "system_mode": settings.get("system_mode", "paper_trading"),
                "paper_available": True,
                "live_enabled": is_live_enabled(),
                "live_broker_selected": selected_live_broker(),
                "live_broker_implemented": broker_status.get("implemented", False),
                "live_broker_environment": broker_status.get("environment"),
                "practice_mode": broker_status.get("practice_mode", False),
                "cutover_acknowledged": broker_status.get("cutover_acknowledged", False),
                "live_cutover_allowed": broker_status.get("live_cutover_allowed", False),
                "broker_validated": broker_status.get("validated", False),
                "provider_validated": bool(provider_status.get("is_real")) and bool(provider_status.get("ready")),
                "live_ready": quick.ready,
                "live_blocker_count": quick.to_dict()["hard_blocker_count"],
                "live_blocker_rules": [b.rule for b in quick.blockers if b.severity == "hard"],
                "strategies": strategy_registry.list_strategies(),
                "timestamp": utc_timestamp(),
            })
            return

        if path == "/api/auth/audit":
            if not self._check_auth():
                return
            try:
                limit = int(params.get("limit", [50])[0])
            except (TypeError, ValueError):
                limit = 50
            self._json_response({
                "mode": auth_module.resolve_auth_mode(),
                "events": auth_module.recent_auth_events(limit=limit),
                "timestamp": utc_timestamp(),
            })
            return

        if not self._check_auth():
            return

        try:
            if False:
                pass  # placeholder for elif chain below

            elif path == "/api/price":
                self._json_response(get_market_price())

            elif path == "/api/macro":
                self._json_response(get_macro_context())

            elif path == "/api/calendar":
                self._json_response(get_economic_calendar())

            elif path == "/api/structure":
                price_data = get_market_price()
                self._json_response(preprocess_market_structure(price_data))

            elif path == "/api/features":
                quote = market_provider.get_quote()
                macro = macro_provider.get_macro_context()
                calendar = calendar_provider.get_upcoming_events()
                candles_1h = market_provider.get_candles("1h", 100)
                broker = get_paper_broker()
                features = compute_all_features(
                    candles_1h=candles_1h, quote=quote, macro=macro,
                    calendar=calendar, account_state=broker.get_account_features(),
                )
                self._json_response(features)

            elif path == "/api/strategies":
                quote = market_provider.get_quote()
                macro = macro_provider.get_macro_context()
                calendar = calendar_provider.get_upcoming_events()
                candles_1h = market_provider.get_candles("1h", 100)
                broker = get_paper_broker()
                features = compute_all_features(
                    candles_1h=candles_1h, quote=quote, macro=macro,
                    calendar=calendar, account_state=broker.get_account_features(),
                )
                candles_dict = {"1h": candles_1h}
                results = strategy_registry.evaluate_all(features, candles_dict)
                self._json_response({
                    "strategies": [r.to_dict() for r in results],
                    "valid_count": sum(1 for r in results if r.valid),
                })

            elif path == "/api/risk":
                quote = market_provider.get_quote()
                macro = macro_provider.get_macro_context()
                calendar = calendar_provider.get_upcoming_events()
                candles_1h = market_provider.get_candles("1h", 100)
                broker = get_paper_broker()
                features = compute_all_features(
                    candles_1h=candles_1h, quote=quote, macro=macro,
                    calendar=calendar, account_state=broker.get_account_features(),
                )
                engine = get_risk_engine()
                allowed, blockers = engine.is_allowed(features)
                self._json_response({
                    "trading_allowed": allowed,
                    "blockers": [b.to_dict() for b in blockers],
                    "config": engine.config.to_dict(),
                })

            elif path == "/api/trades":
                status = params.get("status", [None])[0]
                self._json_response(get_trades(status))

            elif path == "/api/metrics":
                self._json_response(compute_metrics())

            elif path == "/api/settings":
                self._json_response(load_settings())

            elif path == "/api/analysis-log":
                log = load_json(ANALYSIS_LOG, [])
                limit = int(params.get("limit", [20])[0])
                self._json_response(log[-limit:])

            elif path == "/api/paper/account":
                broker = get_paper_broker()
                self._json_response(broker.get_account())

            elif path == "/api/paper/positions":
                broker = get_paper_broker()
                self._json_response([p.to_dict() for p in broker.get_positions()])

            elif path == "/api/paper/fills":
                broker = get_paper_broker()
                limit = int(params.get("limit", [50])[0])
                self._json_response(broker.get_fills(limit))

            elif path == "/api/decisions":
                limit = int(params.get("limit", [20])[0])
                self._json_response(decision_store.get_recent(limit))

            elif path == "/api/decisions/analysis":
                self._json_response(decision_store.analyze_claude_accuracy())

            elif path == "/api/experiments":
                self._json_response(experiment_tracker.get_all())

            elif path == "/api/readiness":
                self._json_response(get_live_readiness())

            elif path == "/api/historical/list":
                self._json_response({
                    "directory": str(DATA_DIR / "historical"),
                    "files": historical_import.list_available(DATA_DIR / "historical"),
                })

            else:
                self._json_response({"error": "Not found"}, 404)

        except Exception as e:
            self._json_response({"error": str(e), "trace": traceback.format_exc()}, 500)

    def do_POST(self):
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body, err = self._read_body()
            if err:
                self._json_response({"error": err}, 400)
                return

            if path == "/api/analyze":
                context = body.get("context", "")
                result = run_claude_analysis(context)
                self._json_response(result)

            elif path == "/api/decide":
                use_claude = body.get("use_claude", True)
                result = run_structured_decision(use_claude=use_claude)
                self._json_response(result)

            elif path == "/api/trades":
                errors = validate_trade_input(body)
                if errors:
                    self._json_response({"error": "; ".join(errors)}, 400)
                    return
                trade = log_trade(body)
                self._json_response(trade, 201)

            elif path == "/api/settings":
                errors = validate_settings(body)
                if errors:
                    self._json_response({"error": "; ".join(errors)}, 400)
                    return
                settings = load_settings()
                settings.update(body)
                save_settings(settings)
                self._json_response(settings)

            elif path == "/api/paper/execute":
                """Execute a trade through the paper broker based on the latest decision."""
                decision_id = body.get("decision_id")
                if not decision_id:
                    result = run_structured_decision(use_claude=body.get("use_claude", False))
                else:
                    decisions = decision_store.get_recent(50)
                    result = next((d for d in decisions if str(d.get("id")) == str(decision_id)), None)
                    if not result:
                        self._json_response({"error": "Decision not found"}, 404)
                        return

                dec = result.get("decision", {})
                if dec.get("trade_or_no_trade") != "trade":
                    self._json_response({"error": "Decision is no_trade", "decision": dec}, 400)
                    return

                settings = load_settings()
                if settings.get("system_mode") not in ("paper_trading",):
                    self._json_response({"error": f"System mode is '{settings.get('system_mode')}', not paper_trading"}, 400)
                    return

                broker = get_paper_broker()
                risk = get_risk_engine()
                pos_size = risk.compute_position_size(
                    equity=broker.get_account()["equity"],
                    entry=dec["entry"],
                    stop=dec["stop"],
                )

                from backend.execution.broker_base import BrokerOrder
                order = BrokerOrder(
                    direction=dec.get("chosen_strategy", "").split("_")[0] if dec.get("entry") and dec.get("stop") and dec["entry"] > dec["stop"] else "long",
                    entry=dec["entry"],
                    stop=dec["stop"],
                    target_1=dec["target_1"],
                    target_2=dec.get("target_2"),
                    position_lots=pos_size["position_lots"],
                    strategy=dec.get("chosen_strategy", ""),
                    decision_id=str(result.get("decision_id", "")),
                )
                # Set direction based on entry/stop
                if dec["entry"] > dec["stop"]:
                    order.direction = "long"
                else:
                    order.direction = "short"

                fill = broker.submit_order(order)

                # ── Paper → Journal sync: create journal entry on open ──
                journal_trade = log_trade({
                    "direction": order.direction,
                    "entry": fill["fill_price"],
                    "stop": dec["stop"],
                    "t1": dec["target_1"],
                    "t2": dec.get("target_2"),
                    "zone": "Paper",
                    "trigger": "Decision Pipeline",
                    "risk_distance": round(abs(fill["fill_price"] - dec["stop"]), 2),
                    "rr_to_t1": round(abs(dec["target_1"] - fill["fill_price"]) / max(abs(fill["fill_price"] - dec["stop"]), 0.01), 2) if dec.get("target_1") else None,
                    "position_oz": pos_size.get("position_oz", 0),
                    "position_lots": pos_size.get("position_lots", 0),
                    "risk_usd": pos_size.get("risk_usd", 0),
                    "status": "open",
                    "exit_price": None,
                    "r_multiple": None,
                    "error_type": "None",
                    "notes": f"Paper trade via {dec.get('chosen_strategy', 'unknown')} | Decision {result.get('decision_id', '')}",
                    "paper_position_id": fill["position_id"],
                    "source": "paper_broker",
                    "strategy": dec.get("chosen_strategy", ""),
                    "date": fill.get("timestamp") or utc_timestamp(),
                })
                self._json_response({"fill": fill, "position_size": pos_size, "journal_trade_id": journal_trade["id"]})

            elif path == "/api/paper/close":
                position_id = body.get("position_id")
                price = body.get("price")
                if not position_id:
                    self._json_response({"error": "position_id required"}, 400)
                    return
                if not price:
                    quote = market_provider.get_quote()
                    price = quote["price"]
                broker = get_paper_broker()
                result = broker.close_position(position_id, price)

                # ── Paper → Journal sync: update journal entry on close ──
                if result.get("status") == "closed":
                    trades = get_trades()
                    for t in trades:
                        if t.get("paper_position_id") == position_id and t.get("status") == "open":
                            update_trade(t["id"], {
                                "status": "closed",
                                "exit_price": result["exit_price"],
                                "r_multiple": result["r_multiple"],
                                "exit_reason": result.get("exit_reason", "manual_close"),
                                "closed_at": utc_timestamp(),
                            })
                            break

                self._json_response(result)

            elif path == "/api/backtest":
                n_candles = body.get("candles", 500)
                spread = body.get("spread", 0.40)
                candles_1h = market_provider.get_candles("1h", n_candles)

                engine = BacktestEngine(
                    strategy_registry=strategy_registry,
                    spread=spread,
                )
                result = engine.run(candles_1h)

                baselines = run_all_baselines(candles_1h, spread=spread)

                experiment_tracker.log_experiment(
                    name=f"backtest_{epoch_ms()}",
                    config={"candles": n_candles, "spread": spread, "strategies": strategy_registry.list_strategies()},
                    results=result["metrics"],
                    description=f"Backtest over {n_candles} 1h candles",
                )

                self._json_response({"backtest": result, "baselines": baselines})

            elif path == "/api/backtest/historical":
                # Backtest using imported historical OHLC data (CSV or JSON).
                # Body: {"filename": "xauusd_1h.csv", "timeframe": "1h", "spread": 0.40}
                filename = body.get("filename")
                if not filename:
                    self._json_response({"error": "filename is required"}, 400)
                    return
                # Path-traversal guard: only basenames inside DATA_DIR/historical.
                safe_name = Path(filename).name
                if safe_name != filename:
                    self._json_response({"error": "filename must not contain path separators"}, 400)
                    return
                hist_dir = DATA_DIR / "historical"
                file_path = hist_dir / safe_name
                if not file_path.exists():
                    self._json_response({
                        "error": f"file not found in {hist_dir}: {safe_name}",
                        "available": [f["filename"] for f in historical_import.list_available(hist_dir)],
                    }, 404)
                    return
                timeframe = body.get("timeframe", "1h")
                spread = body.get("spread", 0.40)
                try:
                    candles_1h = historical_import.load_candles(file_path, timeframe)
                except historical_import.HistoricalImportError as e:
                    self._json_response({"error": f"import failed: {e}"}, 400)
                    return

                engine = BacktestEngine(
                    strategy_registry=strategy_registry,
                    spread=spread,
                )
                result = engine.run(candles_1h)
                baselines = run_all_baselines(candles_1h, spread=spread)

                experiment_tracker.log_experiment(
                    name=f"backtest_historical_{epoch_ms()}",
                    config={
                        "source": "historical_import",
                        "filename": safe_name,
                        "timeframe": timeframe,
                        "candles": len(candles_1h),
                        "spread": spread,
                    },
                    results=result["metrics"],
                    description=f"Historical backtest from {safe_name}",
                )

                self._json_response({
                    "source": "historical_import",
                    "filename": safe_name,
                    "candles_loaded": len(candles_1h),
                    "first_timestamp": candles_1h[0]["timestamp"] if candles_1h else None,
                    "last_timestamp": candles_1h[-1]["timestamp"] if candles_1h else None,
                    "backtest": result,
                    "baselines": baselines,
                })

            elif path == "/api/backtest/walk-forward":
                n_candles = body.get("candles", 500)
                n_folds = body.get("folds", 3)
                candles_1h = market_provider.get_candles("1h", n_candles)

                result = run_walk_forward(
                    candles_1h=candles_1h,
                    n_folds=n_folds,
                    registry=strategy_registry,
                )

                experiment_tracker.log_experiment(
                    name=f"walk_forward_{epoch_ms()}",
                    config={"candles": n_candles, "folds": n_folds},
                    results=result.get("aggregate_oos_metrics", {}),
                    description=f"Walk-forward {n_folds}-fold over {n_candles} candles",
                )

                self._json_response(result)

            else:
                self._json_response({"error": "Not found"}, 404)

        except Exception as e:
            self._json_response({"error": str(e), "trace": traceback.format_exc()}, 500)

    def do_PUT(self):
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            body, err = self._read_body()
            if err:
                self._json_response({"error": err}, 400)
                return

            if path.startswith("/api/trades/"):
                raw_id = path.split("/")[-1]
                trade_id, err = validate_trade_id(raw_id)
                if err:
                    self._json_response({"error": err}, 400)
                    return
                result = update_trade(trade_id, body)
                if result:
                    self._json_response(result)
                else:
                    self._json_response({"error": "Trade not found"}, 404)
            else:
                self._json_response({"error": "Not found"}, 404)

        except Exception as e:
            self._json_response({"error": str(e), "trace": traceback.format_exc()}, 500)

    def do_DELETE(self):
        if not self._check_auth():
            return

        parsed = urlparse(self.path)
        path = parsed.path

        try:
            if path.startswith("/api/trades/"):
                raw_id = path.split("/")[-1]
                trade_id, err = validate_trade_id(raw_id)
                if err:
                    self._json_response({"error": err}, 400)
                    return
                delete_trade(trade_id)
                self._json_response({"deleted": True})
            else:
                self._json_response({"error": "Not found"}, 404)

        except Exception as e:
            self._json_response({"error": str(e), "trace": traceback.format_exc()}, 500)

    def log_message(self, format, *args):
        pass


def main():
    settings = load_settings()
    mode = settings.get("system_mode", "paper_trading")

    auth_mode = auth_module.resolve_auth_mode()
    if auth_mode["mode"] == "multi_token":
        auth_status = f"ENABLED ({auth_mode['token_count']} tokens via file)"
    elif auth_mode["mode"] == "single_token":
        auth_status = "ENABLED (legacy single token)"
    else:
        auth_status = "DISABLED (local dev)"
    cors_status = f"restricted to: {CORS_ALLOWED_ORIGINS}" if CORS_ALLOWED_ORIGINS else "open (local dev)"
    bind_warning = ""
    if BIND_HOST == "0.0.0.0" and auth_mode["mode"] == "disabled":
        bind_warning = "\n  ⚠  WARNING: Binding to 0.0.0.0 without auth — API is open to the network"
    if auth_mode.get("warning"):
        bind_warning += f"\n  ⚠  AUTH: {auth_mode['warning']}"

    provider_status = get_provider_status()
    provider_summary = (
        f"{provider_status.get('name')} "
        f"({'real' if provider_status.get('is_real') else 'simulated'}, "
        f"{'ready' if provider_status.get('ready') else 'NOT READY'})"
    )
    if _PROVIDER_FALLBACK_REASON:
        provider_summary += f" -- fell back: {_PROVIDER_FALLBACK_REASON}"

    broker_status = get_live_broker_status()
    env_label = broker_status.get("environment", "unknown")
    if not broker_status.get("enabled"):
        live_summary = "DISABLED (safe default — paper only)"
    elif not broker_status.get("implemented"):
        live_summary = f"ENABLED but adapter NOT IMPLEMENTED ({broker_status.get('selected')})"
    elif env_label == "live" and not broker_status.get("cutover_acknowledged"):
        live_summary = "ENABLED on LIVE env — BLOCKED (cutover not ack)"
    elif broker_status.get("ready"):
        live_summary = f"ENABLED + ready ({broker_status.get('selected')} / {env_label})"
    else:
        live_summary = f"ENABLED but NOT READY ({broker_status.get('reason') or 'see /api/readiness'})"

    # Extra hard-to-miss warning when the operator has flipped on live-money
    # config but hasn't completed the supervised cutover acknowledgement.
    if (
        broker_status.get("enabled")
        and broker_status.get("implemented")
        and env_label == "live"
        and not broker_status.get("cutover_acknowledged")
    ):
        bind_warning += (
            "\n  ⚠  LIVE ENV: OANDA_ENVIRONMENT=live but "
            "LIVE_CUTOVER_ACKNOWLEDGED!=true — live orders BLOCKED."
        )

    print(f"""
╔═══════════════════════════════════════════════════════════════════╗
║  Gold Market Intelligence System v4.0 (Phase 3)                  ║
║  Research + paper-trading; live after supervised validation      ║
║  Default posture: paper only — real-money live blocked by gate   ║
╠═══════════════════════════════════════════════════════════════════╣
║  Listening:  http://{BIND_HOST}:{PORT:<5d}                             ║
║  Mode:       {mode:<48s} ║
║  API Key:    {'configured' if ANTHROPIC_API_KEY else 'NOT SET — demo mode':<48s} ║
║  Auth:       {auth_status:<48s} ║
║  CORS:       {cors_status:<48s} ║
║  Data:       {provider_summary:<48s} ║
║  Live trade: {live_summary:<48s} ║
║  Strategies: {', '.join(strategy_registry.list_strategies()):<48s} ║
╚═══════════════════════════════════════════════════════════════════╝{bind_warning}

Endpoints:
  GET  /api/health           System status (public, no auth required)
  GET  /api/readiness        Detailed live-readiness report (auth gated)
  GET  /api/historical/list  List importable historical OHLC files
  POST /api/backtest/historical  Backtest an imported OHLC file
  GET  /api/price            XAU/USD price ({DATA_PROVIDER})
  GET  /api/features         Computed market features
  GET  /api/strategies       Strategy evaluations
  GET  /api/risk             Risk blockers
  GET  /api/metrics          Performance analytics
  GET  /api/paper/account    Paper trading account
  GET  /api/paper/positions  Open paper positions
  GET  /api/decisions        Decision history
  GET  /api/experiments      Experiment history
  POST /api/analyze          Legacy analysis
  POST /api/decide           Structured decision pipeline
  POST /api/paper/execute    Execute paper trade
  POST /api/backtest         Run backtest
  POST /api/backtest/walk-forward  Walk-forward analysis
""")
    httpd = HTTPServer((BIND_HOST, PORT), GoldAgentHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.server_close()


if __name__ == "__main__":
    main()
