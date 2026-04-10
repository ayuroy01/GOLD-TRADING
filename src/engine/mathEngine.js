/**
 * Mathematical engine for trading analytics.
 * Computes all metrics from raw trade data arrays.
 */

/**
 * Expected Value per trade.
 * EV = (Win% × AvgWin) - (Loss% × AvgLoss)
 * @param {number[]} rMultiples - Array of R-multiples for closed trades
 * @returns {number}
 */
export function expectedValue(rMultiples) {
  if (!rMultiples.length) return 0;
  const wins = rMultiples.filter(r => r > 0);
  const losses = rMultiples.filter(r => r <= 0);
  const winRate = wins.length / rMultiples.length;
  const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLoss = losses.length ? Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length) : 0;
  return winRate * avgWin - (1 - winRate) * avgLoss;
}

/**
 * Win rate with 95% confidence interval.
 * @param {number[]} rMultiples
 * @returns {{ winRate: number, ciLow: number, ciHigh: number, sampleSize: number }}
 */
export function winRateWithCI(rMultiples) {
  if (!rMultiples.length) return { winRate: 0, ciLow: 0, ciHigh: 0, sampleSize: 0 };
  const wins = rMultiples.filter(r => r > 0).length;
  const n = rMultiples.length;
  const winRate = wins / n;
  const se = Math.sqrt((winRate * (1 - winRate)) / n);
  return {
    winRate,
    ciLow: Math.max(0, winRate - 1.96 * se),
    ciHigh: Math.min(1, winRate + 1.96 * se),
    sampleSize: n,
  };
}

/**
 * Average R-multiple (mean return per trade in R units).
 * @param {number[]} rMultiples
 * @returns {number}
 */
export function averageR(rMultiples) {
  if (!rMultiples.length) return 0;
  return rMultiples.reduce((a, b) => a + b, 0) / rMultiples.length;
}

/**
 * Standard deviation of R-multiples.
 * @param {number[]} rMultiples
 * @returns {number}
 */
export function stdDev(rMultiples) {
  if (rMultiples.length < 2) return 0;
  const mean = averageR(rMultiples);
  const variance = rMultiples.reduce((s, r) => s + (r - mean) ** 2, 0) / rMultiples.length;
  return Math.sqrt(variance);
}

/**
 * Profit factor = gross wins / gross losses.
 * @param {number[]} rMultiples
 * @returns {number}
 */
export function profitFactor(rMultiples) {
  const grossWin = rMultiples.filter(r => r > 0).reduce((a, b) => a + b, 0);
  const grossLoss = Math.abs(rMultiples.filter(r => r <= 0).reduce((a, b) => a + b, 0));
  if (grossLoss === 0) return grossWin > 0 ? Infinity : 0;
  return grossWin / grossLoss;
}

/**
 * Compute equity curve from R-multiples.
 * Returns cumulative R at each trade.
 * @param {number[]} rMultiples
 * @returns {number[]} Cumulative R array (length = rMultiples.length + 1, starts at 0)
 */
export function equityCurve(rMultiples) {
  const curve = [0];
  let cum = 0;
  for (const r of rMultiples) {
    cum += r;
    curve.push(Math.round(cum * 100) / 100);
  }
  return curve;
}

/**
 * Maximum drawdown in R-multiples from peak.
 * @param {number[]} rMultiples
 * @returns {{ maxDrawdown: number, maxDrawdownPct: number, drawdownSeries: number[] }}
 */
export function drawdown(rMultiples) {
  const curve = equityCurve(rMultiples);
  let peak = 0;
  let maxDD = 0;
  const series = [];

  for (const val of curve) {
    if (val > peak) peak = val;
    const dd = peak - val;
    if (dd > maxDD) maxDD = dd;
    series.push(dd);
  }

  // As percentage of peak (if peak > 0)
  const maxDDPct = peak > 0 ? (maxDD / peak) * 100 : 0;

  return {
    maxDrawdown: Math.round(maxDD * 100) / 100,
    maxDrawdownPct: Math.round(maxDDPct * 100) / 100,
    drawdownSeries: series,
  };
}

/**
 * Risk of Ruin — simplified formula.
 * Uses the formula: RoR = ((1 - Edge) / (1 + Edge))^Units
 * where Edge = EV / AvgWin, Units = capital / risk_per_trade
 *
 * This is a basic approximation assuming fixed bet size.
 * @param {number[]} rMultiples
 * @param {number} capitalInR - How many R-units of capital (e.g., 100 means can lose 100R before ruin)
 * @returns {number} Probability of ruin (0 to 1)
 */
