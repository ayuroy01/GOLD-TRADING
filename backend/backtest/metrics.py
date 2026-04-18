"""
Backtest performance metrics computation.
Takes a trade log and computes comprehensive statistics.
"""

import math
from typing import List, Dict


def compute_backtest_metrics(trade_log: List[dict]) -> dict:
    """Compute comprehensive metrics from a backtest trade log.

    Each trade in the log should have at minimum:
        r_multiple: float
    Optionally:
        strategy, exit_reason, direction, open_timestamp, etc.
    """
    r_multiples = [t["r_multiple"] for t in trade_log
                   if t.get("r_multiple") is not None]

    if not r_multiples:
        return {
            "total_trades": len(trade_log),
            "closed_trades": 0,
            "r_multiples": [],
            "message": "No trades with R-multiples",
        }

    n = len(r_multiples)
    wins = [r for r in r_multiples if r > 0]
    losses = [r for r in r_multiples if r <= 0]

    win_rate = len(wins) / n if n else 0
    avg_win = sum(wins) / len(wins) if wins else 0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0

    expectancy = win_rate * avg_win - (1 - win_rate) * avg_loss

    # Equity curve
    curve = [0.0]
    cum = 0.0
    for r in r_multiples:
        cum += r
        curve.append(round(cum, 2))

    # Max drawdown
    peak = 0.0
    max_dd = 0.0
    for val in curve:
        if val > peak:
            peak = val
        dd = peak - val
        if dd > max_dd:
            max_dd = dd

    # Profit factor
    gross_win = sum(wins) if wins else 0
    gross_loss = abs(sum(losses)) if losses else 0
    pf = gross_win / gross_loss if gross_loss > 0 else (float('inf') if gross_win > 0 else 0)

    # Standard deviation
    mean = sum(r_multiples) / n
    variance = sum((r - mean) ** 2 for r in r_multiples) / n if n > 1 else 0
    std = math.sqrt(variance)

    # Sharpe-like (expectancy / std)
    sharpe = expectancy / std if std > 0 else 0

    # Max losing streak
    max_streak = 0
    current_streak = 0
    for r in r_multiples:
        if r <= 0:
            current_streak += 1
            max_streak = max(max_streak, current_streak)
        else:
            current_streak = 0

    # Max winning streak
    max_win_streak = 0
    cur_win_streak = 0
    for r in r_multiples:
        if r > 0:
            cur_win_streak += 1
            max_win_streak = max(max_win_streak, cur_win_streak)
        else:
            cur_win_streak = 0

    # Average hold time (if timestamps available)
    hold_times = []
    for t in trade_log:
        if t.get("open_timestamp") and t.get("close_timestamp"):
            try:
                from backend.core.time_utils import parse_utc
                open_dt = parse_utc(t["open_timestamp"])
                close_dt = parse_utc(t["close_timestamp"])
                hold_times.append((close_dt - open_dt).total_seconds() / 3600)
            except Exception:
                pass
    avg_hold_hours = sum(hold_times) / len(hold_times) if hold_times else None

    # Breakdown by strategy
    by_strategy = {}
    for t in trade_log:
        strat = t.get("strategy", "unknown")
        if strat not in by_strategy:
            by_strategy[strat] = []
        if t.get("r_multiple") is not None:
            by_strategy[strat].append(t["r_multiple"])

    strategy_breakdown = {}
    for strat, rs in by_strategy.items():
        if rs:
            w = [r for r in rs if r > 0]
            l = [r for r in rs if r <= 0]
            strategy_breakdown[strat] = {
                "trades": len(rs),
                "win_rate": round(len(w) / len(rs), 4),
                "expectancy": round(
                    (len(w) / len(rs)) * (sum(w) / len(w) if w else 0) -
                    (len(l) / len(rs)) * (abs(sum(l) / len(l)) if l else 0), 4
                ),
                "total_r": round(sum(rs), 2),
            }

    # Breakdown by exit reason
    by_exit = {}
    for t in trade_log:
        reason = t.get("exit_reason", "unknown")
        if reason not in by_exit:
            by_exit[reason] = 0
        by_exit[reason] += 1

    # CI for win rate
    se = math.sqrt(win_rate * (1 - win_rate) / n) if n > 0 else 0
    ci_low = max(0, win_rate - 1.96 * se)
    ci_high = min(1, win_rate + 1.96 * se)

    return {
        "total_trades": len(trade_log),
        "closed_trades": n,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": round(win_rate, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
        "avg_win_r": round(avg_win, 2),
        "avg_loss_r": round(avg_loss, 2),
        "expectancy": round(expectancy, 4),
        "profit_factor": round(pf, 2) if pf != float('inf') else "Infinity",
        "sharpe": round(sharpe, 2),
        "std_dev": round(std, 4),
        "max_drawdown_r": round(max_dd, 2),
        "max_losing_streak": max_streak,
        "max_winning_streak": max_win_streak,
        "avg_hold_hours": round(avg_hold_hours, 1) if avg_hold_hours else None,
        "equity_curve": curve,
        "r_multiples": r_multiples,
        "by_strategy": strategy_breakdown,
        "by_exit_reason": by_exit,
        "total_r": round(sum(r_multiples), 2),
    }
