/**
 * Mock API helpers for frontend tests.
 * Returns mock data matching the real backend response shapes.
 */

import { vi } from "vitest";

export const mockHealth = {
  status: "ok",
  version: "4.0",
  has_api_key: false,
  system_mode: "paper_trading",
  live_enabled: false,
  strategies: ["trend_pullback", "range_reversion", "breakout_compression"],
  timestamp: "2024-01-15T12:00:00+00:00",
};

export const mockTrades = [
  {
    id: 1001,
    direction: "long",
    entry: 3250.0,
    stop: 3240.0,
    t1: 3270.0,
    rr_to_t1: 2.0,
    status: "open",
    exit_price: null,
    r_multiple: null,
    error_type: "None",
    date: "2024-01-15T10:00:00Z",
    notes: "Test trade",
  },
  {
    id: 1002,
    direction: "short",
    entry: 3280.0,
    stop: 3290.0,
    t1: 3260.0,
    rr_to_t1: 2.0,
    status: "closed",
    exit_price: 3265.0,
    r_multiple: 1.5,
    error_type: "None",
    date: "2024-01-14T08:00:00Z",
    notes: "",
  },
];

export const mockSettings = {
  equity: 50000,
  risk_pct: 1,
  max_positions: 2,
  max_daily_loss_pct: 3,
  max_drawdown_pct: 5,
  max_trades_per_day: 5,
  friday_cutoff_hour: 18,
  cooloff_after_losses: 3,
  max_spread: 0.6,
  min_risk_reward: 1.5,
  min_confidence: 50,
  safe_mode: false,
  system_mode: "paper_trading",
};

export const mockStrategies = {
  strategies: [
    { strategy_name: "trend_pullback", valid: true, direction: "long", entry: 3250, stop: 3240, target_1: 3270, risk_reward: 2.0, confidence: 65, quality_score: 72, rationale: ["Trend aligned"], invalidation_reason: null },
    { strategy_name: "range_reversion", valid: false, direction: null, entry: null, stop: null, target_1: null, risk_reward: null, confidence: 0, quality_score: 0, rationale: [], invalidation_reason: "Not in ranging market" },
    { strategy_name: "breakout_compression", valid: false, direction: null, entry: null, stop: null, target_1: null, risk_reward: null, confidence: 0, quality_score: 0, rationale: [], invalidation_reason: "No compression detected" },
  ],
  valid_count: 1,
};

export const mockRisk = {
  trading_allowed: true,
  blockers: [],
  config: { max_positions: 2, max_spread: 0.6 },
};

export const mockRiskBlocked = {
  trading_allowed: false,
  blockers: [
    { rule: "session", reason: "Outside active trading sessions", severity: "hard" },
  ],
  config: { max_positions: 2, max_spread: 0.6 },
};

export const mockDecision = {
  decision_id: "12345",
  timestamp: "2024-01-15T12:00:00+00:00",
  decision: {
    market_state: "bullish_trend",
    chosen_strategy: "trend_pullback",
    thesis_summary: "Bullish setup",
    invalidation_summary: "Below 3240",
    entry: 3250,
    stop: 3240,
    target_1: 3270,
    target_2: 3290,
    confidence: 65,
    trade_or_no_trade: "trade",
    rationale: ["Trend aligned", "Pullback to EMA"],
    risk_notes: [],
    uncertainty_notes: [],
  },
  setups_evaluated: [],
  risk_blockers: [],
  claude_used: false,
  trade_or_no_trade: "trade",
  strategy: "trend_pullback",
  confidence: 65,
};

export const mockNoTradeDecision = {
  decision_id: "12346",
  timestamp: "2024-01-15T12:00:00+00:00",
  decision: {
    market_state: "transition",
    chosen_strategy: "no_trade",
    thesis_summary: "No trade — no valid setup",
    invalidation_summary: "N/A",
    entry: null,
    stop: null,
    target_1: null,
    target_2: null,
    confidence: 0,
    trade_or_no_trade: "no_trade",
    rationale: ["No valid setup"],
    risk_notes: [],
    uncertainty_notes: [],
  },
  setups_evaluated: [],
  risk_blockers: [],
  claude_used: false,
  trade_or_no_trade: "no_trade",
  strategy: "no_trade",
  confidence: 0,
};

export const mockPaperAccount = {
  balance: 50000,
  equity: 50000,
  unrealized_pnl: 0,
  peak_equity: 50000,
  drawdown_pct: 0,
  daily_pnl: 0,
  open_positions: 0,
  trades_today: 0,
  consecutive_losses: 0,
  initial_balance: 50000,
  mode: "paper",
};

