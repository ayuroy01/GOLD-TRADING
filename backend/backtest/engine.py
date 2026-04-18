"""
Backtesting engine — replays historical candles through strategy evaluation,
simulates fills and position management, and computes performance metrics.
"""

import math
from typing import List, Dict, Optional
from backend.features.market_features import compute_all_features, compute_atr, compute_trend_regime, compute_rolling_high, compute_rolling_low, compute_volatility_regime, compute_support_resistance, compute_spread_regime
from backend.strategies.base import SetupResult
from backend.strategies.registry import StrategyRegistry
from backend.backtest.metrics import compute_backtest_metrics
from backend.core.time_utils import parse_utc, get_session, is_weekend, is_friday_late


class BacktestPosition:
    """Represents a simulated position during backtesting."""

    def __init__(self, direction: str, entry: float, stop: float,
                 target_1: float, target_2: float = None,
                 strategy: str = "", timestamp: str = ""):
        self.direction = direction
        self.entry = entry
        self.stop = stop
        self.target_1 = target_1
        self.target_2 = target_2
        self.strategy = strategy
        self.open_timestamp = timestamp
        self.close_timestamp = ""
        self.exit_price = None
        self.exit_reason = ""
        self.r_multiple = None

    def check_exit(self, candle: dict, spread: float = 0.40) -> bool:
        """Check if the position should be closed based on candle OHLC.
        Applies spread to simulate realistic fills.
        Returns True if position was closed."""
        h = candle["high"]
        l = candle["low"]

        if self.direction == "long":
            # Check stop first (worst-case: stop hit before target in same bar)
            if l <= self.stop:
                self.exit_price = self.stop - spread / 2  # slippage
                self.exit_reason = "stop_loss"
                self.close_timestamp = candle["timestamp"]
                self._compute_r()
                return True
            # Check target
            if h >= self.target_1:
                self.exit_price = self.target_1 - spread / 2
                self.exit_reason = "target_1"
                self.close_timestamp = candle["timestamp"]
                self._compute_r()
                return True
        else:  # short
            if h >= self.stop:
                self.exit_price = self.stop + spread / 2
                self.exit_reason = "stop_loss"
                self.close_timestamp = candle["timestamp"]
                self._compute_r()
                return True
            if l <= self.target_1:
                self.exit_price = self.target_1 + spread / 2
                self.exit_reason = "target_1"
                self.close_timestamp = candle["timestamp"]
                self._compute_r()
                return True

        return False

    def _compute_r(self):
        if self.exit_price is None:
            return
        risk = abs(self.entry - self.stop)
        if risk == 0:
            self.r_multiple = 0
            return
        if self.direction == "long":
            self.r_multiple = round((self.exit_price - self.entry) / risk, 2)
        else:
            self.r_multiple = round((self.entry - self.exit_price) / risk, 2)

    def to_dict(self) -> dict:
        return {
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "strategy": self.strategy,
            "open_timestamp": self.open_timestamp,
            "close_timestamp": self.close_timestamp,
            "exit_price": self.exit_price,
            "exit_reason": self.exit_reason,
            "r_multiple": self.r_multiple,
        }


