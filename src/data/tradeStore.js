/**
 * Trade data persistence layer.
 * Uses localStorage with a structured schema.
 */

const TRADES_KEY = "gold_v1_trades";
const SETTINGS_KEY = "gold_v1_settings";

// Default settings
const DEFAULT_SETTINGS = {
  equity: 50000,
  openPositions: 0,
  peakEquity: 50000,
};

/**
 * Trade schema:
 * {
 *   id: number (timestamp),
 *   date: string (ISO),
 *   session: 'London' | 'New York' | 'Overlap',
 *   direction: 'long' | 'short',
 *   trend: { direction, priceAboveEma, higherHighs, higherLows, lowerHighs, lowerLows },
 *   zone: 'EMA' | 'S/R Flip' | '50% Fib',
 *   trigger: string,
 *   entry: number,
 *   stop: number,
 *   t1: number | null,
 *   t2: number | null,
 *   riskDistance: number,
 *   rrToT1: number | null,
 *   positionOz: number,
 *   positionLots: number,
 *   riskUsd: number,
 *   // Validation
 *   validationResult: { approved, reasons },
 *   // Closure
 *   status: 'open' | 'closed',
 *   exitPrice: number | null,
 *   exitReason: string | null,
 *   rMultiple: number | null,
 *   mae: number | null,
 *   mfe: number | null,
 *   error: 'None' | 'Process' | 'Analytical' | 'Timing' | 'Behavioral',
 *   notes: string,
 * }
 */

// --- Trades CRUD ---

export function loadTrades() {
  try {
    const raw = JSON.parse(localStorage.getItem(TRADES_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch {
    return [];
  }
}

export function saveTrades(trades) {
  try {
    localStorage.setItem(TRADES_KEY, JSON.stringify(trades));
  } catch {
    // Storage full or unavailable
  }
}

export function addTrade(trade) {
  const trades = loadTrades();
  trades.push({ ...trade, id: trade.id || Date.now() });
  saveTrades(trades);
  return trades;
}

export function updateTrade(id, updates) {
  const trades = loadTrades();
  const idx = trades.findIndex(t => t.id === id);
  if (idx === -1) return trades;
  trades[idx] = { ...trades[idx], ...updates };
  saveTrades(trades);
  return trades;
}

export function deleteTrade(id) {
  const trades = loadTrades().filter(t => t.id !== id);
  saveTrades(trades);
  return trades;
}

export function getClosedTrades() {
  return loadTrades().filter(t => t.status === "closed" && t.rMultiple != null);
}

export function getOpenTrades() {
  return loadTrades().filter(t => t.status === "open");
}

export function getRMultiples() {
  return getClosedTrades().map(t => t.rMultiple);
}

// --- Settings ---

export function loadSettings() {
  try {
    const raw = JSON.parse(localStorage.getItem(SETTINGS_KEY) || "null");
    return raw ? { ...DEFAULT_SETTINGS, ...raw } : { ...DEFAULT_SETTINGS };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

export function saveSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  } catch {
    // Storage full or unavailable
  }
}

// --- Derived metrics ---

export function currentDrawdownPct() {
  const settings = loadSettings();
  if (settings.peakEquity <= 0) return 0;
  return ((settings.peakEquity - settings.equity) / settings.peakEquity) * 100;
}

// --- Migration from old journal format ---

export function migrateFromOldJournal() {
  const oldKey = "gold_v1_journal";
  try {
    const old = JSON.parse(localStorage.getItem(oldKey) || "[]");
    if (!Array.isArray(old) || old.length === 0) return false;

    const existing = loadTrades();
    if (existing.length > 0) return false; // Don't overwrite

    // Map old format to new
    const migrated = old.map(t => ({
      id: t.id || Date.now() + Math.random(),
      date: t.date,
      session: t.session || "London",
      direction: t.trend === "Up" ? "long" : "short",
      trend: {
        direction: t.trend === "Up" ? "up" : "down",
        priceAboveEma: true,
        higherHighs: t.trend === "Up",
        higherLows: t.trend === "Up",
        lowerHighs: t.trend === "Down",
        lowerLows: t.trend === "Down",
      },
      zone: t.zone || "EMA",
      trigger: t.trigger || "",
      entry: t.entry,
      stop: t.stop,
      t1: t.t1,
      t2: t.t2,
      riskDistance: t.riskDist || Math.abs(t.entry - t.stop),
      rrToT1: t.rrToT1,
      positionOz: 0,
      positionLots: 0,
      riskUsd: 0,
      validationResult: null,
      status: t.status || "closed",
      exitPrice: t.exitPrice,
      exitReason: t.exitReason,
      rMultiple: t.rMultiple,
      mae: t.mae,
      mfe: t.mfe,
      error: t.error || "None",
      notes: t.notes || "",
    }));

    saveTrades(migrated);
    return true;
  } catch {
    return false;
  }
}