export const mockMetrics = {
  total_trades: 10,
  closed_trades: 8,
  open_trades: 2,
  wins: 5,
  losses: 3,
  win_rate: 0.625,
  ci_low: 0.4,
  ci_high: 0.85,
  avg_win_r: 1.8,
  avg_loss_r: 0.9,
  expectancy: 0.775,
  ev_at_ci_low: 0.2,
  avg_r: 0.5,
  profit_factor: 3.33,
  sharpe: 1.2,
  std_dev: 1.1,
  max_drawdown_r: 2.0,
  max_losing_streak: 2,
  equity_curve: [0, 1.5, 0.5, 2.7, 1.7, 3.5, 2.5, 4.0, 5.2],
  r_multiples: [1.5, -1.0, 2.2, -0.8, 1.8, -1.0, 1.5, 1.0],
  phase: 1,
  edge_status: "Collecting data",
};

export const mockBacktest = {
  backtest: {
    trade_log: [],
    metrics: {
      closed_trades: 15,
      wins: 9,
      losses: 6,
      win_rate: 0.6,
      expectancy: 0.3,
      profit_factor: 1.8,
      sharpe: 0.9,
      max_drawdown_r: 3.0,
      total_r: 4.5,
      equity_curve: [0, 1, 0.5, 1.5, 2.0, 3.0, 2.5, 3.5, 4.0, 4.5],
      by_strategy: { trend_pullback: { trades: 10, win_rate: 0.7, expectancy: 0.5, total_r: 5 } },
    },
    total_candles: 500,
    warmup_candles: 30,
    spread_assumption: 0.4,
    strategies_used: ["trend_pullback", "range_reversion", "breakout_compression"],
  },
  baselines: [
    { name: "no_trade_baseline", description: "Zero-activity baseline", metrics: { total_trades: 0, total_r: 0 } },
    { name: "random_baseline", description: "Random entry baseline", metrics: { closed_trades: 20, win_rate: 0.45, expectancy: -0.1, total_r: -2 } },
  ],
};

/**
 * Create a mock api module. Call this and use vi.mock to replace '../api'.
 */
export function createMockApi(overrides = {}) {
  return {
    health: vi.fn().mockResolvedValue(mockHealth),
    getPrice: vi.fn().mockResolvedValue({ price: 3255.50, bid: 3255.30, ask: 3255.70, spread: 0.40, source: "simulated", timestamp: "2024-01-15T12:00:00Z" }),
    getMacro: vi.fn().mockResolvedValue({ usd_index: 103.5, usd_regime: "neutral", treasury_10y: 4.2, rate_direction: "stable", gold_macro_bias: "neutral", geopolitical_risk: "moderate" }),
    getCalendar: vi.fn().mockResolvedValue({ events: [], high_impact_within_2h: false, nearest_high_impact: null }),
    getStructure: vi.fn().mockResolvedValue({}),
    getFeatures: vi.fn().mockResolvedValue({}),
    getStrategies: vi.fn().mockResolvedValue(mockStrategies),
    getRisk: vi.fn().mockResolvedValue(mockRisk),
    runAnalysis: vi.fn().mockResolvedValue({ analysis: "## Test analysis\nNo trade.", iterations: 1, timestamp: "2024-01-15T12:00:00Z", model: "rule-based (demo)" }),
    getAnalysisLog: vi.fn().mockResolvedValue([]),
    runDecision: vi.fn().mockResolvedValue(mockNoTradeDecision),
    getDecisions: vi.fn().mockResolvedValue([]),
    getDecisionAnalysis: vi.fn().mockResolvedValue({ claude_stats: { count: 0 }, deterministic_stats: { count: 0 } }),
    getPaperAccount: vi.fn().mockResolvedValue(mockPaperAccount),
    getPaperPositions: vi.fn().mockResolvedValue([]),
    getPaperFills: vi.fn().mockResolvedValue([]),
    executePaperTrade: vi.fn().mockResolvedValue({ fill: { status: "filled" }, position_size: {} }),
    closePaperPosition: vi.fn().mockResolvedValue({ status: "closed" }),
    runBacktest: vi.fn().mockResolvedValue(mockBacktest),
    runWalkForward: vi.fn().mockResolvedValue({ n_folds: 2, folds: [], aggregate_oos_metrics: {} }),
    getExperiments: vi.fn().mockResolvedValue([]),
    getTrades: vi.fn().mockResolvedValue(mockTrades),
    logTrade: vi.fn().mockResolvedValue({ id: 1003 }),
    updateTrade: vi.fn().mockResolvedValue({}),
    deleteTrade: vi.fn().mockResolvedValue({}),
    getMetrics: vi.fn().mockResolvedValue(mockMetrics),
    getSettings: vi.fn().mockResolvedValue(mockSettings),
    updateSettings: vi.fn().mockResolvedValue(mockSettings),
    ...overrides,
  };
}
