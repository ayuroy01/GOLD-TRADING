"""
Deterministic market feature engine.
Computes structured, testable features from raw market data.
No LLM calls — pure computation.
"""

import math
from typing import List, Optional
from backend.core.time_utils import now_utc, get_session, is_weekend, is_friday_late, parse_utc


def compute_atr(candles: List[dict], period: int = 14) -> float:
    """Compute Average True Range over the last `period` candles."""
    if len(candles) < 2:
        return 0.0
    trs = []
    for i in range(1, len(candles)):
        c = candles[i]
        prev_close = candles[i - 1]["close"]
        tr = max(
            c["high"] - c["low"],
            abs(c["high"] - prev_close),
            abs(c["low"] - prev_close),
        )
        trs.append(tr)
    recent = trs[-period:] if len(trs) >= period else trs
    return sum(recent) / len(recent) if recent else 0.0


def compute_rolling_high(candles: List[dict], window: int = 20) -> float:
    """Highest high over the last `window` candles."""
    recent = candles[-window:]
    return max(c["high"] for c in recent) if recent else 0.0


def compute_rolling_low(candles: List[dict], window: int = 20) -> float:
    """Lowest low over the last `window` candles."""
    recent = candles[-window:]
    return min(c["low"] for c in recent) if recent else 0.0


def find_swing_highs(candles: List[dict], lookback: int = 5) -> List[float]:
    """Find recent swing high levels (local maxima)."""
    if len(candles) < lookback * 2 + 1:
        return []
    highs = []
    for i in range(lookback, len(candles) - lookback):
        h = candles[i]["high"]
        is_swing = all(candles[j]["high"] < h for j in range(i - lookback, i))
        is_swing = is_swing and all(candles[j]["high"] < h for j in range(i + 1, i + lookback + 1))
        if is_swing:
            highs.append(h)
    return highs[-5:]


def find_swing_lows(candles: List[dict], lookback: int = 5) -> List[float]:
    """Find recent swing low levels (local minima)."""
    if len(candles) < lookback * 2 + 1:
        return []
    lows = []
    for i in range(lookback, len(candles) - lookback):
        l = candles[i]["low"]
        is_swing = all(candles[j]["low"] > l for j in range(i - lookback, i))
        is_swing = is_swing and all(candles[j]["low"] > l for j in range(i + 1, i + lookback + 1))
        if is_swing:
            lows.append(l)
    return lows[-5:]


def compute_trend_regime(candles: List[dict], fast_period: int = 10, slow_period: int = 30) -> str:
    """Determine trend regime using simple moving average crossover.
    Returns: 'uptrend', 'downtrend', or 'ranging'
    """
    if len(candles) < slow_period:
        return "ranging"
    fast_ma = sum(c["close"] for c in candles[-fast_period:]) / fast_period
    slow_ma = sum(c["close"] for c in candles[-slow_period:]) / slow_period
    diff_pct = (fast_ma - slow_ma) / slow_ma * 100

    if diff_pct > 0.15:
        return "uptrend"
    elif diff_pct < -0.15:
        return "downtrend"
    return "ranging"


def compute_volatility_regime(candles: List[dict], atr_period: int = 14) -> str:
    """Classify current volatility as low/normal/high based on ATR percentile."""
    if len(candles) < atr_period + 20:
        return "normal"
    current_atr = compute_atr(candles, atr_period)
    # Compare to historical ATR range
    historical_atrs = []
    for i in range(atr_period, len(candles)):
        window = candles[i - atr_period:i]
        if len(window) >= 2:
            historical_atrs.append(compute_atr(window, atr_period))
    if not historical_atrs:
        return "normal"
    sorted_atrs = sorted(historical_atrs)
    idx = sum(1 for a in sorted_atrs if a < current_atr)
    percentile = idx / len(sorted_atrs)

    if percentile > 0.8:
        return "high"
    elif percentile < 0.2:
        return "low"
    return "normal"


def compute_psychological_levels(price: float) -> List[float]:
    """Compute round-number psychological levels near the current price."""
    r100 = round(price / 100) * 100
    r50 = round(price / 50) * 50
    levels = set()
    for offset in [-200, -150, -100, -50, 0, 50, 100, 150, 200]:
        levels.add(r100 + offset)
    for offset in [-100, -50, 0, 50, 100]:
        levels.add(r50 + offset)
    return sorted(levels)


