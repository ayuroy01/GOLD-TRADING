"""
Decision memory store — persists every decision with its full context
for analysis, learning, and auditability.
"""

import json
from pathlib import Path
from typing import List, Optional
from backend.core.time_utils import utc_timestamp


class DecisionStore:
    """Stores decision snapshots with full audit trail."""

    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.decisions_file = data_dir / "decisions.json"

    def _load(self) -> List[dict]:
        try:
            if self.decisions_file.exists():
                return json.loads(self.decisions_file.read_text())
        except Exception:
            pass
        return []

    def _save(self, decisions: List[dict]):
        self.decisions_file.write_text(
            json.dumps(decisions[-1000:], indent=2, default=str)  # Keep last 1000
        )

    def store(self, decision_result: dict, outcome: dict = None) -> dict:
        """Store a decision from the decision engine.

        Args:
            decision_result: full output from DecisionEngine.decide()
            outcome: optional trade outcome if already known
        """
        record = {
            "id": decision_result.get("decision_id"),
            "timestamp": decision_result.get("timestamp", utc_timestamp()),
            "decision": decision_result.get("decision"),
            "trade_or_no_trade": decision_result.get("trade_or_no_trade"),
            "strategy": decision_result.get("strategy"),
            "confidence": decision_result.get("confidence"),
            "setups_evaluated": decision_result.get("setups_evaluated"),
            "risk_blockers": decision_result.get("risk_blockers"),
            "claude_used": decision_result.get("claude_used", False),
            "claude_raw_response": decision_result.get("claude_raw_response"),
            "claude_error": decision_result.get("claude_error"),
            "features_snapshot": decision_result.get("features_snapshot"),
            "outcome": outcome,
        }

        decisions = self._load()
        decisions.append(record)
        self._save(decisions)
        return record

    def update_outcome(self, decision_id: str, outcome: dict) -> Optional[dict]:
        """Attach an outcome to a stored decision."""
        decisions = self._load()
        for d in decisions:
            if str(d.get("id")) == str(decision_id):
                d["outcome"] = outcome
                self._save(decisions)
                return d
        return None

    def get_recent(self, limit: int = 20) -> List[dict]:
        """Get most recent decisions."""
        return self._load()[-limit:]

    def get_by_strategy(self, strategy_name: str) -> List[dict]:
        """Get all decisions for a specific strategy."""
        return [d for d in self._load() if d.get("strategy") == strategy_name]

    def get_with_outcomes(self) -> List[dict]:
        """Get all decisions that have outcomes attached."""
        return [d for d in self._load() if d.get("outcome") is not None]

    def analyze_claude_accuracy(self) -> dict:
        """Analyze whether Claude's confidence correlates with outcomes."""
        with_outcomes = self.get_with_outcomes()
        claude_decisions = [d for d in with_outcomes if d.get("claude_used")]
        determ_decisions = [d for d in with_outcomes if not d.get("claude_used")]

        def _stats(decisions):
            if not decisions:
                return {"count": 0}
            trades = [d for d in decisions
                      if d.get("trade_or_no_trade") == "trade"
                      and d.get("outcome", {}).get("r_multiple") is not None]
            if not trades:
                return {"count": len(decisions), "trades": 0}
            r_mults = [d["outcome"]["r_multiple"] for d in trades]
            wins = [r for r in r_mults if r > 0]
            return {
                "count": len(decisions),
                "trades": len(trades),
                "win_rate": round(len(wins) / len(trades), 4) if trades else 0,
                "avg_r": round(sum(r_mults) / len(r_mults), 4) if r_mults else 0,
                "total_r": round(sum(r_mults), 2),
            }

        return {
            "claude_stats": _stats(claude_decisions),
            "deterministic_stats": _stats(determ_decisions),
            "total_decisions": len(self._load()),
            "decisions_with_outcomes": len(with_outcomes),
        }
