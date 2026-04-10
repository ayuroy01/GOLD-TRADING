import systemRules from "../../gold_v1_system_rules.json";

const RISK_FRACTION = systemRules.step_6_position_sizing.risk_fraction; // 0.01
const MAX_POSITIONS = systemRules.system_metadata.max_open_positions;   // 2
const MIN_RR = 1.5; // From step_7: R:R to T1 must be >= 1.5

/**
 * Compute risk distance (R) between entry and stop.
 * @param {number} entry - Entry price
 * @param {number} stop  - Stop loss price
 * @returns {number} Absolute risk distance in price units
 */
export function riskDistance(entry, stop) {
  return Math.abs(entry - stop);
}

/**
 * Determine trade direction from entry/stop relationship.
 * @param {number} entry
 * @param {number} stop
 * @returns {'long'|'short'}
 */
export function tradeDirection(entry, stop) {
  return entry > stop ? "long" : "short";
}

/**
 * Compute position size in ounces (oz).
 * Formula: (Equity × risk_fraction) / risk_distance
 * @param {number} equity   - Account equity in USD
 * @param {number} entry    - Entry price
 * @param {number} stop     - Stop loss price
 * @returns {{ oz: number, lots: number, riskUsd: number }}
 */
export function positionSize(equity, entry, stop) {
  const risk = riskDistance(entry, stop);
  if (risk <= 0) return { oz: 0, lots: 0, riskUsd: 0 };
  const riskUsd = equity * RISK_FRACTION;
  const oz = riskUsd / risk;
  // Standard gold lot = 100 oz
  const lots = oz / 100;
  return {
    oz: Math.round(oz * 100) / 100,
    lots: Math.round(lots * 100) / 100,
    riskUsd: Math.round(riskUsd * 100) / 100,
  };
}

/**
 * Compute risk-reward ratio to a target.
 * @param {number} entry  - Entry price
 * @param {number} stop   - Stop loss price
 * @param {number} target - Target price
 * @returns {number} R:R ratio (e.g., 2.5 means 2.5:1)
 */
export function riskRewardRatio(entry, stop, target) {
  const risk = riskDistance(entry, stop);
  if (risk <= 0) return 0;
  const reward = Math.abs(target - entry);
  return Math.round((reward / risk) * 100) / 100;
}

/**
 * Compute the R-multiple of a closed trade.
 * @param {number} entry     - Entry price
 * @param {number} stop      - Stop loss price
 * @param {number} exitPrice - Actual exit price
 * @returns {number} R-multiple (positive = profit, negative = loss)
 */
export function rMultiple(entry, stop, exitPrice) {
  const risk = riskDistance(entry, stop);
  if (risk <= 0) return 0;
  const direction = tradeDirection(entry, stop);
  const pnl = direction === "long" ? exitPrice - entry : entry - exitPrice;
  return Math.round((pnl / risk) * 100) / 100;
}

/**
 * Compute stop loss with buffer per system rules.
 * Long: pullback low - 0.3% of price
 * Short: pullback high + 0.3% of price
 * @param {'long'|'short'} direction
 * @param {number} swingPrice - Pullback swing extreme
 * @param {number} currentPrice - Current price for buffer calc
 * @returns {number} Buffered stop loss price
 */
export function bufferedStop(direction, swingPrice, currentPrice) {
  const buffer = currentPrice * 0.003;
  if (direction === "long") {
    return Math.round((swingPrice - buffer) * 100) / 100;
  }
  return Math.round((swingPrice + buffer) * 100) / 100;
}

/**
 * Full pre-trade computation. Takes raw inputs and returns everything
 * the system needs to evaluate and execute a trade.
 */
export function computeTrade({ equity, entry, stop, target1, target2 }) {
  const risk = riskDistance(entry, stop);
  const direction = tradeDirection(entry, stop);
  const size = positionSize(equity, entry, stop);
  const rrT1 = target1 ? riskRewardRatio(entry, stop, target1) : null;
  const rrT2 = target2 ? riskRewardRatio(entry, stop, target2) : null;

  return {
    direction,
    risk,
    riskUsd: size.riskUsd,
    positionOz: size.oz,
    positionLots: size.lots,
    rrToT1: rrT1,
    rrToT2: rrT2,
    // Minimum R:R gate
    rrValid: rrT1 !== null && rrT1 >= MIN_RR,
    // For display
    riskPct: RISK_FRACTION * 100,
    equity,
  };
}

/**
 * Evaluate whether this trade should be BLOCKED.
 * Returns { allowed: boolean, reasons: string[] }
 */
export function gateTrade({ rrToT1, openPositions = 0, drawdownPct = 0 }) {
  const reasons = [];

  if (rrToT1 !== null && rrToT1 < MIN_RR) {
    reasons.push(`R:R to T1 is ${rrToT1}:1 — minimum is ${MIN_RR}:1`);
  }
  if (openPositions >= MAX_POSITIONS) {
    reasons.push(`Already holding ${openPositions} positions (max ${MAX_POSITIONS})`);
  }
  if (drawdownPct > 5) {
    reasons.push(`Drawdown is ${drawdownPct.toFixed(1)}% — exceeds 5% limit`);
  }

  return {
    allowed: reasons.length === 0,
    reasons,
  };
}

export { RISK_FRACTION, MAX_POSITIONS, MIN_RR };
