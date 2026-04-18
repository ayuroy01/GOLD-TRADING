"""
Macroeconomic context provider interface and simulated implementation.
"""

import abc
import hashlib
from backend.core.time_utils import now_utc, utc_timestamp


class MacroProvider(abc.ABC):
    """Abstract interface for macro context data."""

    @abc.abstractmethod
    def get_macro_context(self) -> dict:
        """Get macroeconomic context.
        Returns: {usd_index, usd_regime, treasury_10y, rate_direction,
                  gold_macro_bias, geopolitical_risk, ...}
        """


class SimulatedMacroProvider(MacroProvider):
    """Simulated macro provider using time-based hashing for stable hourly values."""

    def get_macro_context(self) -> dict:
        now = now_utc()
        h = int(hashlib.md5(now.strftime("%Y-%m-%d-%H").encode()).hexdigest()[:8], 16)

        dxy_base = 104.5
        dxy = round(dxy_base + ((h % 400) - 200) / 100, 2)
        rate_10y = round(4.25 + ((h % 100) - 50) / 200, 3)

        if dxy > 105:
            usd_regime = "strong"
            gold_bias = "bearish"
        elif dxy < 103:
            usd_regime = "weak"
            gold_bias = "bullish"
        else:
            usd_regime = "neutral"
            gold_bias = "neutral"

        return {
            "timestamp": utc_timestamp(),
            "usd_index": dxy,
            "usd_regime": usd_regime,
            "treasury_10y": rate_10y,
            "rate_direction": "rising" if rate_10y > 4.3 else "falling" if rate_10y < 4.2 else "stable",
            "gold_macro_bias": gold_bias,
            "geopolitical_risk": "elevated" if (h % 3 == 0) else "moderate",
            "inflation_expectation": "above_target",
            "vix_regime": "low_vol" if (h % 4 != 0) else "elevated",
            "source": "simulated",
        }
