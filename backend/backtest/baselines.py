"""
Baseline strategies for comparison.
These provide a reference point to measure whether real strategies add value.
"""

from typing import List
from backend.backtest.metrics import compute_backtest_metrics


def no_trade_baseline(candles: List[dict]) -> dict:
    """Baseline: never trade. Always returns zero performance.
    This is the default comparison — any strategy must beat doing nothing.
    """
    return {
        "name": "no_trade_baseline",
        "description": "Never trade. PnL is always zero.",
        "metrics": {
            "total_trades": 0,
            "closed_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "expectancy": 0,
            "profit_factor": 0,
            "sharpe": 0,
            "max_drawdown_r": 0,
            "total_r": 0,
            "equity_curve": [0.0],
            "r_multiples": [],
        },
    }


def random_baseline(candles: List[dict], n_trades: int = 50,
                    spread: float = 0.40, seed: int = 42) -> dict:
    """Baseline: enter random long/short trades at random candles.
    Uses fixed 1:2 risk:reward with ATR-based stop.
    Shows what random entry achieves to establish a floor.
    """
    import random
    rng = random.Random(seed)

    if len(candles) < 50:
        return {
            "name": "random_baseline",
            "description": "Insufficient data for random baseline",
            "metrics": compute_backtest_metrics([]),
        }

    trade_log = []
    # Pick random candle indices, skip first 20 for warmup
    indices = sorted(rng.sample(range(20, len(candles) - 5), min(n_trades, len(candles) - 25)))

    for idx in indices:
        candle = candles[idx]
        price = candle["close"]
        direction = rng.choice(["long", "short"])

        # Compute simple ATR for stop sizing
        recent = candles[max(0, idx - 14):idx]
        if len(recent) < 2:
            continue
        trs = []
        for j in range(1, len(recent)):
            tr = max(
                recent[j]["high"] - recent[j]["low"],
                abs(recent[j]["high"] - recent[j - 1]["close"]),
                abs(recent[j]["low"] - recent[j - 1]["close"]),
            )
            trs.append(tr)
        atr = sum(trs) / len(trs) if trs else 5.0

        if direction == "long":
            entry = price + spread / 2
            stop = entry - atr
            target = entry + atr * 2
        else:
            entry = price - spread / 2
            stop = entry + atr
            target = entry - atr * 2

        # Simulate outcome by scanning forward
        r_mult = None
        exit_reason = "end_of_data"
        for j in range(idx + 1, min(idx + 50, len(candles))):
            fwd = candles[j]
            if direction == "long":
                if fwd["low"] <= stop:
                    r_mult = -1.0
                    exit_reason = "stop_loss"
                    break
                if fwd["high"] >= target:
                    r_mult = 2.0
                    exit_reason = "target"
                    break
            else:
                if fwd["high"] >= stop:
                    r_mult = -1.0
                    exit_reason = "stop_loss"
                    break
                if fwd["low"] <= target:
                    r_mult = 2.0
                    exit_reason = "target"
                    break

        if r_mult is None:
            # Did not hit stop or target — close at last scanned price
            if idx + 50 < len(candles):
                last = candles[idx + 49]["close"]
            else:
                last = candles[-1]["close"]
            risk = abs(entry - stop)
            if risk > 0:
                if direction == "long":
                    r_mult = round((last - entry) / risk, 2)
                else:
                    r_mult = round((entry - last) / risk, 2)
            else:
                r_mult = 0

        trade_log.append({
            "direction": direction,
            "entry": round(entry, 2),
            "stop": round(stop, 2),
            "target_1": round(target, 2),
            "strategy": "random_baseline",
            "exit_reason": exit_reason,
            "r_multiple": r_mult,
            "open_timestamp": candle.get("timestamp", ""),
        })

    return {
        "name": "random_baseline",
        "description": "Random entry with 1:2 R:R using ATR stops",
        "metrics": compute_backtest_metrics(trade_log),
    }


def run_all_baselines(candles: List[dict], spread: float = 0.40) -> List[dict]:
    """Run all baseline comparisons and return results."""
    return [
        no_trade_baseline(candles),
        random_baseline(candles, spread=spread),
    ]
