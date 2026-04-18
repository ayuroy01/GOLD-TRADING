"""
Live-trading readiness gate.

This module is the single source of truth for whether live execution is
permitted right now. It combines:

  - explicit env enable flag (LIVE_BROKER_ENABLED)
  - data provider readiness (real, ready, fresh)
  - broker adapter readiness (configured, implemented)
  - operator settings (safe_mode, system_mode)
  - critical risk blockers (drawdown, daily loss, news, weekend, off-hours)
  - PHASE 3: explicit live-cutover acknowledgement when broker env is "live"

Rules encoded here:

  Rule 1: Simulated data is acceptable for research/paper.
          Simulated data is NEVER acceptable for live execution.

  Rule 2: If real provider config is missing, live mode must block --
          NEVER silently degrade to simulated.

  Rule 3: If data is stale beyond `stale_data_seconds`, live mode must block.

  Rule 4: If the broker adapter is not implemented or not ready, live mode
          must block. Health/status must report the reason.

  Rule 5: Claude is advisory only. Deterministic checks here are the
          authority over what reaches the broker.

  Rule 6 (PHASE 3): If the broker environment is "live" (real money),
          LIVE_CUTOVER_ACKNOWLEDGED=true must also be set by the operator.
          Practice accounts do NOT require this gate; live accounts always
          do, no matter how green the rest of the checks are. This exists
          because the adapters are implemented but UNVALIDATED against the
          live service in this build -- an operator must explicitly assert
          they have completed the supervised practice-account run.

Result shape:

    {
      "ready": False,
      "blockers": [
        {"rule": "live_disabled", "reason": "...", "severity": "hard"},
        ...
      ],
      "checked_at": "2026-04-17T...",
    }

Callers:
  - /api/health surfaces a summary
  - /api/readiness returns the full report
  - LiveBroker.submit_order() refuses to place orders unless ready=True
"""

from typing import List, Dict, Any, Optional
from backend.core.time_utils import utc_timestamp


# Reason / rule constants for stable test/UI matching.
RULE_LIVE_DISABLED = "live_disabled"
RULE_BROKER_NOT_IMPLEMENTED = "broker_not_implemented"
RULE_BROKER_NOT_READY = "broker_not_ready"
RULE_PROVIDER_NOT_READY = "provider_not_ready"
RULE_SIMULATED_DATA = "simulated_data"
RULE_STALE_DATA = "stale_data"
RULE_SAFE_MODE = "safe_mode"
RULE_NOT_LIVE_MODE = "not_live_mode"
RULE_RISK_BLOCKED = "risk_blocked"
RULE_CUTOVER_NOT_ACKNOWLEDGED = "cutover_not_acknowledged"


class Blocker:
    __slots__ = ("rule", "reason", "severity")

    def __init__(self, rule: str, reason: str, severity: str = "hard"):
        self.rule = rule
        self.reason = reason
        self.severity = severity

    def to_dict(self) -> Dict[str, str]:
        return {"rule": self.rule, "reason": self.reason, "severity": self.severity}


class LiveReadinessReport:
    def __init__(self, blockers: List[Blocker]):
        self.blockers = blockers
        self.checked_at = utc_timestamp()

    @property
    def ready(self) -> bool:
        # Any "hard" blocker => not ready.
        return not any(b.severity == "hard" for b in self.blockers)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ready": self.ready,
            "blockers": [b.to_dict() for b in self.blockers],
            "checked_at": self.checked_at,
            "blocker_count": len(self.blockers),
            "hard_blocker_count": sum(1 for b in self.blockers if b.severity == "hard"),
        }


