import systemRules from "../../gold_v1_system_rules.json";

const SESSIONS = systemRules.system_metadata.sessions;

/**
 * Validate trend determination (Step 1).
 * User provides their assessment; engine checks internal consistency.
 * @param {{ direction: 'up'|'down', priceAboveEma: boolean, higherHighs: boolean, higherLows: boolean, lowerHighs: boolean, lowerLows: boolean }} params
 * @returns {{ valid: boolean, reasons: string[] }}
 */
export function validateTrend({ direction, priceAboveEma, higherHighs, higherLows, lowerHighs, lowerLows }) {
  const reasons = [];

  if (direction === "up") {
    if (!priceAboveEma) reasons.push("Price must be above 50 EMA for uptrend");
    if (!higherLows) reasons.push("Most recent swing low must be higher than previous");
    if (!higherHighs) reasons.push("Most recent swing high must be higher than previous");
  } else if (direction === "down") {
    if (priceAboveEma) reasons.push("Price must be below 50 EMA for downtrend");
    if (!lowerHighs) reasons.push("Most recent swing high must be lower than previous");
    if (!lowerLows) reasons.push("Most recent swing low must be lower than previous");
  } else {
    reasons.push("Trend direction must be 'up' or 'down'");
  }

  return { valid: reasons.length === 0, reasons };
}

/**
 * Validate pullback zone (Step 2).
 * @param {{ zone: string, direction: 'up'|'down' }} params
 * @returns {{ valid: boolean, reasons: string[] }}
 */
export function validatePullback({ zone, direction }) {
  const validZones = direction === "up"
    ? systemRules.step_2_pullback_identification.uptrend_pullback_zones
    : systemRules.step_2_pullback_identification.downtrend_pullback_zones;

  const zoneMap = {
    "EMA": "50-period EMA on H4",
    "S/R Flip": direction === "up"
      ? "Most recent broken resistance level (S/R flip)"
      : "Most recent broken support level (S/R flip)",
    "50% Fib": "50% retracement of the most recent " + (direction === "up" ? "impulse leg" : "down leg"),
  };

  const mapped = zoneMap[zone];
  if (!mapped) {
    return { valid: false, reasons: [`Unknown pullback zone: ${zone}`] };
  }

  return { valid: true, reasons: [] };
}

/**
 * Validate entry trigger (Step 3).
 * @param {{ trigger: string, direction: 'up'|'down' }} params
 * @returns {{ valid: boolean, reasons: string[] }}
 */
export function validateTrigger({ trigger, direction }) {
  const reasons = [];
  const longTriggers = ["Bullish Engulfing", "Hammer"];
  const shortTriggers = ["Bearish Engulfing", "Shooting Star"];

  if (direction === "up" && !longTriggers.includes(trigger)) {
    reasons.push(`Invalid trigger for long: "${trigger}". Must be: ${longTriggers.join(" or ")}`);
  }
  if (direction === "down" && !shortTriggers.includes(trigger)) {
    reasons.push(`Invalid trigger for short: "${trigger}". Must be: ${shortTriggers.join(" or ")}`);
  }

  return { valid: reasons.length === 0, reasons };
}

/**
 * Validate session timing (Step 7 filter).
 * @param {Date} tradeTime - UTC time of the trade
 * @returns {{ valid: boolean, session: string|null, reasons: string[] }}
 */
export function validateSession(tradeTime) {
  const reasons = [];
  const hour = tradeTime.getUTCHours();
  const day = tradeTime.getUTCDay();

  // Friday after 18:00 UTC
  if (day === 5 && hour >= 18) {
    reasons.push("Friday after 18:00 UTC — weekend gap risk");
    return { valid: false, session: null, reasons };
  }

  // Weekend
  if (day === 0 || day === 6) {
    reasons.push("Weekend — market closed");
    return { valid: false, session: null, reasons };
  }

  // Session detection
  let session = null;
  if (hour >= 8 && hour < 16) session = "London";
  if (hour >= 13 && hour < 21) {
    session = hour < 16 ? "Overlap" : "New York";
  }

  if (!session) {
    reasons.push(`Outside trading sessions. London: 08:00-16:00 UTC, New York: 13:00-21:00 UTC. Current: ${hour}:00 UTC`);
  }

  return { valid: session !== null, session, reasons };
}

/**
 * No-trade conditions check (Step 7).
 * @param {object} params
 * @returns {{ canTrade: boolean, blockers: string[] }}
 */
export function checkNoTradeConditions({
  trendValid = true,
  newsWithin2h = false,
  spreadExceeds050 = false,
  openPositions = 0,
  drawdownPct = 0,
  isFridayLate = false,
  rrToT1 = null,
}) {
  const blockers = [];

  if (!trendValid) {
    blockers.push("Trend is unclear (Step 1 fails)");
  }
  if (newsWithin2h) {
    blockers.push("Major news (FOMC, NFP, CPI) within 2 hours");
  }
  if (spreadExceeds050) {
    blockers.push("Spread exceeds $0.50");
  }
  if (openPositions >= 2) {
    blockers.push(`Already holding ${openPositions} open positions (max 2)`);
  }
  if (drawdownPct > 5) {
    blockers.push(`Drawdown ${drawdownPct.toFixed(1)}% exceeds 5% limit`);
  }
  if (isFridayLate) {
    blockers.push("Friday after 18:00 UTC (weekend gap risk)");
  }
  if (rrToT1 !== null && rrToT1 < 1.5) {
    blockers.push(`R:R to T1 is ${rrToT1}:1 — below minimum 1.5:1`);
  }

  return { canTrade: blockers.length === 0, blockers };
}

/**
 * Run full pre-trade validation pipeline.
 * Returns aggregated pass/fail with all reasons.
 */
export function validateTrade({
  trend,           // { direction, priceAboveEma, higherHighs, higherLows, lowerHighs, lowerLows }
  pullback,        // { zone, direction }
  trigger,         // { trigger, direction }
  tradeTime,       // Date
  noTradeInputs,   // { newsWithin2h, spreadExceeds050, openPositions, drawdownPct }
  rrToT1,          // number
}) {
  const results = [];

  // Step 1: Trend
  const trendResult = validateTrend(trend);
  results.push({ step: "Trend (Step 1)", ...trendResult });

  // Step 2: Pullback
  const pullbackResult = validatePullback(pullback);
  results.push({ step: "Pullback (Step 2)", ...pullbackResult });

  // Step 3: Trigger
  const triggerResult = validateTrigger(trigger);
  results.push({ step: "Trigger (Step 3)", ...triggerResult });

  // Session
  const sessionResult = validateSession(tradeTime);
  results.push({ step: "Session", valid: sessionResult.valid, reasons: sessionResult.reasons });

  // No-trade conditions
  const noTrade = checkNoTradeConditions({
    trendValid: trendResult.valid,
    isFridayLate: tradeTime.getUTCDay() === 5 && tradeTime.getUTCHours() >= 18,
    rrToT1,
    ...noTradeInputs,
  });
  results.push({ step: "No-Trade Gates (Step 7)", valid: noTrade.canTrade, reasons: noTrade.blockers });

  const allValid = results.every(r => r.valid);
  const allReasons = results.flatMap(r => r.reasons);

  return {
    approved: allValid,
    results,
    reasons: allReasons,
    session: sessionResult.session,
  };
}
