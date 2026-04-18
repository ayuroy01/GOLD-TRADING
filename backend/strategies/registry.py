"""
Strategy registry — manages all available strategies and evaluates them.
"""

from typing import List, Dict
from backend.strategies.base import BaseStrategy, SetupResult
from backend.strategies.trend_pullback import TrendPullbackStrategy
from backend.strategies.range_reversion import RangeReversionStrategy
from backend.strategies.breakout_compression import BreakoutCompressionStrategy


class StrategyRegistry:
    """Registry of all trading strategies.
    Evaluates each strategy against current market features and returns
    ranked candidate setups.
    """

    def __init__(self):
        self._strategies: Dict[str, BaseStrategy] = {}
        self._register_defaults()

    def _register_defaults(self):
        for s in [
            TrendPullbackStrategy(),
            RangeReversionStrategy(),
            BreakoutCompressionStrategy(),
        ]:
            self.register(s)

    def register(self, strategy: BaseStrategy):
        self._strategies[strategy.name] = strategy

    def get(self, name: str) -> BaseStrategy:
        return self._strategies.get(name)

    def list_strategies(self) -> List[str]:
        return list(self._strategies.keys())

    def evaluate_all(self, features: dict, candles: dict) -> List[SetupResult]:
        """Evaluate all registered strategies and return results sorted by quality."""
        results = []
        for name, strategy in self._strategies.items():
            try:
                result = strategy.evaluate(features, candles)
                results.append(result)
            except Exception as e:
                results.append(SetupResult(
                    strategy_name=name, valid=False,
                    invalidation_reason=f"Evaluation error: {str(e)}",
                ))
        # Sort: valid first, then by quality_score descending
        results.sort(key=lambda r: (r.valid, r.quality_score), reverse=True)
        return results

    def get_valid_setups(self, features: dict, candles: dict) -> List[SetupResult]:
        """Return only valid setups, ranked by quality."""
        return [r for r in self.evaluate_all(features, candles) if r.valid]

    def get_best_setup(self, features: dict, candles: dict) -> SetupResult:
        """Return the highest-quality valid setup, or None."""
        valid = self.get_valid_setups(features, candles)
        return valid[0] if valid else None