def compute_support_resistance(candles: List[dict], price: float) -> dict:
    """Compute support and resistance candidates from swing levels and round numbers."""
    swing_highs = find_swing_highs(candles)
    swing_lows = find_swing_lows(candles)
    psych_levels = compute_psychological_levels(price)

    all_levels = sorted(set(swing_highs + swing_lows + psych_levels))
    resistance = sorted([l for l in all_levels if l > price])
    support = sorted([l for l in all_levels if l < price], reverse=True)

    return {
        "resistance": resistance[:5],
        "support": support[:5],
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "psychological": psych_levels,
        "nearest_resistance": resistance[0] if resistance else None,
        "nearest_support": support[0] if support else None,
    }


def compute_spread_regime(spread: float) -> str:
    """Classify spread as tight/normal/wide."""
    if spread <= 0.30:
        return "tight"
    elif spread <= 0.60:
        return "normal"
    return "wide"


def compute_all_features(
    candles_1h: List[dict],
    quote: dict,
    macro: dict,
    calendar: dict,
    account_state: dict = None,
    candles_15m: List[dict] = None,
    candles_4h: List[dict] = None,
    dt=None,
) -> dict:
    """Compute all market features from raw data.
    This is the main entry point for the feature engine.
    Returns a flat dict of structured, testable features.
    """
    if dt is None:
        dt = now_utc()

    price = quote.get("price", 0)
    spread = quote.get("spread", 0)

    # Candle-based features
    atr_14 = compute_atr(candles_1h, 14)
    rolling_high_20 = compute_rolling_high(candles_1h, 20)
    rolling_low_20 = compute_rolling_low(candles_1h, 20)
    trend = compute_trend_regime(candles_1h)
    vol_regime = compute_volatility_regime(candles_1h)
    sr = compute_support_resistance(candles_1h, price)

    # Multi-timeframe trend
    trend_15m = compute_trend_regime(candles_15m) if candles_15m else None
    trend_4h = compute_trend_regime(candles_4h) if candles_4h else None

    # Session and time features
    session = get_session(dt)
    weekend = is_weekend(dt)
    friday_late = is_friday_late(dt)

    # Calendar features
    news_blackout = calendar.get("high_impact_within_2h", False)
    nearest_news = calendar.get("nearest_high_impact")
    hours_to_news = nearest_news["hours_until"] if nearest_news else 999

    # Distance features
    dist_to_resistance = round(sr["nearest_resistance"] - price, 2) if sr["nearest_resistance"] else None
    dist_to_support = round(price - sr["nearest_support"], 2) if sr["nearest_support"] else None

    # Account features
    acct = account_state or {}

    features = {
        # Price
        "price": price,
        "spread": spread,
        "spread_regime": compute_spread_regime(spread),

        # Volatility
        "atr_14": round(atr_14, 2),
        "volatility_regime": vol_regime,

        # Trend
        "trend_1h": trend,
        "trend_15m": trend_15m,
        "trend_4h": trend_4h,

        # Structure
        "rolling_high_20": round(rolling_high_20, 2),
        "rolling_low_20": round(rolling_low_20, 2),
        "nearest_resistance": sr["nearest_resistance"],
        "nearest_support": sr["nearest_support"],
        "dist_to_resistance": dist_to_resistance,
        "dist_to_support": dist_to_support,
        "support_levels": sr["support"],
        "resistance_levels": sr["resistance"],
        "swing_highs": sr["swing_highs"],
        "swing_lows": sr["swing_lows"],

        # Session / Time
        "session": session,
        "is_weekend": weekend,
        "is_friday_late": friday_late,
        "day_of_week": dt.strftime("%A"),

        # Calendar / News
        "news_blackout": news_blackout,
        "hours_to_news": round(hours_to_news, 1),

        # Macro
        "usd_regime": macro.get("usd_regime", "neutral"),
        "gold_macro_bias": macro.get("gold_macro_bias", "neutral"),
        "geopolitical_risk": macro.get("geopolitical_risk", "moderate"),
        "vix_regime": macro.get("vix_regime", "low_vol"),

        # Account (paper/live state)
        "open_positions": acct.get("open_positions", 0),
        "unrealized_pnl": acct.get("unrealized_pnl", 0),
        "current_drawdown_pct": acct.get("current_drawdown_pct", 0),
        "daily_pnl": acct.get("daily_pnl", 0),
        "equity": acct.get("equity", 0),
        "peak_equity": acct.get("peak_equity", 0),
        "trades_today": acct.get("trades_today", 0),
        "consecutive_losses": acct.get("consecutive_losses", 0),

        # Metadata
        "timestamp": dt.isoformat(),
        "data_source": quote.get("source", "unknown"),
    }

    return features
