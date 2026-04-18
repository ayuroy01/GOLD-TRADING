"""
Risk management engine.
Enforces all risk rules as a first-class gating layer.
If any rule blocks, the action becomes NO_TRADE with a stored reason.
"""

from typing import List, Optional
from backend.core.time_utils import now_utc, is_weekend, is_friday_late, get_session


class RiskBlocker:
    """Represents a single risk rule violation that blocks trading."""

    def __init__(self, rule: str, reason: str, severity: str = "hard"):
        self.rule = rule
        self.reason = reason
        self.severity = severity  # "hard" = blocks trade, "soft" = warning only

    def to_dict(self) -> dict:
        return {"rule": self.rule, "reason": self.reason, "severity": self.severity}


class RiskConfig:
    """Risk management configuration with sensible defaults."""

    def __init__(self, **kwargs):
        self.risk_per_trade_pct: float = kwargs.get("risk_pct", 1.0)
        self.max_positions: int = kwargs.get("max_positions", 2)
        self.max_daily_loss_pct: float = kwargs.get("max_daily_loss_pct", 3.0)
        self.max_drawdown_pct: float = kwargs.get("max_drawdown_pct", 5.0)
        self.max_trades_per_day: int = kwargs.get("max_trades_per_day", 5)
        self.friday_cutoff_hour: int = kwargs.get("friday_cutoff_hour", 18)
        self.cooloff_after_losses: int = kwargs.get("cooloff_after_losses", 3)
        self.max_spread: float = kwargs.get("max_spread", 0.60)
        self.min_risk_reward: float = kwargs.get("min_risk_reward", 1.5)
        self.min_confidence: int = kwargs.get("min_confidence", 50)
        self.stale_data_seconds: int = kwargs.get("stale_data_seconds", 300)
        self.safe_mode: bool = kwargs.get("safe_mode", False)

    @classmethod
    def from_settings(cls, settings: dict) -> "RiskConfig":
        return cls(**settings)

    def to_dict(self) -> dict:
        return {
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "max_positions": self.max_positions,
            "max_daily_loss_pct": self.max_daily_loss_pct,
            "max_drawdown_pct": self.max_drawdown_pct,
            "max_trades_per_day": self.max_trades_per_day,
            "friday_cutoff_hour": self.friday_cutoff_hour,
            "cooloff_after_losses": self.cooloff_after_losses,
            "max_spread": self.max_spread,
            "min_risk_reward": self.min_risk_reward,
            "min_confidence": self.min_confidence,
            "safe_mode": self.safe_mode,
        }


class RiskEngine:
    """Evaluates all risk rules and returns blockers.
    If any hard blocker exists, trading is not allowed.
    """

    def __init__(self, config: RiskConfig = None):
        self.config = config or RiskConfig()

    def evaluate(self, features: dict, setup: dict = None) -> List[RiskBlocker]:
        """Evaluate all risk rules against current features and optional setup.

        Args:
            features: dict from compute_all_features()
            setup: optional SetupResult.to_dict() for the candidate trade

        Returns:
            List of RiskBlocker objects. Empty list means trading is allowed.
        """
        blockers = []

        # Kill switch
        if self.config.safe_mode:
            blockers.append(RiskBlocker(
                "safe_mode", "Safe mode is enabled — all trading blocked"
            ))

        # Weekend
        if features.get("is_weekend"):
            blockers.append(RiskBlocker(
                "weekend", "Weekend — market closed"
            ))

        # Friday late cutoff
        if features.get("is_friday_late"):
            blockers.append(RiskBlocker(
                "friday_cutoff",
                f"Friday after {self.config.friday_cutoff_hour}:00 UTC — weekend gap risk"
            ))

        # Session check
        session = features.get("session", "off_hours")
        if session == "off_hours":
            blockers.append(RiskBlocker(
                "session", "Outside active trading sessions"
            ))

        # News blackout
        if features.get("news_blackout"):
            blockers.append(RiskBlocker(
                "news_blackout", "High-impact news within 2 hours"
            ))

        # Spread too wide
        spread = features.get("spread", 0)
        if spread > self.config.max_spread:
            blockers.append(RiskBlocker(
                "spread",
                f"Spread ${spread:.2f} exceeds maximum ${self.config.max_spread:.2f}"
            ))

        # Max open positions
        open_pos = features.get("open_positions", 0)
        if open_pos >= self.config.max_positions:
            blockers.append(RiskBlocker(
                "max_positions",
                f"Already holding {open_pos} positions (max {self.config.max_positions})"
            ))

        # Max daily trades
        trades_today = features.get("trades_today", 0)
        if trades_today >= self.config.max_trades_per_day:
            blockers.append(RiskBlocker(
                "max_daily_trades",
                f"Already {trades_today} trades today (max {self.config.max_trades_per_day})"
            ))

        # Account drawdown
        dd = features.get("current_drawdown_pct", 0)
        if dd > self.config.max_drawdown_pct:
            blockers.append(RiskBlocker(
                "max_drawdown",
                f"Account drawdown {dd:.1f}% exceeds {self.config.max_drawdown_pct}% limit"
            ))

        # Daily loss
        equity = features.get("equity", 50000)
        daily_pnl = features.get("daily_pnl", 0)
        if equity > 0 and daily_pnl < 0:
            daily_loss_pct = abs(daily_pnl) / equity * 100
            if daily_loss_pct > self.config.max_daily_loss_pct:
                blockers.append(RiskBlocker(
                    "max_daily_loss",
                    f"Daily loss {daily_loss_pct:.1f}% exceeds {self.config.max_daily_loss_pct}% limit"
                ))

        # Consecutive losses cooloff
        consec_losses = features.get("consecutive_losses", 0)
        if consec_losses >= self.config.cooloff_after_losses > 0:
            blockers.append(RiskBlocker(
                "loss_cooloff",
                f"{consec_losses} consecutive losses — cooloff active (threshold: {self.config.cooloff_after_losses})"
            ))

        # Setup-specific checks
        if setup:
            rr = setup.get("risk_reward", 0)
            if rr and rr < self.config.min_risk_reward:
                blockers.append(RiskBlocker(
                    "min_rr",
                    f"R:R {rr:.2f} below minimum {self.config.min_risk_reward}"
                ))

            conf = setup.get("confidence", 0)
            if conf < self.config.min_confidence:
                blockers.append(RiskBlocker(
                    "min_confidence",
                    f"Confidence {conf} below minimum {self.config.min_confidence}"
                ))

        return blockers

    def is_allowed(self, features: dict, setup: dict = None) -> tuple:
        """Check if trading is allowed.
        Returns: (allowed: bool, blockers: List[RiskBlocker])
        """
        blockers = self.evaluate(features, setup)
        hard_blockers = [b for b in blockers if b.severity == "hard"]
        return len(hard_blockers) == 0, blockers

    def compute_position_size(self, equity: float, entry: float, stop: float) -> dict:
        """Compute position size based on risk parameters.
        Returns: {risk_usd, risk_distance, position_oz, position_lots}
        """
        risk_usd = equity * (self.config.risk_per_trade_pct / 100)
        risk_distance = abs(entry - stop)
        if risk_distance <= 0:
            return {"risk_usd": 0, "risk_distance": 0, "position_oz": 0, "position_lots": 0}

        position_oz = risk_usd / risk_distance
        position_lots = position_oz / 100  # 1 lot = 100 oz for XAU/USD

        return {
            "risk_usd": round(risk_usd, 2),
            "risk_distance": round(risk_distance, 2),
            "position_oz": round(position_oz, 2),
            "position_lots": round(position_lots, 3),
        }
