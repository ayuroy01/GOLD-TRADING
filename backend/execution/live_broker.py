"""
Live broker adapter — gated, fail-closed, NOT enabled by default.

Responsibilities:
  1. Refuse to construct unless LIVE_BROKER_ENABLED=true.
  2. Validate broker-specific config up-front (env vars).
  3. Expose get_status() so /api/health and /api/readiness can report
     implemented / ready / reason without instantiating the adapter.
  4. Delegate every order attempt through the readiness gate. If readiness
     reports any hard blocker, raise LiveExecutionBlocked -- never silently
     fall back to paper, never partially execute.

This module intentionally does NOT contain a working broker integration.
The actual HTTP/SDK glue belongs in a per-broker subclass (e.g. OandaBroker).
The skeleton below is the seam: configuration, gating, and audit hooks.

Supported broker stubs (only one should be implemented at a time):
  - OANDA (REST v20)
  - Interactive Brokers (TWS API)
  - MetaTrader 5

Required env to even attempt construction:
  LIVE_BROKER_ENABLED=true
  LIVE_BROKER=oanda                 # or ib, mt5
  OANDA_API_KEY=...                 # if LIVE_BROKER=oanda
  OANDA_ACCOUNT_ID=...
  OANDA_ENVIRONMENT=practice|live
"""

import os
from typing import List, Optional, Dict, Any
from backend.execution.broker_base import BaseBroker, BrokerOrder, BrokerPosition
from backend.execution.live_readiness import (
    LiveReadinessReport,
    LiveExecutionBlocked,
    evaluate_live_readiness,
)


# ─── Env gates ────────────────────────────────────────────────────────────────


def is_live_enabled() -> bool:
    """LIVE_BROKER_ENABLED must be the string 'true' to enable the adapter."""
    return os.environ.get("LIVE_BROKER_ENABLED", "").lower() == "true"


def selected_live_broker() -> str:
    """Which live broker the operator selected (default: 'oanda')."""
    return os.environ.get("LIVE_BROKER", "oanda").lower()


def broker_environment() -> str:
    """The current broker environment. OANDA-specific today -- if other
    brokers are added, branch on selected_live_broker()."""
    chosen = selected_live_broker()
    if chosen == "oanda":
        return os.environ.get("OANDA_ENVIRONMENT", "practice").lower()
    return "unknown"


def is_cutover_acknowledged() -> bool:
    """Phase 3: real-money live cutover requires explicit operator ack.

    An operator must set LIVE_CUTOVER_ACKNOWLEDGED=true after completing the
    supervised practice-account validation (deploy/README.md section 5).
    This flag is NEVER inferred -- the only way it flips true is an explicit
    env assertion by the operator.
    """
    return os.environ.get("LIVE_CUTOVER_ACKNOWLEDGED", "").lower() == "true"


# ─── Per-broker config validation (no SDK calls) ──────────────────────────────


def _validate_oanda_config() -> Optional[str]:
    missing = [v for v in ("OANDA_API_KEY", "OANDA_ACCOUNT_ID") if not os.environ.get(v)]
    if missing:
        return f"OANDA missing env vars: {', '.join(missing)}"
    env = os.environ.get("OANDA_ENVIRONMENT", "practice").lower()
    if env not in ("practice", "live"):
        return f"OANDA_ENVIRONMENT must be 'practice' or 'live' (got {env!r})"
    return None


_BROKER_CONFIG_VALIDATORS = {
    "oanda": _validate_oanda_config,
    # "ib": _validate_ib_config,
    # "mt5": _validate_mt5_config,
}


def validate_live_broker_config() -> Optional[str]:
    """Returns None if config looks valid, or an error string explaining why not."""
    if not is_live_enabled():
        return "LIVE_BROKER_ENABLED is not 'true'"
    chosen = selected_live_broker()
    validator = _BROKER_CONFIG_VALIDATORS.get(chosen)
    if validator is None:
        return f"Unsupported LIVE_BROKER={chosen!r}"
    return validator()


# ─── Status (no instantiation required) ───────────────────────────────────────


# Which live brokers have a concrete, HTTP-wired adapter in this build.
# Add a broker name here ONLY after its subclass is tested end-to-end.
_IMPLEMENTED_BROKERS = {"oanda"}