def evaluate_live_readiness(
    *,
    live_enabled: bool,
    provider_status: Dict[str, Any],
    broker_status: Dict[str, Any],
    settings: Dict[str, Any],
    risk_blockers: Optional[List[Dict[str, Any]]] = None,
    stale_data_seconds: int = 300,
    broker_environment: Optional[str] = None,
    cutover_acknowledged: bool = False,
) -> LiveReadinessReport:
    """Evaluate every condition required for live execution.

    All inputs are plain dicts -- this function has no I/O and is fully
    deterministic / fully testable.
    """
    blockers: List[Blocker] = []

    # ── Mode / explicit enable ────────────────────────────────────────────────
    system_mode = (settings or {}).get("system_mode", "paper_trading")
    if system_mode != "live":
        blockers.append(Blocker(
            RULE_NOT_LIVE_MODE,
            f"System mode is {system_mode!r}; set system_mode='live' to attempt live execution.",
        ))

    if not live_enabled:
        blockers.append(Blocker(
            RULE_LIVE_DISABLED,
            "Live trading is disabled. Set LIVE_BROKER_ENABLED=true to enable.",
        ))

    if (settings or {}).get("safe_mode"):
        blockers.append(Blocker(
            RULE_SAFE_MODE,
            "Safe mode is on -- all trading blocked by operator.",
        ))

    # ── Data provider ────────────────────────────────────────────────────────
    if not provider_status:
        blockers.append(Blocker(
            RULE_PROVIDER_NOT_READY,
            "No market data provider status available.",
        ))
    else:
        if not provider_status.get("ready"):
            reason = provider_status.get("reason") or "provider not ready"
            blockers.append(Blocker(RULE_PROVIDER_NOT_READY, reason))

        # Rule 1: simulated data NEVER acceptable for live execution.
        if provider_status.get("is_real") is False:
            kind = provider_status.get("kind", "simulated")
            blockers.append(Blocker(
                RULE_SIMULATED_DATA,
                f"Active data provider is {kind!r}; live execution requires a real-data provider.",
            ))

        # Rule 3: stale data => block live.
        age = provider_status.get("last_quote_age_seconds")
        if isinstance(age, (int, float)) and age > stale_data_seconds:
            blockers.append(Blocker(
                RULE_STALE_DATA,
                f"Last quote is {age}s old; exceeds {stale_data_seconds}s freshness budget.",
            ))

    # ── Broker adapter ───────────────────────────────────────────────────────
    if not broker_status:
        blockers.append(Blocker(
            RULE_BROKER_NOT_IMPLEMENTED,
            "No live broker adapter is configured.",
        ))
    else:
        if not broker_status.get("implemented", False):
            blockers.append(Blocker(
                RULE_BROKER_NOT_IMPLEMENTED,
                broker_status.get("reason") or
                "Live broker adapter is a skeleton (not implemented).",
            ))
        elif not broker_status.get("ready", False):
            blockers.append(Blocker(
                RULE_BROKER_NOT_READY,
                broker_status.get("reason") or "Live broker adapter is not ready.",
            ))

    # ── Live-cutover acknowledgement (Rule 6) ────────────────────────────────
    # Only applies when the broker is pointed at a real-money "live" venue.
    # Practice accounts are exempt so the dry-run workflow isn't blocked.
    env_norm = (broker_environment or "").strip().lower()
    if env_norm == "live" and not cutover_acknowledged:
        blockers.append(Blocker(
            RULE_CUTOVER_NOT_ACKNOWLEDGED,
            "Broker is pointed at a real-money live environment but "
            "LIVE_CUTOVER_ACKNOWLEDGED is not 'true'. Complete the supervised "
            "practice-account validation in deploy/README.md, then set the "
            "env var explicitly.",
        ))

    # ── Risk blockers (forwarded from RiskEngine) ────────────────────────────
    for rb in (risk_blockers or []):
        # Treat all risk-engine hard blockers as live-blocking too.
        sev = rb.get("severity", "hard")
        if sev == "hard":
            blockers.append(Blocker(
                f"{RULE_RISK_BLOCKED}:{rb.get('rule', 'unknown')}",
                rb.get("reason", "risk engine blocked"),
                "hard",
            ))

    return LiveReadinessReport(blockers)


class LiveExecutionBlocked(Exception):
    """Raised by live brokers when readiness gating refuses a live action."""

    def __init__(self, report: LiveReadinessReport):
        self.report = report
        reasons = "; ".join(f"{b.rule}: {b.reason}" for b in report.blockers)
        super().__init__(f"Live execution blocked: {reasons}")