class BacktestEngine:
    """Replays historical candles through strategies and simulates trading."""

    def __init__(
        self,
        strategy_registry: StrategyRegistry = None,
        spread: float = 0.40,
        max_positions: int = 2,
        max_trades_per_day: int = 5,
    ):
        self.registry = strategy_registry or StrategyRegistry()
        self.spread = spread
        self.max_positions = max_positions
        self.max_trades_per_day = max_trades_per_day

    def run(
        self,
        candles_1h: List[dict],
        candles_15m: List[dict] = None,
        candles_4h: List[dict] = None,
        macro: dict = None,
        calendar: dict = None,
        warmup: int = 30,
    ) -> dict:
        """Run a backtest over the provided candle data.

        Args:
            candles_1h: Primary 1-hour candles (required)
            candles_15m: Optional 15-minute candles
            candles_4h: Optional 4-hour candles
            macro: Static macro context (or simulated)
            calendar: Static calendar context (or simulated)
            warmup: Number of initial candles to skip for indicator warmup

        Returns:
            dict with trade_log, metrics, and metadata
        """
        if macro is None:
            macro = {"usd_regime": "neutral", "gold_macro_bias": "neutral",
                     "geopolitical_risk": "moderate", "vix_regime": "low_vol"}
        if calendar is None:
            calendar = {"high_impact_within_2h": False, "nearest_high_impact": None}

        open_positions: List[BacktestPosition] = []
        closed_trades: List[dict] = []
        daily_trade_count = {}
        current_day = None

        for i in range(warmup, len(candles_1h)):
            candle = candles_1h[i]
            history = candles_1h[:i]  # No lookahead

            # Parse timestamp for session/time checks
            try:
                dt = parse_utc(candle["timestamp"])
            except Exception:
                continue

            day_key = dt.strftime("%Y-%m-%d")
            if day_key != current_day:
                current_day = day_key
                daily_trade_count[day_key] = daily_trade_count.get(day_key, 0)

            # Check open positions for exits
            still_open = []
            for pos in open_positions:
                if pos.check_exit(candle, self.spread):
                    closed_trades.append(pos.to_dict())
                else:
                    still_open.append(pos)
            open_positions = still_open

            # Skip if at capacity or time restrictions
            if len(open_positions) >= self.max_positions:
                continue
            if daily_trade_count.get(day_key, 0) >= self.max_trades_per_day:
                continue
            if is_weekend(dt) or is_friday_late(dt):
                continue

            # Build features from available history (no lookahead)
            price = candle["close"]
            quote = {
                "price": price,
                "spread": self.spread,
                "source": "backtest",
            }

            # Get matching candles for other timeframes (up to current time)
            candles_15m_avail = None
            candles_4h_avail = None
            if candles_15m:
                candles_15m_avail = [c for c in candles_15m
                                     if c["timestamp"] <= candle["timestamp"]]
            if candles_4h:
                candles_4h_avail = [c for c in candles_4h
                                    if c["timestamp"] <= candle["timestamp"]]

            features = compute_all_features(
                candles_1h=history,
                quote=quote,
                macro=macro,
                calendar=calendar,
                candles_15m=candles_15m_avail,
                candles_4h=candles_4h_avail,
                dt=dt,
            )

            candles_dict = {"1h": history}
            if candles_15m_avail:
                candles_dict["15m"] = candles_15m_avail
            if candles_4h_avail:
                candles_dict["4h"] = candles_4h_avail

            # Evaluate strategies
            best = self.registry.get_best_setup(features, candles_dict)
            if best and best.valid and best.entry and best.stop and best.target_1:
                # Apply spread to entry
                if best.direction == "long":
                    fill_price = best.entry + self.spread / 2
                else:
                    fill_price = best.entry - self.spread / 2

                pos = BacktestPosition(
                    direction=best.direction,
                    entry=round(fill_price, 2),
                    stop=round(best.stop, 2),
                    target_1=round(best.target_1, 2),
                    target_2=round(best.target_2, 2) if best.target_2 else None,
                    strategy=best.strategy_name,
                    timestamp=candle["timestamp"],
                )
                open_positions.append(pos)
                daily_trade_count[day_key] = daily_trade_count.get(day_key, 0) + 1

        # Force-close any remaining open positions at last candle close
        if open_positions and candles_1h:
            last_candle = candles_1h[-1]
            for pos in open_positions:
                pos.exit_price = last_candle["close"]
                pos.exit_reason = "end_of_backtest"
                pos.close_timestamp = last_candle["timestamp"]
                pos._compute_r()
                closed_trades.append(pos.to_dict())

        # Compute metrics
        metrics = compute_backtest_metrics(closed_trades)

        return {
            "trade_log": closed_trades,
            "metrics": metrics,
            "total_candles": len(candles_1h),
            "warmup_candles": warmup,
            "evaluated_candles": len(candles_1h) - warmup,
            "spread_assumption": self.spread,
            "strategies_used": self.registry.list_strategies(),
        }


def run_walk_forward(
    candles_1h: List[dict],
    train_ratio: float = 0.7,
    n_folds: int = 3,
    registry: StrategyRegistry = None,
    spread: float = 0.40,
) -> dict:
    """Walk-forward analysis: split data into folds, train/test on each.
    Since our strategies are rule-based (no fitting), this mainly validates
    out-of-sample stability.

    Returns per-fold and aggregate metrics.
    """
    if registry is None:
        registry = StrategyRegistry()

    total = len(candles_1h)
    fold_size = total // n_folds
    results = []

    for fold in range(n_folds):
        start = fold * fold_size
        end = min(start + fold_size, total)
        fold_candles = candles_1h[start:end]

        split = int(len(fold_candles) * train_ratio)
        train_candles = fold_candles[:split]
        test_candles = fold_candles[split:]

        # Run backtest on train set
        engine = BacktestEngine(strategy_registry=registry, spread=spread)
        train_result = engine.run(train_candles, warmup=min(30, len(train_candles) // 3))

        # Run backtest on test set (out-of-sample)
        test_result = engine.run(test_candles, warmup=min(30, len(test_candles) // 3))

        results.append({
            "fold": fold + 1,
            "train_candles": len(train_candles),
            "test_candles": len(test_candles),
            "train_metrics": train_result["metrics"],
            "test_metrics": test_result["metrics"],
            "train_trades": len(train_result["trade_log"]),
            "test_trades": len(test_result["trade_log"]),
        })

    # Aggregate OOS metrics
    oos_r_multiples = []
    for r in results:
        tm = r["test_metrics"]
        if tm.get("r_multiples"):
            oos_r_multiples.extend(tm["r_multiples"])

    aggregate_oos = compute_backtest_metrics(
        [{"r_multiple": r} for r in oos_r_multiples]
    ) if oos_r_multiples else {}

    return {
        "folds": results,
        "aggregate_oos_metrics": aggregate_oos,
        "n_folds": n_folds,
        "train_ratio": train_ratio,
    }
