"""
Range Fade / Mean Reversion Strategy.

Hypothesis: In a ranging market, price tends to revert to the mean when
it reaches the extremes of the recent range.

Entry: Price near the top/bottom of the 20-period range.
Stop: Beyond the range extreme + ATR buffer.
Target: Opposite side of range (or midpoint for partial).
"""

from typing import List
from backend.strategies.base import BaseStrategy, SetupResult
from backend.features.market_features import compute_atr


class RangeReversionStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "range_reversion"

    @property
    def required_timeframes(self) -> List[str]:
        return ["1h"]

    @property
    def allowed_sessions(self) -> List[str]:
        return ["london", "overlap", "new_york", "asia"]

    def evaluate(self, features: dict, candles: dict) -> SetupResult:
        trend_1h = features.get("trend_1h", "ranging")
        price = features.get("price", 0)
        atr = features.get("atr_14", 0)
        session = features.get("session", "off_hours")
        rolling_high = features.get("rolling_high_20", 0)
        rolling_low = features.get("rolling_low_20", 0)

        if session not in self.allowed_sessions:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Session '{session}' not allowed",
            )

        # Strategy requires a ranging market
        if trend_1h != "ranging":
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Market is trending ({trend_1h}), not ranging",
            )

        range_size = rolling_high - rolling_low
        if range_size <= 0 or atr <= 0:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason="Invalid range or ATR",
            )

        # Need meaningful range (at least 2x ATR)
        if range_size < atr * 2:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Range too tight ({range_size:.2f} < {atr*2:.2f})",
            )

        # Position within range (0 = bottom, 1 = top)
        range_position = (price - rolling_low) / range_size

        direction = None
        entry = price
        stop = None
        target_1 = None
        target_2 = None
        rationale = []

        # Near top of range -> short (fade)
        if range_position > 0.85:
            direction = "short"
            stop = rolling_high + atr * 0.3
            midpoint = (rolling_high + rolling_low) / 2
            target_1 = midpoint
            target_2 = rolling_low + atr * 0.3
            rationale.append(f"Price at {range_position:.0%} of range (near top)")
            rationale.append(f"Fading toward range midpoint ${midpoint:.2f}")

        # Near bottom of range -> long (fade)
        elif range_position < 0.15:
            direction = "long"
            stop = rolling_low - atr * 0.3
            midpoint = (rolling_high + rolling_low) / 2
            target_1 = midpoint
            target_2 = rolling_high - atr * 0.3
            rationale.append(f"Price at {range_position:.0%} of range (near bottom)")
            rationale.append(f"Fading toward range midpoint ${midpoint:.2f}")

        else:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Price at {range_position:.0%} of range — not at extremes",
            )

        rr = self._compute_rr(entry, stop, target_1)

        if rr < self.min_risk_reward:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"R:R {rr:.2f} below minimum {self.min_risk_reward}",
            )

        # Quality scoring
        quality = 0.0
        if range_position > 0.9 or range_position < 0.1:
            quality += 0.3
            rationale.append("Price at extreme of range")
        else:
            quality += 0.15
        if range_size >= atr * 3:
            quality += 0.2
            rationale.append("Wide range provides room for mean reversion")
        if features.get("volatility_regime") in ("low", "normal"):
            quality += 0.15
            rationale.append("Low/normal volatility supports mean reversion")
        if not features.get("news_blackout"):
            quality += 0.1
        if rr >= 2.0:
            quality += 0.15
            rationale.append(f"Good R:R of {rr:.2f}")

        confidence = min(80, int(quality * 100))

        return SetupResult(
            strategy_name=self.name,
            valid=True,
            direction=direction,
            entry=round(entry, 2),
            stop=round(stop, 2),
            target_1=round(target_1, 2),
            target_2=round(target_2, 2),
            risk_reward=rr,
            confidence=confidence,
            quality_score=round(quality, 2),
            rationale=rationale,
            allowed_sessions=self.allowed_sessions,
        )
