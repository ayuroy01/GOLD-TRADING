"""
Trend Pullback Continuation Strategy.

Hypothesis: In an established trend, pullbacks to the fast MA offer
continuation entries with favorable risk:reward.

Entry: Price pulls back to near the 10-period SMA in an uptrend/downtrend
       and shows signs of continuation.
Stop: Below the most recent swing low (longs) or above swing high (shorts).
Target: Recent swing high extension (longs) or swing low extension (shorts).
"""

from typing import List
from backend.strategies.base import BaseStrategy, SetupResult
from backend.features.market_features import compute_atr


class TrendPullbackStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "trend_pullback"

    @property
    def required_timeframes(self) -> List[str]:
        return ["1h", "4h"]

    @property
    def allowed_sessions(self) -> List[str]:
        return ["london", "overlap", "new_york"]

    def evaluate(self, features: dict, candles: dict) -> SetupResult:
        trend_1h = features.get("trend_1h", "ranging")
        trend_4h = features.get("trend_4h")
        price = features.get("price", 0)
        atr = features.get("atr_14", 0)
        session = features.get("session", "off_hours")
        swing_lows = features.get("swing_lows", [])
        swing_highs = features.get("swing_highs", [])

        candles_1h = candles.get("1h", [])

        # Must be in a trending session
        if session not in self.allowed_sessions:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Session '{session}' not allowed",
            )

        # Need a clear trend on 1h
        if trend_1h == "ranging":
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason="No clear 1h trend (ranging)",
            )

        # Prefer trend alignment across timeframes
        trend_aligned = trend_4h is None or trend_4h == trend_1h

        # Check for pullback to fast MA
        if len(candles_1h) < 10:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason="Insufficient candle data",
            )

        fast_ma = sum(c["close"] for c in candles_1h[-10:]) / 10
        dist_to_ma = abs(price - fast_ma)
        ma_proximity = dist_to_ma <= atr * 0.5 if atr > 0 else False

        if not ma_proximity:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Price ${price:.2f} not near 10-SMA ${fast_ma:.2f} (dist: {dist_to_ma:.2f}, threshold: {atr*0.5:.2f})",
            )

        # Determine direction and levels
        if trend_1h == "uptrend":
            direction = "long"
            stop = swing_lows[-1] - atr * 0.2 if swing_lows else price - atr * 1.5
            entry = price
            target_1 = swing_highs[-1] + atr * 0.5 if swing_highs else price + atr * 2.0
            target_2 = price + atr * 3.0
        else:  # downtrend
            direction = "short"
            stop = swing_highs[-1] + atr * 0.2 if swing_highs else price + atr * 1.5
            entry = price
            target_1 = swing_lows[-1] - atr * 0.5 if swing_lows else price - atr * 2.0
            target_2 = price - atr * 3.0

        rr = self._compute_rr(entry, stop, target_1)

        if rr < self.min_risk_reward:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"R:R {rr:.2f} below minimum {self.min_risk_reward}",
            )

        # Quality scoring
        quality = 0.0
        rationale = []

        if trend_aligned:
            quality += 0.3
            rationale.append("Multi-timeframe trend alignment")
        if ma_proximity:
            quality += 0.25
            rationale.append(f"Price at 10-SMA pullback zone (dist: {dist_to_ma:.2f})")
        if features.get("volatility_regime") == "normal":
            quality += 0.15
            rationale.append("Normal volatility regime")
        if features.get("gold_macro_bias") == ("bullish" if direction == "long" else "bearish"):
            quality += 0.2
            rationale.append("Macro bias aligned with direction")
        if rr >= 2.0:
            quality += 0.1
            rationale.append(f"Good R:R of {rr:.2f}")

        confidence = min(85, int(quality * 100))

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
