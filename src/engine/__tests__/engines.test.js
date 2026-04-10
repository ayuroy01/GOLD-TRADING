/**
 * Comprehensive tests for trading system engines.
 * @vitest-environment jsdom
 */

import { describe, it, expect } from "vitest";

import {
  riskDistance,
  tradeDirection,
  positionSize,
  riskRewardRatio,
  rMultiple,
  bufferedStop,
  computeTrade,
  gateTrade,
} from "../tradeEngine.js";

import {
  validateTrend,
  validateTrigger,
  validateSession,
  checkNoTradeConditions,
  validateTrade,
} from "../validationEngine.js";

import {
  expectedValue,
  winRateWithCI,
  profitFactor,
  equityCurve,
  drawdown,
  maxLosingStreak,
  tradeDistribution,
  riskOfRuin,
  computeAllAnalytics,
} from "../mathEngine.js";

// ---------------------------------------------------------------------------
// tradeEngine
// ---------------------------------------------------------------------------

describe("tradeEngine", () => {
  // 1. riskDistance
  it("riskDistance(2320, 2303) should be 17", () => {
    expect(riskDistance(2320, 2303)).toBe(17);
  });

  // 2. tradeDirection — long
  it("tradeDirection(2320, 2303) should be 'long'", () => {
    expect(tradeDirection(2320, 2303)).toBe("long");
  });

  // 3. tradeDirection — short
  it("tradeDirection(2303, 2320) should be 'short'", () => {
    expect(tradeDirection(2303, 2320)).toBe("short");
  });

  // 4. positionSize — normal case
  it("positionSize(50000, 2320, 2303) — oz ~29.41, lots ~0.29, riskUsd 500", () => {
    const result = positionSize(50000, 2320, 2303);
    // riskUsd = 50000 * 0.01 = 500
    expect(result.riskUsd).toBe(500);
    // oz = 500 / 17 ≈ 29.41
    expect(result.oz).toBeCloseTo(29.41, 1);
    // lots = oz / 100 ≈ 0.29
    expect(result.lots).toBeCloseTo(0.29, 1);
  });

  // 5. positionSize — zero risk
  it("positionSize(50000, 2320, 2320) — zero risk returns 0s", () => {
    const result = positionSize(50000, 2320, 2320);
    expect(result.oz).toBe(0);
    expect(result.lots).toBe(0);
    expect(result.riskUsd).toBe(0);
  });

  // 6. riskRewardRatio — T1 target
  it("riskRewardRatio(2320, 2303, 2340) — reward 20, risk 17, RR ≈ 1.18", () => {
    // reward = |2340 - 2320| = 20, risk = 17
    expect(riskRewardRatio(2320, 2303, 2340)).toBeCloseTo(1.18, 1);
  });

  // 7. riskRewardRatio — T2 target
  it("riskRewardRatio(2320, 2303, 2355.5) — reward 35.5, risk 17, RR ≈ 2.09", () => {
    // reward = |2355.5 - 2320| = 35.5, risk = 17
    expect(riskRewardRatio(2320, 2303, 2355.5)).toBeCloseTo(2.09, 1);
  });

  // 8. rMultiple — long winning trade
  it("rMultiple(2320, 2303, 2340) — long trade profit 20, risk 17, R ≈ 1.18", () => {
    // direction = long, pnl = 2340 - 2320 = 20, risk = 17
    expect(rMultiple(2320, 2303, 2340)).toBeCloseTo(1.18, 1);
  });

  // 9. rMultiple — long losing trade
  it("rMultiple(2320, 2303, 2300) — long trade loss 20, risk 17, R ≈ -1.18", () => {
    // direction = long, pnl = 2300 - 2320 = -20, risk = 17
    expect(rMultiple(2320, 2303, 2300)).toBeCloseTo(-1.18, 1);
  });

  // 10. rMultiple — short winning trade
  it("rMultiple(2320, 2337, 2303) — short trade profit 17, risk 17, R = 1.0", () => {
    // direction = short (stop > entry), pnl = 2320 - 2303 = 17, risk = 17
    expect(rMultiple(2320, 2337, 2303)).toBeCloseTo(1.0, 2);
  });

  // 11. bufferedStop — long direction
  it("bufferedStop('long', 2303, 2320) — should be 2303 - (2320*0.003) ≈ 2296.04", () => {
    // buffer = 2320 * 0.003 = 6.96, result = 2303 - 6.96 = 2296.04
    expect(bufferedStop("long", 2303, 2320)).toBeCloseTo(2296.04, 2);
  });

  // 12. computeTrade — full computation
  it("computeTrade({ equity:50000, entry:2320, stop:2303, target1:2345, target2:2370 }) computes all fields", () => {
    const trade = computeTrade({
      equity: 50000,
      entry: 2320,
      stop: 2303,
      target1: 2345,
      target2: 2370,
    });

    expect(trade.direction).toBe("long");
    expect(trade.risk).toBe(17);
    expect(trade.riskUsd).toBe(500);
    // positionOz = 500 / 17 ≈ 29.41
    expect(trade.positionOz).toBeCloseTo(29.41, 1);
    // positionLots ≈ 0.29
    expect(trade.positionLots).toBeCloseTo(0.29, 1);
    // rrToT1: reward = |2345 - 2320| = 25, risk = 17 → 25/17 ≈ 1.47
    expect(trade.rrToT1).toBeCloseTo(1.47, 1);
    // rrToT2: reward = |2370 - 2320| = 50, risk = 17 → 50/17 ≈ 2.94
    expect(trade.rrToT2).toBeCloseTo(2.94, 1);
    // rrValid: rrToT1 ≈ 1.47, which is below MIN_RR of 1.5
    expect(trade.rrValid).toBe(false);
    expect(trade.riskPct).toBe(1);
    expect(trade.equity).toBe(50000);
  });

  // 13. gateTrade — blocked: RR too low
  it("gateTrade({ rrToT1: 1.2, openPositions: 0 }) — should NOT allow (RR < 1.5)", () => {
    const result = gateTrade({ rrToT1: 1.2, openPositions: 0 });
    expect(result.allowed).toBe(false);
    expect(result.reasons.length).toBeGreaterThan(0);
  });

  // 14. gateTrade — allowed
  it("gateTrade({ rrToT1: 2.0, openPositions: 0 }) — should allow", () => {
    const result = gateTrade({ rrToT1: 2.0, openPositions: 0 });
    expect(result.allowed).toBe(true);
    expect(result.reasons).toHaveLength(0);
  });

  // 15. gateTrade — blocked: max positions reached
  it("gateTrade({ rrToT1: 2.0, openPositions: 2 }) — should NOT allow (max positions)", () => {
    const result = gateTrade({ rrToT1: 2.0, openPositions: 2 });
    expect(result.allowed).toBe(false);
    expect(result.reasons.some(r => r.includes("positions"))).toBe(true);
  });

  // 16. gateTrade — blocked: drawdown exceeded
  it("gateTrade({ rrToT1: 2.0, openPositions: 0, drawdownPct: 6 }) — should NOT allow (drawdown > 5%)", () => {
    const result = gateTrade({ rrToT1: 2.0, openPositions: 0, drawdownPct: 6 });
    expect(result.allowed).toBe(false);
    expect(result.reasons.some(r => r.includes("Drawdown") || r.includes("drawdown"))).toBe(true);
  });
});

