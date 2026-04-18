"""
Builds structured prompts for Claude from features and candidate setups.
"""

import json


def build_system_prompt(settings: dict) -> str:
    """Build the system prompt with current settings injected."""
    equity = settings.get("equity", 50000)
    risk_pct = settings.get("risk_pct", 1.0)
    max_pos = settings.get("max_positions", 2)

    return f"""You are the Gold Market Intelligence System — a constrained decision assistant for XAU/USD trading.

## Your Role
You receive structured market features and candidate trade setups from deterministic strategy modules.
Your job is to RANK, EXPLAIN, and VALIDATE — not to invent trades from scratch.

## Current Account
- Equity: ${equity:,.0f}
- Risk per trade: {risk_pct}%
- Max open positions: {max_pos}

## Decision Rules (HARD GATES — you cannot override these)
- NO TRADE is the default. You need strong confluence to recommend a trade.
- R:R must be >= 1.5:1 to target_1
- If no deterministic strategy passes validation, output no_trade
- If risk blockers are active, output no_trade
- If confidence < 50, output no_trade
- Never bypass deterministic gates

## Output Format
You MUST respond with ONLY a JSON object matching this exact schema:
{{
  "market_state": "bullish_trend|bearish_trend|range|expansion|compression|transition",
  "chosen_strategy": "strategy_name or no_trade",
  "thesis_summary": "1-2 sentence thesis",
  "invalidation_summary": "what would invalidate this",
  "entry": number or null,
  "stop": number or null,
  "target_1": number or null,
  "target_2": number or null,
  "confidence": 0-100,
  "trade_or_no_trade": "trade|no_trade",
  "rationale": ["reason 1", "reason 2"],
  "risk_notes": ["risk 1"],
  "uncertainty_notes": ["uncertainty 1"]
}}

Do NOT include any text outside the JSON object. No markdown, no explanation, just valid JSON.
Do NOT wrap your response in markdown code blocks.
Do NOT include any text before or after the JSON object.
Confidence must be a whole number (integer), not a decimal.

IMPORTANT — respond with ONLY a valid JSON object. No markdown, no explanation."""


def build_decision_prompt(features: dict, setups: list,
                          risk_blockers: list, metrics: dict = None) -> str:
    """Build the user message with all structured inputs for Claude."""
    parts = []

    parts.append("## Current Market Features")
    feature_subset = {k: v for k, v in features.items()
                      if k not in ("support_levels", "resistance_levels",
                                   "swing_highs", "swing_lows")}
    parts.append(json.dumps(feature_subset, indent=2, default=str))

    parts.append("\n## Key Levels")
    parts.append(json.dumps({
        "resistance": features.get("resistance_levels", [])[:3],
        "support": features.get("support_levels", [])[:3],
    }, indent=2))

    parts.append("\n## Candidate Setups from Deterministic Strategies")
    if setups:
        for s in setups:
            parts.append(json.dumps(s, indent=2, default=str))
    else:
        parts.append("No valid setups detected by any strategy module.")

    parts.append("\n## Risk Blockers")
    if risk_blockers:
        for b in risk_blockers:
            parts.append(f"- [{b.get('severity', 'hard')}] {b.get('rule', '')}: {b.get('reason', '')}")
    else:
        parts.append("No risk blockers active.")

    if metrics and metrics.get("closed_trades", 0) > 0:
        parts.append("\n## Recent Performance")
        parts.append(json.dumps({
            "closed_trades": metrics.get("closed_trades"),
            "win_rate": metrics.get("win_rate"),
            "expectancy": metrics.get("expectancy"),
            "max_drawdown_r": metrics.get("max_drawdown_r"),
            "edge_status": metrics.get("edge_status"),
        }, indent=2))

    parts.append("\n## Instructions")
    parts.append("Analyze the above data and output your decision as a single JSON object.")
    parts.append("If risk blockers are active or no valid setups exist, output no_trade.")
    parts.append("If you choose a trade, use the entry/stop/target from the strategy setup.")
    parts.append("\nRemember: respond with ONLY a valid JSON object. No markdown, no explanation.")

    return "\n".join(parts)
