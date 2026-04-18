"""
Decision schema for Claude outputs.
Defines the exact JSON structure Claude must return and validation logic.
"""

DECISION_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "market_state": {
            "type": "string",
            "enum": ["bullish_trend", "bearish_trend", "range", "expansion", "compression", "transition"],
            "description": "Current market regime classification"
        },
        "chosen_strategy": {
            "type": "string",
            "description": "Strategy name from the candidate list, or 'no_trade'"
        },
        "thesis_summary": {
            "type": "string",
            "description": "1-2 sentence summary of the trade thesis"
        },
        "invalidation_summary": {
            "type": "string",
            "description": "What would invalidate this trade/analysis"
        },
        "entry": {"type": ["number", "null"], "description": "Entry price or null if no trade"},
        "stop": {"type": ["number", "null"], "description": "Stop loss price or null"},
        "target_1": {"type": ["number", "null"], "description": "First target price or null"},
        "target_2": {"type": ["number", "null"], "description": "Second target price or null"},
        "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
        "trade_or_no_trade": {"type": "string", "enum": ["trade", "no_trade"]},
        "rationale": {"type": "array", "items": {"type": "string"}},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
        "uncertainty_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "market_state", "chosen_strategy", "thesis_summary",
        "invalidation_summary", "confidence", "trade_or_no_trade",
        "rationale", "risk_notes", "uncertainty_notes"
    ],
}


def validate_decision_output(d: dict) -> list:
    """Validate a decision dict against the schema. Returns list of error strings.

    This validator is intentionally tolerant of minor type mismatches that Claude
    may produce (e.g. float confidence, string confidence, extra fields).  It
    coerces where safe and only reports genuine structural problems.
    """
    errors = []
    required = DECISION_JSON_SCHEMA["required"]
    for field in required:
        if field not in d:
            errors.append(f"Missing required field: {field}")

    if errors:
        return errors

    # --- confidence: accept float / numeric string and coerce to int ---
    conf = d["confidence"]
    if isinstance(conf, float):
        d["confidence"] = int(round(conf))
    elif isinstance(conf, str):
        try:
            d["confidence"] = int(round(float(conf)))
        except (TypeError, ValueError):
            errors.append("confidence must be a number 0-100")
            return errors
    if not isinstance(d["confidence"], int) or not (0 <= d["confidence"] <= 100):
        errors.append("confidence must be an integer 0-100")

    valid_states = ["bullish_trend", "bearish_trend", "range", "expansion", "compression", "transition"]
    if d["market_state"] not in valid_states:
        errors.append(f"Invalid market_state: {d['market_state']}")

    if d["trade_or_no_trade"] not in ("trade", "no_trade"):
        errors.append(f"trade_or_no_trade must be 'trade' or 'no_trade'")

    if not isinstance(d.get("rationale", []), list):
        errors.append("rationale must be a list of strings")
    if not isinstance(d.get("risk_notes", []), list):
        errors.append("risk_notes must be a list of strings")
    if not isinstance(d.get("uncertainty_notes", []), list):
        errors.append("uncertainty_notes must be a list of strings")

    if d["trade_or_no_trade"] == "trade":
        for f in ("entry", "stop", "target_1"):
            val = d.get(f)
            if val is None or not isinstance(val, (int, float)):
                errors.append(f"'{f}' must be a number when trade_or_no_trade is 'trade'")
        if not errors:
            entry = d["entry"]
            stop = d["stop"]
            t1 = d["target_1"]
            risk = abs(entry - stop)
            reward = abs(t1 - entry)
            if risk > 0 and reward / risk < 1.5:
                errors.append(f"R:R to target_1 is {reward/risk:.2f}, minimum 1.5 required")

    return errors


def make_no_trade_decision(reason: str, market_state: str = "transition",
                           confidence: int = 0) -> dict:
    """Create a valid no-trade decision dict."""
    return {
        "market_state": market_state,
        "chosen_strategy": "no_trade",
        "thesis_summary": "No trade — " + reason,
        "invalidation_summary": "N/A",
        "entry": None,
        "stop": None,
        "target_1": None,
        "target_2": None,
        "confidence": confidence,
        "trade_or_no_trade": "no_trade",
        "rationale": [reason],
        "risk_notes": [],
        "uncertainty_notes": [],
    }