// ---------------------------------------------------------------------------
// validationEngine
// ---------------------------------------------------------------------------

describe("validationEngine", () => {
  // 17. validateTrend — valid uptrend
  it("validateTrend — uptrend with all conditions met → valid", () => {
    const result = validateTrend({
      direction: "up",
      priceAboveEma: true,
      higherHighs: true,
      higherLows: true,
      lowerHighs: false,
      lowerLows: false,
    });
    expect(result.valid).toBe(true);
    expect(result.reasons).toHaveLength(0);
  });

  // 18. validateTrend — uptrend missing priceAboveEma
  it("validateTrend — uptrend missing priceAboveEma → invalid with correct reason", () => {
    const result = validateTrend({
      direction: "up",
      priceAboveEma: false,
      higherHighs: true,
      higherLows: true,
      lowerHighs: false,
      lowerLows: false,
    });
    expect(result.valid).toBe(false);
    expect(result.reasons.some(r => r.includes("50 EMA"))).toBe(true);
  });

  // 19. validateTrigger — long with valid bullish trigger
  it("validateTrigger — long with 'Bullish Engulfing' → valid", () => {
    const result = validateTrigger({ trigger: "Bullish Engulfing", direction: "up" });
    expect(result.valid).toBe(true);
    expect(result.reasons).toHaveLength(0);
  });

  // 20. validateTrigger — long with invalid bearish trigger
  it("validateTrigger — long with 'Bearish Engulfing' → invalid", () => {
    const result = validateTrigger({ trigger: "Bearish Engulfing", direction: "up" });
    expect(result.valid).toBe(false);
    expect(result.reasons.length).toBeGreaterThan(0);
  });

  // 21. validateSession — Monday 10:00 UTC → London session
  it("validateSession — Monday 10:00 UTC → valid, session 'London'", () => {
    // Monday = day 1, hour 10 → London (08:00–16:00 UTC, not yet overlap at 13)
    const date = new Date("2024-01-08T10:00:00Z"); // A Monday
    const result = validateSession(date);
    expect(result.valid).toBe(true);
    expect(result.session).toBe("London");
  });

  // 22. validateSession — Monday 14:00 UTC → Overlap session
  it("validateSession — Monday 14:00 UTC → valid, session 'Overlap'", () => {
    // Monday, hour 14 → falls in both London (8-16) and New York (13-21), so Overlap
    const date = new Date("2024-01-08T14:00:00Z");
    const result = validateSession(date);
    expect(result.valid).toBe(true);
    expect(result.session).toBe("Overlap");
  });

  // 23. validateSession — Monday 03:00 UTC → outside sessions
  it("validateSession — Monday 03:00 UTC → invalid (outside sessions)", () => {
    const date = new Date("2024-01-08T03:00:00Z");
    const result = validateSession(date);
    expect(result.valid).toBe(false);
    expect(result.session).toBeNull();
  });

  // 24. validateSession — Friday 19:00 UTC → invalid (Friday late)
  it("validateSession — Friday 19:00 UTC → invalid (Friday late)", () => {
    // Friday = day 5, hour 19 >= 18 → weekend gap risk
    const date = new Date("2024-01-12T19:00:00Z"); // A Friday
    const result = validateSession(date);
    expect(result.valid).toBe(false);
    expect(result.reasons.some(r => r.includes("Friday"))).toBe(true);
  });

  // 25. checkNoTradeConditions — all clear → canTrade true
  it("checkNoTradeConditions — all clear → canTrade true", () => {
    const result = checkNoTradeConditions({
      trendValid: true,
      newsWithin2h: false,
      spreadExceeds050: false,
      openPositions: 0,
      drawdownPct: 0,
      isFridayLate: false,
      rrToT1: 2.0,
    });
    expect(result.canTrade).toBe(true);
    expect(result.blockers).toHaveLength(0);
  });

  // 26. checkNoTradeConditions — newsWithin2h true → canTrade false
  it("checkNoTradeConditions — newsWithin2h true → canTrade false", () => {
    const result = checkNoTradeConditions({
      trendValid: true,
      newsWithin2h: true,
      spreadExceeds050: false,
      openPositions: 0,
      drawdownPct: 0,
      isFridayLate: false,
      rrToT1: 2.0,
    });
    expect(result.canTrade).toBe(false);
    expect(result.blockers.some(b => b.includes("news") || b.includes("News"))).toBe(true);
  });

  // 27. validateTrade full pipeline — valid trade → approved true
  it("validateTrade full pipeline — valid trade → approved: true", () => {
    // Monday 10:00 UTC — London session
    const tradeTime = new Date("2024-01-08T10:00:00Z");

    const result = validateTrade({
      trend: {
        direction: "up",
        priceAboveEma: true,
        higherHighs: true,
        higherLows: true,
        lowerHighs: false,
        lowerLows: false,
      },
      pullback: { zone: "EMA", direction: "up" },
      trigger: { trigger: "Bullish Engulfing", direction: "up" },
      tradeTime,
      noTradeInputs: {
        newsWithin2h: false,
        spreadExceeds050: false,
        openPositions: 0,
        drawdownPct: 0,
      },
      rrToT1: 2.0,
    });

    expect(result.approved).toBe(true);
    expect(result.reasons).toHaveLength(0);
    expect(result.session).toBe("London");
  });

  // 28. validateTrade full pipeline — invalid trigger → approved false
  it("validateTrade full pipeline — invalid trigger → approved: false", () => {
    const tradeTime = new Date("2024-01-08T10:00:00Z");

    const result = validateTrade({
      trend: {
        direction: "up",
        priceAboveEma: true,
        higherHighs: true,
        higherLows: true,
        lowerHighs: false,
        lowerLows: false,
      },
      pullback: { zone: "EMA", direction: "up" },
      // Wrong trigger for a long/up trade
      trigger: { trigger: "Bearish Engulfing", direction: "up" },
      tradeTime,
      noTradeInputs: {
        newsWithin2h: false,
        spreadExceeds050: false,
        openPositions: 0,
        drawdownPct: 0,
      },
      rrToT1: 2.0,
    });

    expect(result.approved).toBe(false);
    expect(result.reasons.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// mathEngine
// ---------------------------------------------------------------------------

describe("mathEngine", () => {
  // Input used across several tests
  const R_MULTIPLES = [2, -1, 1.5, -1, 3, -1];
  //   wins   = [2, 1.5, 3]  → sum 6.5, avg ≈ 2.1667
  //   losses = [-1, -1, -1] → sum -3,  avg 1 (absolute)
  //   winRate = 3/6 = 0.5
  //   EV = 0.5 * 2.1667 - 0.5 * 1 = 1.0833 - 0.5 = 0.5833

  // 29. expectedValue
  it("expectedValue([2, -1, 1.5, -1, 3, -1]) ≈ 0.5833", () => {
    // wins=[2,1.5,3], avgWin=6.5/3≈2.1667, losses=[-1,-1,-1], avgLoss=1
    // EV = 0.5*2.1667 - 0.5*1 ≈ 0.5833
    expect(expectedValue(R_MULTIPLES)).toBeCloseTo(0.5833, 3);
  });

  // 30. winRateWithCI — 6 trades, 3 wins
  it("winRateWithCI — 6 trades, 3 wins → winRate 0.5, CI reasonable", () => {
    const result = winRateWithCI(R_MULTIPLES);
    expect(result.winRate).toBe(0.5);
    expect(result.sampleSize).toBe(6);
    // 95% CI for p=0.5, n=6: se=sqrt(0.25/6)≈0.204, margin≈0.4, so [0.1, 0.9] roughly
    expect(result.ciLow).toBeGreaterThanOrEqual(0);
    expect(result.ciHigh).toBeLessThanOrEqual(1);
    expect(result.ciLow).toBeLessThan(result.winRate);
    expect(result.ciHigh).toBeGreaterThan(result.winRate);
  });

  // 31. profitFactor
  it("profitFactor([2, -1, 1.5, -1, 3, -1]) — grossWin 6.5, grossLoss 3, PF ≈ 2.17", () => {
    // grossWin = 2 + 1.5 + 3 = 6.5, grossLoss = 3
    expect(profitFactor(R_MULTIPLES)).toBeCloseTo(2.17, 1);
  });

  // 32. equityCurve
  it("equityCurve([1, -1, 2, -0.5]) → [0, 1, 0, 2, 1.5]", () => {
    expect(equityCurve([1, -1, 2, -0.5])).toEqual([0, 1, 0, 2, 1.5]);
  });

  // 33. drawdown
  it("drawdown([1, -1, 2, -0.5]) — maxDrawdown should be 1 (from peak 1 to 0)", () => {
    // curve = [0, 1, 0, 2, 1.5]
    // peaks:   0, 1, 1, 2, 2
    // dd:      0, 0, 1, 0, 0.5
    // maxDD = 1
    const result = drawdown([1, -1, 2, -0.5]);
    expect(result.maxDrawdown).toBe(1);
  });

  // 34. maxLosingStreak
  it("maxLosingStreak([1, -1, -1, -1, 2, -1]) → 3", () => {
    expect(maxLosingStreak([1, -1, -1, -1, 2, -1])).toBe(3);
  });

  // 35. tradeDistribution — bucket counts sum to total trades
  it("tradeDistribution — bucket counts sum to total number of trades", () => {
    const dist = tradeDistribution(R_MULTIPLES);
    const totalCount = dist.reduce((sum, b) => sum + b.count, 0);
    expect(totalCount).toBe(R_MULTIPLES.length);
  });

  // 36. riskOfRuin — positive EV → RoR < 1; negative EV → RoR = 1
  it("riskOfRuin — positive EV trades (10+) → RoR < 1", () => {
    // Need >= 10 trades for the function to return a value
    const positiveR = [2, -1, 1.5, -1, 3, -1, 2, 1, -1, 1.5];
    const ror = riskOfRuin(positiveR);
    expect(ror).not.toBeNull();
    expect(ror).toBeLessThan(1);
  });

  it("riskOfRuin — negative EV trades (10+) → RoR = 1", () => {
    const negativeR = [-2, -1, -1.5, 0.5, -3, -1, -2, -1, -1, -1.5];
    const ror = riskOfRuin(negativeR);
    expect(ror).toBe(1);
  });

  // 37. computeAllAnalytics — null for empty array; object for valid data
  it("computeAllAnalytics — returns null for empty array", () => {
    expect(computeAllAnalytics([])).toBeNull();
  });

  it("computeAllAnalytics — returns an analytics object for valid data", () => {
    const result = computeAllAnalytics(R_MULTIPLES);
    expect(result).not.toBeNull();
    expect(typeof result).toBe("object");
    expect(result).toHaveProperty("totalTrades", 6);
    expect(result).toHaveProperty("winRate");
    expect(result).toHaveProperty("expectancy");
    expect(result).toHaveProperty("profitFactor");
    expect(result).toHaveProperty("maxDrawdownR");
    expect(result).toHaveProperty("equityCurve");
    expect(result).toHaveProperty("phase");
    expect(result).toHaveProperty("edgeStatus");
  });

  // 38. computeAllAnalytics — phase determination
  it("computeAllAnalytics — phase 1 for < 50 trades", () => {
    const trades = Array.from({ length: 10 }, (_, i) => (i % 2 === 0 ? 1 : -0.5));
    const result = computeAllAnalytics(trades);
    expect(result.phase).toBe(1);
  });

  it("computeAllAnalytics — phase 2 for 50–149 trades", () => {
    // 50 trades
    const trades = Array.from({ length: 50 }, (_, i) => (i % 2 === 0 ? 1 : -0.5));
    const result = computeAllAnalytics(trades);
    expect(result.phase).toBe(2);
  });

  it("computeAllAnalytics — phase 3 for 150+ trades", () => {
    // 150 trades
    const trades = Array.from({ length: 150 }, (_, i) => (i % 2 === 0 ? 1 : -0.5));
    const result = computeAllAnalytics(trades);
    expect(result.phase).toBe(3);
  });
});
