"""
Decision engine — orchestrates the full decision pipeline.
Combines features, strategies, risk, and optionally Claude into a single decision.
"""

import json
import logging
import re
import traceback
from typing import Optional
from urllib.request import Request, urlopen

from backend.agent.decision_schema import validate_decision_output, make_no_trade_decision, DECISION_JSON_SCHEMA
from backend.agent.prompt_builder import build_system_prompt, build_decision_prompt
from backend.strategies.registry import StrategyRegistry
from backend.risk.engine import RiskEngine, RiskConfig
from backend.core.time_utils import utc_timestamp, epoch_ms

logger = logging.getLogger(__name__)


class DecisionEngine:
    """Orchestrates the full decision pipeline.

    Flow:
    1. Compute features (external)
    2. Evaluate strategies deterministically
    3. Check risk rules
    4. Optionally invoke Claude for ranking/explanation
    5. Validate output schema
    6. Return structured decision with full audit trail
    """

    def __init__(self, strategy_registry: StrategyRegistry = None,
                 risk_engine: RiskEngine = None,
                 api_key: str = "", model: str = "claude-sonnet-4-20250514"):
        self.registry = strategy_registry or StrategyRegistry()
        self.risk_engine = risk_engine or RiskEngine()
        self.api_key = api_key
        self.model = model

    def decide(self, features: dict, candles: dict,
               settings: dict = None, metrics: dict = None,
               use_claude: bool = True) -> dict:
        """Run the full decision pipeline.

        Args:
            features: output from compute_all_features()
            candles: dict of {timeframe: [candle_list]}
            settings: account settings dict
            metrics: performance metrics dict
            use_claude: whether to invoke Claude (False = deterministic only)

        Returns:
            dict with decision, audit trail, and metadata
        """
        settings = settings or {}
        decision_id = str(epoch_ms())
        timestamp = utc_timestamp()

        # Step 1: Evaluate all strategies
        all_setups = self.registry.evaluate_all(features, candles)
        valid_setups = [s for s in all_setups if s.valid]
        setup_dicts = [s.to_dict() for s in all_setups]

        # Step 2: Check risk rules
        best_setup_dict = valid_setups[0].to_dict() if valid_setups else None
        allowed, blockers = self.risk_engine.is_allowed(features, best_setup_dict)
        blocker_dicts = [b.to_dict() for b in blockers]

        # Step 3: If risk blocks or no setups, no trade
        if not allowed or not valid_setups:
            if not valid_setups:
                reason = "No valid strategy setup detected"
            else:
                reasons = [b.reason for b in blockers if b.severity == "hard"]
                reason = "; ".join(reasons) if reasons else "Risk rules blocked"

            decision = make_no_trade_decision(reason)
            return self._build_result(
                decision=decision,
                decision_id=decision_id,
                timestamp=timestamp,
                setups=setup_dicts,
                blockers=blocker_dicts,
                claude_used=False,
                features_snapshot=features,
            )

        # Step 4: Optionally use Claude
        claude_raw = None
        claude_error = None
        decision = None

        if use_claude and self.api_key:
            try:
                decision, claude_raw = self._invoke_claude(
                    features, [s.to_dict() for s in valid_setups],
                    blocker_dicts, settings, metrics
                )
            except Exception as e:
                claude_error = f"{type(e).__name__}: {e}"
                logger.warning("Claude invocation failed, falling back to deterministic: %s", claude_error)
                # Fall through to deterministic

        # Step 5: Deterministic fallback
        if decision is None:
            best = valid_setups[0]
            decision = {
                "market_state": features.get("trend_1h", "transition"),
                "chosen_strategy": best.strategy_name,
                "thesis_summary": "; ".join(best.rationale) if best.rationale else "Deterministic setup",
                "invalidation_summary": best.invalidation_reason or "Stop loss hit",
                "entry": best.entry,
                "stop": best.stop,
                "target_1": best.target_1,
                "target_2": best.target_2,
                "confidence": best.confidence,
                "trade_or_no_trade": "trade",
                "rationale": best.rationale or [],
                "risk_notes": [],
                "uncertainty_notes": ["Deterministic mode — Claude not used"],
            }

        # Step 6: Validate
        errors = validate_decision_output(decision)
        if errors:
            decision = make_no_trade_decision(
                f"Schema validation failed: {'; '.join(errors)}"
            )

        return self._build_result(
            decision=decision,
            decision_id=decision_id,
            timestamp=timestamp,
            setups=setup_dicts,
            blockers=blocker_dicts,
            claude_used=claude_raw is not None,
            claude_raw=claude_raw,
            claude_error=claude_error,
            features_snapshot=features,
        )

    # ── JSON extraction helpers ────────────────────────────────────────────

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Try multiple strategies to extract a JSON object from *text*.

        Strategies (in order):
        1. Direct json.loads on the stripped text.
        2. Extract from ```json ... ``` fenced code blocks.
        3. Extract from ``` ... ``` fenced code blocks (no language tag).
        4. Scan for the first '{' and match the last '}' in the text.
        If all fail, raise ValueError with a descriptive message.
        """
        stripped = text.strip()

        # Strategy 1: direct parse
        try:
            return json.loads(stripped)
        except (json.JSONDecodeError, ValueError):
            pass

        # Strategy 2: ```json ... ``` blocks
        m = re.search(r"```json\s*\n?(.*?)```", stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 3: ``` ... ``` blocks (any language or none)
        m = re.search(r"```\w*\s*\n?(.*?)```", stripped, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1).strip())
            except (json.JSONDecodeError, ValueError):
                pass

        # Strategy 4: first '{' to last '}'
        first_brace = stripped.find("{")
        last_brace = stripped.rfind("}")
        if first_brace != -1 and last_brace > first_brace:
            try:
                return json.loads(stripped[first_brace:last_brace + 1])
            except (json.JSONDecodeError, ValueError):
                pass

        raise ValueError(
            f"Could not extract valid JSON from Claude response "
            f"(length={len(text)}). First 200 chars: {text[:200]!r}"
        )

    @staticmethod
    def _coerce_decision(raw: dict) -> dict:
        """Normalise Claude's raw output so it passes schema validation.

        - confidence → int (round floats, parse numeric strings)
        - rationale / risk_notes / uncertainty_notes → list (wrap str)
        - trade_or_no_trade → lowercase
        - market_state → lowercase with underscores
        - Strip keys not present in the schema
        """
        allowed_keys = set(DECISION_JSON_SCHEMA["properties"].keys())
        coerced = {k: v for k, v in raw.items() if k in allowed_keys}

        # confidence → int
        conf = coerced.get("confidence")
        if conf is not None:
            try:
                coerced["confidence"] = int(round(float(conf)))
            except (TypeError, ValueError):
                pass  # leave as-is; schema validation will catch it

        # list fields — wrap bare string in a list
        for field in ("rationale", "risk_notes", "uncertainty_notes"):
            val = coerced.get(field)
            if isinstance(val, str):
                coerced[field] = [val]

        # trade_or_no_trade → lowercase
        if isinstance(coerced.get("trade_or_no_trade"), str):
            coerced["trade_or_no_trade"] = coerced["trade_or_no_trade"].strip().lower()

        # market_state → lowercase, spaces/hyphens → underscores
        if isinstance(coerced.get("market_state"), str):
            coerced["market_state"] = (
                coerced["market_state"]
                .strip()
                .lower()
                .replace(" ", "_")
                .replace("-", "_")
            )

        return coerced

    # ── Claude invocation ────────────────────────────────────────────────

    def _invoke_claude(self, features, setups, blockers, settings, metrics):
        """Call Claude API and parse JSON response."""
        system_prompt = build_system_prompt(settings or {})
        user_prompt = build_decision_prompt(
            features, setups, blockers, metrics
        )

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        req = Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(payload).encode(),
            headers=headers,
            method="POST",
        )

        with urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())

        # Extract text from response
        raw_text = ""
        for block in result.get("content", []):
            if block.get("type") == "text":
                raw_text += block.get("text", "")

        # Parse, coerce, and return
        try:
            parsed = self._extract_json(raw_text)
        except ValueError as e:
            logger.warning("JSON extraction failed: %s", e)
            raise

        decision = self._coerce_decision(parsed)
        return decision, raw_text

    def _build_result(self, decision, decision_id, timestamp, setups,
                      blockers, claude_used, claude_raw=None,
                      claude_error=None, features_snapshot=None):
        """Build the full result dict with audit trail."""
        return {
            "decision_id": decision_id,
            "timestamp": timestamp,
            "decision": decision,
            "setups_evaluated": setups,
            "risk_blockers": blockers,
            "claude_used": claude_used,
            "claude_raw_response": claude_raw,
            "claude_error": claude_error,
            "features_snapshot": features_snapshot,
            "trade_or_no_trade": decision.get("trade_or_no_trade", "no_trade"),
            "strategy": decision.get("chosen_strategy", "no_trade"),
            "confidence": decision.get("confidence", 0),
        }
