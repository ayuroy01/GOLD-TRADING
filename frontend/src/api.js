/**
 * API client for Gold Intelligence System backend v4.
 */

const BASE = "/api";

async function request(path, options = {}) {
  const url = `${BASE}${path}`;
  const config = {
    headers: { "Content-Type": "application/json" },
    ...options,
  };
  if (config.body && typeof config.body === "object") {
    config.body = JSON.stringify(config.body);
  }
  try {
    const res = await fetch(url, config);
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `HTTP ${res.status}`);
    return data;
  } catch (err) {
    console.error(`API ${path}:`, err);
    throw err;
  }
}

export const api = {
  // Health & readiness
  health: () => request("/health"),
  readiness: () => request("/readiness"),

  // Historical data import (Phase 2)
  listHistorical: () => request("/historical/list"),
  runHistoricalBacktest: (filename, timeframe = "1h", spread = 0.4) =>
    request("/backtest/historical", {
      method: "POST",
      body: { filename, timeframe, spread },
    }),

  // Market Data
  getPrice: () => request("/price"),
  getMacro: () => request("/macro"),
  getCalendar: () => request("/calendar"),
  getStructure: () => request("/structure"),
  getFeatures: () => request("/features"),

  // Strategies
  getStrategies: () => request("/strategies"),

  // Risk
  getRisk: () => request("/risk"),

  // Analysis (legacy)
  runAnalysis: (context = "") =>
    request("/analyze", { method: "POST", body: { context } }),
  getAnalysisLog: (limit = 20) => request(`/analysis-log?limit=${limit}`),

  // Structured Decision Pipeline
  runDecision: (useClaude = true) =>
    request("/decide", { method: "POST", body: { use_claude: useClaude } }),
  getDecisions: (limit = 20) => request(`/decisions?limit=${limit}`),
  getDecisionAnalysis: () => request("/decisions/analysis"),

  // Paper Trading
  getPaperAccount: () => request("/paper/account"),
  getPaperPositions: () => request("/paper/positions"),
  getPaperFills: (limit = 50) => request(`/paper/fills?limit=${limit}`),
  executePaperTrade: (decisionId, useClaude = false) =>
    request("/paper/execute", {
      method: "POST",
      body: { decision_id: decisionId, use_claude: useClaude },
    }),
  closePaperPosition: (positionId, price) =>
    request("/paper/close", {
      method: "POST",
      body: { position_id: positionId, price },
    }),

  // Backtesting
  runBacktest: (candles = 500, spread = 0.4) =>
    request("/backtest", {
      method: "POST",
      body: { candles, spread },
    }),
  runWalkForward: (candles = 500, folds = 3) =>
    request("/backtest/walk-forward", {
      method: "POST",
      body: { candles, folds },
    }),

  // Experiments
  getExperiments: () => request("/experiments"),

  // Trades (journal)
  getTrades: (status) =>
    request(`/trades${status ? `?status=${status}` : ""}`),
  logTrade: (trade) =>
    request("/trades", { method: "POST", body: trade }),
  updateTrade: (id, updates) =>
    request(`/trades/${id}`, { method: "PUT", body: updates }),
  deleteTrade: (id) =>
    request(`/trades/${id}`, { method: "DELETE" }),

  // Metrics
  getMetrics: () => request("/metrics"),

  // Settings
  getSettings: () => request("/settings"),
  updateSettings: (settings) =>
    request("/settings", { method: "POST", body: settings }),
};
