"""
Schema definitions and validation for the Gold Trading Platform.
All structured data flowing through the system is validated here.
"""

from enum import Enum
from typing import Optional


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"


class TradeStatus(str, Enum):
    OPEN = "open"
    CLOSED = "closed"


class MarketState(str, Enum):
    BULLISH_TREND = "bullish_trend"
    BEARISH_TREND = "bearish_trend"
    RANGE = "range"
    EXPANSION = "expansion"
    COMPRESSION = "compression"
    TRANSITION = "transition"


class SystemMode(str, Enum):
    ANALYSIS_ONLY = "analysis_only"
    BACKTEST = "backtest"
    PAPER_TRADING = "paper_trading"
    LIVE_DISABLED = "live_disabled"


class Timeframe(str, Enum):
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    H1 = "1h"
    H4 = "4h"
    D1 = "1d"


# --- Candle ---

CANDLE_REQUIRED = {"timestamp", "open", "high", "low", "close"}
CANDLE_OPTIONAL = {"volume", "timeframe"}


def validate_candle(c: dict) -> Optional[str]:
    """Validate a candle dict. Returns error string or None."""
    missing = CANDLE_REQUIRED - set(c.keys())
    if missing:
        return f"Missing candle fields: {missing}"
    for f in ("open", "high", "low", "close"):
        if not isinstance(c[f], (int, float)) or c[f] <= 0:
            return f"Candle field '{f}' must be a positive number"
    if c["high"] < c["low"]:
        return "Candle high < low"
    if c["high"] < c["open"] or c["high"] < c["close"]:
        return "Candle high must be >= open and close"
    if c["low"] > c["open"] or c["low"] > c["close"]:
        return "Candle low must be <= open and close"
    return None


# --- Decision Schema ---

DECISION_SCHEMA_FIELDS = {
    "market_state": str,
    "chosen_strategy": str,       # strategy name or "no_trade"
    "thesis_summary": str,
    "invalidation_summary": str,
    "entry": (float, type(None)),
    "stop": (float, type(None)),
    "target_1": (float, type(None)),
    "target_2": (float, type(None)),
    "confidence": int,
    "trade_or_no_trade": str,     # "trade" or "no_trade"
    "rationale": list,
    "risk_notes": list,
    "uncertainty_notes": list,
}


def validate_decision(d: dict) -> list:
    """Validate a Claude decision output. Returns list of error strings."""
    errors = []
    for field, expected_type in DECISION_SCHEMA_FIELDS.items():
        if field not in d:
            errors.append(f"Missing field: {field}")
            continue
        val = d[field]
        if isinstance(expected_type, tuple):
            if not isinstance(val, expected_type):
                errors.append(f"Field '{field}' expected {expected_type}, got {type(val).__name__}")
        else:
            if not isinstance(val, expected_type):
                errors.append(f"Field '{field}' expected {expected_type.__name__}, got {type(val).__name__}")

    if not errors:
        if d["trade_or_no_trade"] not in ("trade", "no_trade"):
            errors.append("trade_or_no_trade must be 'trade' or 'no_trade'")
        if not (0 <= d["confidence"] <= 100):
            errors.append("confidence must be 0-100")
        if d["trade_or_no_trade"] == "trade":
            for f in ("entry", "stop", "target_1"):
                if d.get(f) is None:
                    errors.append(f"Field '{f}' required when trade_or_no_trade is 'trade'")
            if d.get("entry") and d.get("stop") and d.get("target_1"):
                risk = abs(d["entry"] - d["stop"])
                reward = abs(d["target_1"] - d["entry"])
                if risk > 0 and reward / risk < 1.5:
                    errors.append(f"R:R to target_1 is {reward/risk:.2f}, minimum 1.5 required")
    return errors


# --- Trade Validation ---

TRADE_REQUIRED = {"direction", "entry", "stop", "status"}


def validate_trade_input(t: dict) -> list:
    """Validate trade input for logging. Returns list of errors."""
    errors = []
    missing = TRADE_REQUIRED - set(t.keys())
    if missing:
        errors.append(f"Missing fields: {missing}")
        return errors

    if t["direction"] not in ("long", "short"):
        errors.append("direction must be 'long' or 'short'")
    if t["status"] not in ("open", "closed"):
        errors.append("status must be 'open' or 'closed'")
    for f in ("entry", "stop"):
        if not isinstance(t.get(f), (int, float)) or t[f] <= 0:
            errors.append(f"'{f}' must be a positive number")
    if t.get("entry") and t.get("stop"):
        if t["direction"] == "long" and t["stop"] >= t["entry"]:
            errors.append("For long trades, stop must be below entry")
        if t["direction"] == "short" and t["stop"] <= t["entry"]:
            errors.append("For short trades, stop must be above entry")
    return errors


# --- Settings Validation ---

SETTINGS_RANGES = {
    "equity": (100, 100_000_000),
    "risk_pct": (0.01, 10.0),
    "max_positions": (1, 20),
    "max_daily_loss_pct": (0.5, 20.0),
    "max_drawdown_pct": (1.0, 50.0),
    "max_trades_per_day": (1, 100),
    "friday_cutoff_hour": (12, 23),
    "cooloff_after_losses": (0, 10),
}


def validate_settings(s: dict) -> list:
    """Validate settings values. Returns list of errors."""
    errors = []
    for field, (lo, hi) in SETTINGS_RANGES.items():
        if field in s:
            val = s[field]
            if not isinstance(val, (int, float)):
                errors.append(f"'{field}' must be numeric")
            elif val < lo or val > hi:
                errors.append(f"'{field}' must be between {lo} and {hi}")
    return errors