export function riskOfRuin(rMultiples, capitalInR = 100) {
  if (rMultiples.length < 10) return null; // Not enough data
  const ev = expectedValue(rMultiples);
  if (ev <= 0) return 1; // Negative expectancy → ruin is certain long-term

  const wins = rMultiples.filter(r => r > 0);
  const avgWin = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 1;
  const edge = Math.min(ev / avgWin, 0.99); // Cap to avoid division issues

  const base = (1 - edge) / (1 + edge);
  return Math.pow(base, capitalInR);
}

/**
 * Maximum consecutive losing streak.
 * @param {number[]} rMultiples
 * @returns {number}
 */
export function maxLosingStreak(rMultiples) {
  let max = 0;
  let current = 0;
  for (const r of rMultiples) {
    if (r <= 0) {
      current++;
      if (current > max) max = current;
    } else {
      current = 0;
    }
  }
  return max;
}

/**
 * Trade distribution by R-multiple buckets.
 * Useful for histogram display.
 * @param {number[]} rMultiples
 * @returns {{ bucket: string, count: number, pct: number }[]}
 */
export function tradeDistribution(rMultiples) {
  const buckets = [
    { label: "< -2R", min: -Infinity, max: -2 },
    { label: "-2R to -1R", min: -2, max: -1 },
    { label: "-1R to 0R", min: -1, max: 0 },
    { label: "0R to 1R", min: 0, max: 1 },
    { label: "1R to 2R", min: 1, max: 2 },
    { label: "2R to 3R", min: 2, max: 3 },
    { label: "> 3R", min: 3, max: Infinity },
  ];

  const n = rMultiples.length || 1;
  return buckets.map(b => {
    const count = rMultiples.filter(r => r >= b.min && r < b.max).length;
    return { bucket: b.label, count, pct: Math.round((count / n) * 100) };
  });
}

/**
 * Sharpe-like ratio: EV / StdDev of R-multiples.
 * @param {number[]} rMultiples
 * @returns {number}
 */
export function sharpeRatio(rMultiples) {
  const sd = stdDev(rMultiples);
  if (sd === 0) return 0;
  return expectedValue(rMultiples) / sd;
}

/**
 * Compute all analytics from trade data.
 * Single entry point for the analytics dashboard.
 * @param {number[]} rMultiples
 * @returns {object} Full analytics object
 */
export function computeAllAnalytics(rMultiples) {
  if (!rMultiples.length) return null;

  const wr = winRateWithCI(rMultiples);
  const wins = rMultiples.filter(r => r > 0);
  const losses = rMultiples.filter(r => r <= 0);
  const ev = expectedValue(rMultiples);
  const avgWinR = wins.length ? wins.reduce((a, b) => a + b, 0) / wins.length : 0;
  const avgLossR = losses.length ? Math.abs(losses.reduce((a, b) => a + b, 0) / losses.length) : 0;
  const dd = drawdown(rMultiples);

  // EV at CI lower bound (pessimistic estimate)
  const evAtCiLow = (wr.ciLow * avgWinR) - ((1 - wr.ciLow) * avgLossR);

  // Phase determination
  const n = rMultiples.length;
  const phase = n < 50 ? 1 : n < 150 ? 2 : 3;

  // Edge status
  const pf = profitFactor(rMultiples);
  let edgeStatus = "Insufficient data";
  if (phase === 3) {
    if (ev > 0.20 && evAtCiLow > 0 && pf > 1.3) edgeStatus = "EDGE VALIDATED";
    else if (ev > 0 && evAtCiLow > -0.3) edgeStatus = "Preliminary positive — continue";
    else edgeStatus = "EDGE NOT CONFIRMED — review system";
  } else if (phase === 2) {
    if (ev > 0 && evAtCiLow > -0.3) edgeStatus = "On track — continue";
    else edgeStatus = "Warning — monitor closely";
  }

  return {
    totalTrades: n,
    wins: wins.length,
    losses: losses.length,
    winRate: wr.winRate,
    ciLow: wr.ciLow,
    ciHigh: wr.ciHigh,
    avgWinR,
    avgLossR,
    expectancy: ev,
    evAtCiLow,
    profitFactor: pf,
    standardDeviation: stdDev(rMultiples),
    sharpe: sharpeRatio(rMultiples),
    maxLosingStreak: maxLosingStreak(rMultiples),
    maxDrawdownR: dd.maxDrawdown,
    maxDrawdownPct: dd.maxDrawdownPct,
    equityCurve: equityCurve(rMultiples),
    drawdownSeries: dd.drawdownSeries,
    distribution: tradeDistribution(rMultiples),
    riskOfRuin: riskOfRuin(rMultiples),
    phase,
    edgeStatus,
  };
}
