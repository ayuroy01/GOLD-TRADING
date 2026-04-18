"""
Strategy base class and setup definition.
All strategies must subclass BaseStrategy and implement evaluate().
"""

import abc
from typing import List, Optional


class SetupResult:
    """Represents a candidate trade setup from a strategy evaluation."""

    def __init__(
        self,
        strategy_name: str,
        valid: bool,
        direction: Optional[str] = None,
        entry: Optional[float] = None,
        stop: Optional[float] = None,
        target_1: Optional[float] = None,
        target_2: Optional[float] = None,
        risk_reward: Optional[float] = None,
        confidence: int = 0,
        quality_score: float = 0.0,
        invalidation_reason: Optional[str] = None,
        rationale: Optional[List[str]] = None,
        allowed_sessions: Optional[List[str]] = None,
    ):
        self.strategy_name = strategy_name
        self.valid = valid
        self.direction = direction
        self.entry = entry
        self.stop = stop
        self.target_1 = target_1
        self.target_2 = target_2
        self.risk_reward = risk_reward
        self.confidence = confidence
        self.quality_score = quality_score
        self.invalidation_reason = invalidation_reason
        self.rationale = rationale or []
        self.allowed_sessions = allowed_sessions or ["london", "overlap", "new_york"]

    def to_dict(self) -> dict:
        return {
            "strategy_name": self.strategy_name,
            "valid": self.valid,
            "direction": self.direction,
            "entry": self.entry,
            "stop": self.stop,
            "target_1": self.target_1,
            "target_2": self.target_2,
            "risk_reward": self.risk_reward,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "invalidation_reason": self.invalidation_reason,
            "rationale": self.rationale,
            "allowed_sessions": self.allowed_sessions,
        }


class BaseStrategy(abc.ABC):
    """Abstract base class for all trading strategies."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Unique strategy name."""

    @property
    @abc.abstractmethod
    def required_timeframes(self) -> List[str]:
        """Timeframes required for this strategy (e.g. ['1h', '4h'])."""

    @property
    def allowed_sessions(self) -> List[str]:
        """Sessions during which this strategy is allowed."""
        return ["london", "overlap", "new_york"]

    @property
    def min_risk_reward(self) -> float:
        """Minimum R:R required for a valid setup."""
        return 1.5

    @abc.abstractmethod
    def evaluate(self, features: dict, candles: dict) -> SetupResult:
        """Evaluate current market state for this strategy.
        Args:
            features: dict from compute_all_features()
            candles: dict of {timeframe: [candle_list]} for required timeframes
        Returns:
            SetupResult indicating whether a valid setup exists.
        """

    def _compute_rr(self, entry: float, stop: float, target: float) -> float:
        """Compute risk:reward ratio."""
        risk = abs(entry - stop)
        reward = abs(target - entry)
        return round(reward / risk, 2) if risk > 0 else 0.0