def get_live_broker_status() -> Dict[str, Any]:
    """Report whether a live broker adapter is configurable AND implemented.

    Used by /api/health and /api/readiness without ever constructing the
    LiveBroker (which intentionally raises when disabled).
    """
    enabled = is_live_enabled()
    chosen = selected_live_broker()
    config_error = validate_live_broker_config() if enabled else "LIVE_BROKER_ENABLED is not 'true'"
    implemented = chosen in _IMPLEMENTED_BROKERS
    environment = broker_environment()
    cutover_ack = is_cutover_acknowledged()
    # An adapter is "validated" only if the operator has explicitly asserted
    # completion of the supervised dry-run. No code path flips this true.
    validated = cutover_ack

    reason: Optional[str]
    if not enabled:
        reason = "LIVE_BROKER_ENABLED is not 'true'"
    elif config_error:
        reason = config_error
    elif not implemented:
        reason = (
            f"{chosen!r} adapter is a skeleton: order routing not implemented. "
            "Add a concrete LiveBroker subclass + SDK glue."
        )
    elif environment == "live" and not cutover_ack:
        reason = (
            f"{chosen!r} adapter is implemented but cutover to a real-money "
            "live environment is blocked until LIVE_CUTOVER_ACKNOWLEDGED=true."
        )
    else:
        reason = (
            f"{chosen!r} adapter is implemented but UNVALIDATED against the live "
            "service in this build. Run a supervised practice dry-run before live use."
        )

    # Ready == enabled AND config valid AND implemented AND (practice env OR
    # explicit cutover acknowledgement). Operationally honest: a live-env
    # broker without acknowledgement is NOT ready.
    ready = bool(
        enabled
        and config_error is None
        and implemented
        and (environment != "live" or cutover_ack)
    )

    return {
        "enabled": enabled,
        "selected": chosen,
        "implemented": implemented,
        "ready": ready,
        "config_valid": config_error is None and enabled,
        "environment": environment,
        "practice_mode": environment == "practice",
        "cutover_acknowledged": cutover_ack,
        "validated": validated,
        "live_cutover_allowed": bool(enabled and implemented and cutover_ack),
        "reason": reason,
    }


# ─── The adapter ──────────────────────────────────────────────────────────────


class LiveBroker(BaseBroker):
    """Live broker adapter.

    Refuses to construct unless live execution is enabled AND broker-specific
    config is present. Even then, every order goes through the readiness gate
    -- so a misconfigured environment cannot accidentally place orders.

    Subclasses should implement submit_order/close_position/etc against a
    real SDK and call self._enforce_readiness() at the top of every action.
    """

    def __init__(
        self,
        provider_status: Optional[Dict[str, Any]] = None,
        settings: Optional[Dict[str, Any]] = None,
        risk_blockers: Optional[List[Dict[str, Any]]] = None,
        stale_data_seconds: int = 300,
    ):
        if not is_live_enabled():
            raise RuntimeError(
                "Live trading is disabled. Set LIVE_BROKER_ENABLED=true and "
                "configure broker credentials to enable."
            )
        cfg_err = validate_live_broker_config()
        if cfg_err:
            raise RuntimeError(f"Live broker configuration invalid: {cfg_err}")

        self._provider_status = provider_status or {}
        self._settings = settings or {}
        self._risk_blockers = risk_blockers or []
        self._stale_data_seconds = stale_data_seconds

    # ── readiness ────────────────────────────────────────────────────────────

    def evaluate_readiness(self) -> LiveReadinessReport:
        return evaluate_live_readiness(
            live_enabled=is_live_enabled(),
            provider_status=self._provider_status,
            broker_status=get_live_broker_status(),
            settings=self._settings,
            risk_blockers=self._risk_blockers,
            stale_data_seconds=self._stale_data_seconds,
            broker_environment=broker_environment(),
            cutover_acknowledged=is_cutover_acknowledged(),
        )

    def _enforce_readiness(self) -> None:
        report = self.evaluate_readiness()
        if not report.ready:
            raise LiveExecutionBlocked(report)

    # ── BaseBroker (intentionally not implemented) ───────────────────────────

    def submit_order(self, order: BrokerOrder) -> dict:
        self._enforce_readiness()
        raise NotImplementedError(
            "Live order submission not implemented. "
            "Add a concrete LiveBroker subclass + broker SDK in execution/."
        )

    def close_position(self, position_id: str, price: float = None) -> dict:
        self._enforce_readiness()
        raise NotImplementedError("Live position close not implemented.")

    def get_positions(self) -> List[BrokerPosition]:
        raise NotImplementedError("Live position query not implemented.")

    def get_account(self) -> dict:
        raise NotImplementedError("Live account query not implemented.")

    def get_fills(self, limit: int = 50) -> List[dict]:
        raise NotImplementedError("Live fills query not implemented.")

    def is_live(self) -> bool:
        return True
