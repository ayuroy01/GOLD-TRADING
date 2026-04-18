"""
Breakout After Compression Strategy.

Hypothesis: Periods of low volatility (compression) precede expansion moves.
A breakout from a tight range after compression offers a momentum entry.

Entry: Price breaks above/below a tight range with increased ATR.
Stop: Opposite side of the compression range.
Target: ATR-based extension from breakout level.
"""

from typing import List
from backend.strategies.base import BaseStrategy, SetupResult
from backend.features.market_features import compute_atr


class BreakoutCompressionStrategy(BaseStrategy):

    @property
    def name(self) -> str:
        return "breakout_compression"

    @property
    def required_timeframes(self) -> List[str]:
        return ["1h"]

    @property
    def allowed_sessions(self) -> List[str]:
        return ["london", "overlap"]

    def evaluate(self, features: dict, candles: dict) -> SetupResult:
        price = features.get("price", 0)
        atr = features.get("atr_14", 0)
        vol_regime = features.get("volatility_regime", "normal")
        session = features.get("session", "off_hours")
        rolling_high = features.get("rolling_high_20", 0)
        rolling_low = features.get("rolling_low_20", 0)

        candles_1h = candles.get("1h", [])

        if session not in self.allowed_sessions:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"Session '{session}' not allowed for breakout strategy",
            )

        if len(candles_1h) < 20:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason="Insufficient candle data",
            )

        # Look for compression: recent range should be tight
        recent_5 = candles_1h[-5:]
        recent_high = max(c["high"] for c in recent_5)
        recent_low = min(c["low"] for c in recent_5)
        compression_range = recent_high - recent_low

        # Compression if recent 5-candle range is < 1x ATR
        is_compressed = compression_range < atr * 1.0 if atr > 0 else False

        # Check for breakout: current price outside the compression range
        breakout_up = price > recent_high and is_compressed
        breakout_down = price < recent_low and is_compressed

        if not breakout_up and not breakout_down:
            reason = "No compression breakout detected"
            if not is_compressed:
                reason = f"Not compressed (5-bar range {compression_range:.2f} >= ATR {atr:.2f})"
            elif price <= recent_high and price >= recent_low:
                reason = f"Price ${price:.2f} still within compression range [${recent_low:.2f}, ${recent_high:.2f}]"
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=reason,
            )

        if breakout_up:
            direction = "long"
            entry = price
            stop = recent_low - atr * 0.2
            target_1 = entry + atr * 2.0
            target_2 = entry + atr * 3.0
        else:
            direction = "short"
            entry = price
            stop = recent_high + atr * 0.2
            target_1 = entry - atr * 2.0
            target_2 = entry - atr * 3.0

        rr = self._compute_rr(entry, stop, target_1)

        if rr < self.min_risk_reward:
            return SetupResult(
                strategy_name=self.name, valid=False,
                invalidation_reason=f"R:R {rr:.2f} below minimum {self.min_risk_reward}",
            )

        # Quality scoring
        quality = 0.0
        rationale = []

        rationale.append(f"Compression detected: 5-bar range {compression_range:.2f} < ATR {atr:.2f}")
        quality += 0.25

        if vol_regime == "low":
            quality += 0.2
            rationale.append("Low volatility regime supports breakout potential")
        elif vol_regime == "normal":
            quality += 0.1

        # Breakout distance
        if breakout_up:
            breakout_dist = price - recent_high
        else:
            breakout_dist = recent_low - price
        if breakout_dist > 0:
            quality += 0.15
            rationale.append(f"Breakout confirmed by ${breakout_dist:.2f}")

        if features.get("gold_macro_bias") == ("bullish" if direction == "long" else "bearish"):
            quality += 0.15
            rationale.append("Macro alignment with breakout direction")

        if session in ("london", "overlap"):
            quality += 0.15
            rationale.append(f"High-liquidity session: {session}")

        if rr >= 2.0:
            quality += 0.1
            rationale.append(f"Strong R:R of {rr:.2f}")

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
