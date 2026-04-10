import { useState, useMemo } from "react";
import {
  computeTrade,
  gateTrade,
  riskDistance,
  riskRewardRatio,
  positionSize,
  rMultiple,
  bufferedStop,
} from "../engine/tradeEngine.js";
import {
  validateTrade,
  validateTrend,
  validatePullback,
  validateTrigger,
  validateSession,
  checkNoTradeConditions,
} from "../engine/validationEngine.js";
import {
  addTrade,
  loadTrades,
  loadSettings,
  saveSettings,
  getOpenTrades,
  currentDrawdownPct,
} from "../data/tradeStore.js";

// ─── Design tokens ───────────────────────────────────────────────────────────
const C = {
  bg: "#0a0e17",
  card: "#111827",
  border: "#1e293b",
  text: "#e2e8f0",
  muted: "#64748b",
  green: "#10b981",
  red: "#ef4444",
  accent: "#3b82f6",
  inputBg: "#1e293b",
  yellow: "#f59e0b",
};

// ─── Shared style helpers ─────────────────────────────────────────────────────
const S = {
  card: {
    background: C.card,
    border: `1px solid ${C.border}`,
    borderRadius: 8,
    padding: "20px 24px",
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: C.muted,
    marginBottom: 6,
    fontFamily: "system-ui, sans-serif",
  },
  input: {
    width: "100%",
    background: C.inputBg,
    border: `1px solid ${C.border}`,
    borderRadius: 5,
    color: C.text,
    padding: "8px 12px",
    fontSize: 14,
    fontFamily: "monospace",
    outline: "none",
    boxSizing: "border-box",
  },
  select: {
    width: "100%",
    background: C.inputBg,
    border: `1px solid ${C.border}`,
    borderRadius: 5,
    color: C.text,
    padding: "8px 12px",
    fontSize: 14,
    fontFamily: "system-ui, sans-serif",
    outline: "none",
    cursor: "pointer",
    boxSizing: "border-box",
  },
  row: {
    display: "grid",
    gap: 16,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: "0.1em",
    textTransform: "uppercase",
    color: C.muted,
    marginBottom: 14,
    paddingBottom: 8,
    borderBottom: `1px solid ${C.border}`,
    fontFamily: "system-ui, sans-serif",
  },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function Field({ label, children, style }) {
  return (
    <div style={{ marginBottom: 14, ...style }}>
      <label style={S.label}>{label}</label>
      {children}
    </div>
  );
}

function NumInput({ value, onChange, placeholder, min, step }) {
  return (
    <input
      type="number"
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      min={min}
      step={step || "any"}
      style={S.input}
    />
  );
}

function ToggleBtn({ label, active, onClick, activeColor }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        padding: "9px 0",
        borderRadius: 5,
        border: `1px solid ${active ? (activeColor || C.accent) : C.border}`,
        background: active ? (activeColor || C.accent) + "22" : "transparent",
        color: active ? (activeColor || C.accent) : C.muted,
        fontWeight: 700,
        fontSize: 13,
        cursor: "pointer",
        fontFamily: "system-ui, sans-serif",
        transition: "all 0.15s",
        letterSpacing: "0.05em",
      }}
    >
      {label}
    </button>
  );
}

function CheckRow({ label, checked, onChange }) {
  return (
    <label
      style={{
        display: "flex",
        alignItems: "center",
        gap: 10,
        fontSize: 13,
        color: checked ? C.text : C.muted,
        cursor: "pointer",
        marginBottom: 8,
        fontFamily: "system-ui, sans-serif",
        userSelect: "none",
      }}
    >
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onChange(e.target.checked)}
        style={{ accentColor: C.accent, width: 15, height: 15 }}
      />
      {label}
    </label>
  );
}

function MetricRow({ label, value, color, mono }) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        padding: "7px 0",
        borderBottom: `1px solid ${C.border}`,
      }}
    >
      <span style={{ fontSize: 12, color: C.muted, fontFamily: "system-ui, sans-serif" }}>
        {label}
      </span>
      <span
        style={{
          fontSize: 14,
          fontWeight: 700,
          color: color || C.text,
          fontFamily: mono !== false ? "monospace" : "system-ui, sans-serif",
        }}
      >
        {value}
      </span>
    </div>
  );
}

function ValidationRow({ step, valid, reasons }) {
  return (
    <div
      style={{
        padding: "10px 14px",
        borderRadius: 6,
        background: valid ? C.green + "11" : C.red + "11",
        border: `1px solid ${valid ? C.green + "33" : C.red + "33"}`,
        marginBottom: 8,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 16, lineHeight: 1 }}>{valid ? "✓" : "✗"}</span>
        <span
          style={{
            fontSize: 12,
            fontWeight: 700,
            color: valid ? C.green : C.red,
            fontFamily: "system-ui, sans-serif",
            flex: 1,
          }}
        >
          {step}
        </span>
        <span
          style={{
            fontSize: 11,
            fontWeight: 700,
            color: valid ? C.green : C.red,
            fontFamily: "system-ui, sans-serif",
            letterSpacing: "0.08em",
          }}
        >
          {valid ? "PASS" : "FAIL"}
        </span>
      </div>
      {!valid && reasons && reasons.length > 0 && (
        <ul style={{ margin: "8px 0 0 26px", padding: 0, listStyle: "disc" }}>
          {reasons.map((r, i) => (
            <li key={i} style={{ fontSize: 11, color: C.red, marginBottom: 2, fontFamily: "system-ui, sans-serif" }}>
              {r}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SectionHeader({ children }) {
  return <div style={S.sectionTitle}>{children}</div>;
}

function PanelTab({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        flex: 1,
        padding: "12px 0",
        background: active ? C.accent + "22" : "transparent",
        border: "none",
        borderBottom: `2px solid ${active ? C.accent : "transparent"}`,
        color: active ? C.accent : C.muted,
        fontWeight: 700,
        fontSize: 13,
        cursor: "pointer",
        fontFamily: "system-ui, sans-serif",
        letterSpacing: "0.06em",
        textTransform: "uppercase",
        transition: "all 0.15s",
      }}
    >
      {label}
    </button>
  );
}

// ─── Main component ───────────────────────────────────────────────────────────

export default function TradeExecutionPanel({ onTradeUpdate }) {
  const settings = loadSettings();

  // ── Tab state ──
  const [activeTab, setActiveTab] = useState("pretrade"); // 'pretrade' | 'close'

  // ── Pre-trade form state ──
  const [equity, setEquity] = useState(String(settings.equity || 50000));
  const [direction, setDirection] = useState("long"); // 'long' | 'short'

  // Trend checkboxes
  const [priceAboveEma, setPriceAboveEma] = useState(false);
  const [higherHighs, setHigherHighs] = useState(false);
  const [higherLows, setHigherLows] = useState(false);
  const [lowerHighs, setLowerHighs] = useState(false);
  const [lowerLows, setLowerLows] = useState(false);

  // Pullback zone
  const [zone, setZone] = useState("EMA");

  // Trigger
  const [trigger, setTrigger] = useState("");

  // Price inputs
  const [entry, setEntry] = useState("");
  const [stop, setStop] = useState("");
  const [target1, setTarget1] = useState("");
  const [target2, setTarget2] = useState("");

  // No-trade filters
  const [newsWithin2h, setNewsWithin2h] = useState(false);
  const [spreadExceeds050, setSpreadExceeds050] = useState(false);

  // Execution feedback
  const [executeFeedback, setExecuteFeedback] = useState(null); // null | 'success' | 'error'

  // ── Close Trade form state ──
  const [selectedTradeId, setSelectedTradeId] = useState("");
  const [exitPrice, setExitPrice] = useState("");
  const [exitReason, setExitReason] = useState("T1 hit");
  const [errorType, setErrorType] = useState("None");
  const [notes, setNotes] = useState("");
  const [closeFeedback, setCloseFeedback] = useState(null);

  // ── Derived: open trades (refreshed on render) ──
  const openTrades = useMemo(() => getOpenTrades(), [executeFeedback, closeFeedback]);

  // ── Derived: reset trigger when direction changes ──
  const triggerOptions =
    direction === "long"
      ? ["Bullish Engulfing", "Hammer"]
      : ["Bearish Engulfing", "Shooting Star"];

  // ── Computed trade metrics ──
  const computed = useMemo(() => {
    const eq = parseFloat(equity);
    const en = parseFloat(entry);
    const sl = parseFloat(stop);
    const t1 = parseFloat(target1);
    const t2 = parseFloat(target2);

    if (!eq || !en || !sl || isNaN(eq) || isNaN(en) || isNaN(sl) || en === sl) {
      return null;
    }

    return computeTrade({
      equity: eq,
      entry: en,
      stop: sl,
      target1: isNaN(t1) ? null : t1,
      target2: isNaN(t2) ? null : t2,
    });
  }, [equity, entry, stop, target1, target2]);

  // ── Full validation result ──
  const validation = useMemo(() => {
    if (!computed) return null;

    const openPositions = openTrades.length;
    const drawdownPct = currentDrawdownPct();

    const trendDirection = direction === "long" ? "up" : "down";

    return validateTrade({
      trend: {
        direction: trendDirection,
        priceAboveEma,
        higherHighs,
        higherLows,
        lowerHighs,
        lowerLows,
      },
      pullback: { zone, direction: trendDirection },
      trigger: { trigger, direction: trendDirection },
      tradeTime: new Date(),
      noTradeInputs: {
        newsWithin2h,
        spreadExceeds050,
        openPositions,
        drawdownPct,
      },
      rrToT1: computed.rrToT1,
    });
  }, [
    computed,
    direction,
    priceAboveEma,
    higherHighs,
    higherLows,
    lowerHighs,
    lowerLows,
    zone,
    trigger,
    newsWithin2h,
    spreadExceeds050,
    openTrades.length,
  ]);

  // ── Gate check ──
  const gate = useMemo(() => {
    if (!computed) return null;
    return gateTrade({
      rrToT1: computed.rrToT1,
      openPositions: openTrades.length,
      drawdownPct: currentDrawdownPct(),
    });
  }, [computed, openTrades.length]);

  // ── Close trade computed R-multiple ──
  const closeComputed = useMemo(() => {
    const trade = openTrades.find((t) => String(t.id) === String(selectedTradeId));
    if (!trade) return null;
    const ex = parseFloat(exitPrice);
    if (isNaN(ex) || ex <= 0) return null;
    const rm = rMultiple(trade.entry, trade.stop, ex);
    return { rm, trade };
  }, [selectedTradeId, exitPrice, openTrades]);

  // ── Handlers ──
  function handleDirectionChange(dir) {
    setDirection(dir);
    setTrigger(""); // reset trigger
  }

  function handleExecuteTrade() {
    if (!computed || !validation || !validation.approved) return;

    const settings = loadSettings();
    const trendDirection = direction === "long" ? "up" : "down";
    const sessionResult = validateSession(new Date());

    const trade = {
      id: Date.now(),
      date: new Date().toISOString(),
      session: sessionResult.session || "Unknown",
      direction,
      trend: {
        direction: trendDirection,
        priceAboveEma,
        higherHighs,
        higherLows,
        lowerHighs,
        lowerLows,
      },
      zone,
      trigger,
      entry: parseFloat(entry),
      stop: parseFloat(stop),
      t1: parseFloat(target1) || null,
      t2: parseFloat(target2) || null,
      riskDistance: computed.risk,
      rrToT1: computed.rrToT1,
      rrToT2: computed.rrToT2,
      positionOz: computed.positionOz,
      positionLots: computed.positionLots,
      riskUsd: computed.riskUsd,
      validationResult: { approved: validation.approved, reasons: validation.reasons },
      status: "open",
      exitPrice: null,
      exitReason: null,
      rMultiple: null,
      mae: null,
      mfe: null,
      error: "None",
      notes: "",
    };

    try {
      addTrade(trade);
      setExecuteFeedback("success");
      if (onTradeUpdate) onTradeUpdate();
      // Reset form
      setEntry("");
      setStop("");
      setTarget1("");
      setTarget2("");
      setPriceAboveEma(false);
      setHigherHighs(false);
      setHigherLows(false);
      setLowerHighs(false);
      setLowerLows(false);
      setNewsWithin2h(false);
      setSpreadExceeds050(false);
      setTrigger("");
      setTimeout(() => setExecuteFeedback(null), 3000);
    } catch {
      setExecuteFeedback("error");
      setTimeout(() => setExecuteFeedback(null), 3000);
    }
  }

  function handleCloseTrade() {
    if (!closeComputed) return;
    const { rm } = closeComputed;
    const ex = parseFloat(exitPrice);

    try {
      // Read, mutate, and re-persist — mirrors tradeStore's updateTrade pattern.
      const TRADES_KEY = "gold_v1_trades";
      const raw = JSON.parse(localStorage.getItem(TRADES_KEY) || "[]");
      const idx = raw.findIndex((t) => String(t.id) === String(selectedTradeId));
      if (idx === -1) {
        setCloseFeedback("error");
        return;
      }
      raw[idx] = {
        ...raw[idx],
        status: "closed",
        exitPrice: ex,
        exitReason,
        rMultiple: rm,
        error: errorType,
        notes,
      };
      localStorage.setItem(TRADES_KEY, JSON.stringify(raw));

      setCloseFeedback("success");
      setSelectedTradeId("");
      setExitPrice("");
      setExitReason("T1 hit");
      setErrorType("None");
      setNotes("");
      if (onTradeUpdate) onTradeUpdate();
      setTimeout(() => setCloseFeedback(null), 3000);
    } catch {
      setCloseFeedback("error");
      setTimeout(() => setCloseFeedback(null), 3000);
    }
  }

  // ── Render helpers ──
  const hasAllPrices = computed !== null;
  const isApproved = validation?.approved === true;
  const isBlocked = validation !== null && !isApproved;

  const selectedOpenTrade = openTrades.find(
    (t) => String(t.id) === String(selectedTradeId)
  );

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div
      style={{
        background: C.bg,
        minHeight: "100%",
        padding: "0 0 40px 0",
        fontFamily: "system-ui, -apple-system, sans-serif",
        color: C.text,
      }}
    >
      {/* Tab Bar */}
      <div
        style={{
          display: "flex",
          background: C.card,
          borderBottom: `1px solid ${C.border}`,
          marginBottom: 20,
        }}
      >
        <PanelTab
          label="Pre-Trade Validation"
          active={activeTab === "pretrade"}
          onClick={() => setActiveTab("pretrade")}
        />
        <PanelTab
          label="Close Trade"
          active={activeTab === "close"}
          onClick={() => setActiveTab("close")}
        />
      </div>

      {/* ═══════════════════════════════════════════════════════
          PRE-TRADE PANEL
      ═══════════════════════════════════════════════════════ */}
      {activeTab === "pretrade" && (
        <div>
          {/* Account & Direction */}
          <div style={S.card}>
            <SectionHeader>Account & Direction</SectionHeader>

            <Field label="Account Equity (USD)">
              <NumInput
                value={equity}
                onChange={setEquity}
                placeholder="50000"
                min="0"
                step="100"
              />
            </Field>

            <Field label="Trade Direction">
              <div style={{ display: "flex", gap: 8 }}>
                <ToggleBtn
                  label="▲ LONG"
                  active={direction === "long"}
                  activeColor={C.green}
                  onClick={() => handleDirectionChange("long")}
                />
                <ToggleBtn
                  label="▼ SHORT"
                  active={direction === "short"}
                  activeColor={C.red}
                  onClick={() => handleDirectionChange("short")}
                />
              </div>
            </Field>
          </div>

          {/* Trend Confirmation */}
          <div style={S.card}>
            <SectionHeader>Step 1 — Trend Confirmation</SectionHeader>

            <CheckRow
              label={
                direction === "long"
                  ? "Price is ABOVE 50-period EMA"
                  : "Price is BELOW 50-period EMA"
              }
              checked={priceAboveEma}
              onChange={setPriceAboveEma}
            />

            {direction === "long" ? (
              <>
                <CheckRow
                  label="Higher Highs — most recent swing high > previous"
                  checked={higherHighs}
                  onChange={setHigherHighs}
                />
                <CheckRow
                  label="Higher Lows — most recent swing low > previous"
                  checked={higherLows}
                  onChange={setHigherLows}
                />
              </>
            ) : (
              <>
                <CheckRow
                  label="Lower Highs — most recent swing high < previous"
                  checked={lowerHighs}
                  onChange={setLowerHighs}
                />
                <CheckRow
                  label="Lower Lows — most recent swing low < previous"
                  checked={lowerLows}
                  onChange={setLowerLows}
                />
              </>
            )}
          </div>

          {/* Pullback Zone */}
          <div style={S.card}>
            <SectionHeader>Step 2 — Pullback Zone</SectionHeader>

            <Field label="Zone Type">
              <select
                value={zone}
                onChange={(e) => setZone(e.target.value)}
                style={S.select}
              >
                <option value="EMA">50-period EMA</option>
                <option value="S/R Flip">S/R Flip</option>
                <option value="50% Fib">50% Fibonacci Retracement</option>
              </select>
            </Field>
          </div>

          {/* Entry Trigger */}
          <div style={S.card}>
            <SectionHeader>Step 3 — Entry Trigger</SectionHeader>

            <Field label={`Candlestick Pattern (${direction === "long" ? "Bullish" : "Bearish"})`}>
              <select
                value={trigger}
                onChange={(e) => setTrigger(e.target.value)}
                style={S.select}
              >
                <option value="">— Select Trigger —</option>
                {triggerOptions.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
          </div>

          {/* Price Inputs */}
          <div style={S.card}>
            <SectionHeader>Price Levels</SectionHeader>

            <div style={{ ...S.row, gridTemplateColumns: "1fr 1fr" }}>
              <Field label="Entry Price" style={{ marginBottom: 0 }}>
                <NumInput value={entry} onChange={setEntry} placeholder="2650.00" step="0.01" />
              </Field>
              <Field label="Stop Loss" style={{ marginBottom: 0 }}>
                <NumInput value={stop} onChange={setStop} placeholder="2640.00" step="0.01" />
              </Field>
            </div>

            <div style={{ ...S.row, gridTemplateColumns: "1fr 1fr", marginTop: 0 }}>
              <Field label="Target 1 (T1)" style={{ marginBottom: 0 }}>
                <NumInput value={target1} onChange={setTarget1} placeholder="2675.00" step="0.01" />
              </Field>
              <Field label="Target 2 (T2) — optional" style={{ marginBottom: 0 }}>
                <NumInput value={target2} onChange={setTarget2} placeholder="2695.00" step="0.01" />
              </Field>
            </div>
          </div>

          {/* No-Trade Filters */}
          <div style={S.card}>
            <SectionHeader>No-Trade Filters</SectionHeader>
            <CheckRow
              label="Major news event within 2 hours (FOMC, NFP, CPI)"
              checked={newsWithin2h}
              onChange={setNewsWithin2h}
            />
            <CheckRow
              label="Spread exceeds $0.50"
              checked={spreadExceeds050}
              onChange={setSpreadExceeds050}
            />
          </div>

          {/* ── Computed Metrics ── */}
          {hasAllPrices && (
            <div style={S.card}>
              <SectionHeader>Computed Trade Metrics</SectionHeader>

              <MetricRow
                label="Direction (auto)"
                value={computed.direction.toUpperCase()}
                color={computed.direction === "long" ? C.green : C.red}
                mono={false}
              />
              <MetricRow
                label="Risk Distance"
                value={`$${computed.risk.toFixed(2)}`}
              />
              <MetricRow
                label="Risk in USD (1% of equity)"
                value={`$${computed.riskUsd.toFixed(2)}`}
                color={C.accent}
              />
              <MetricRow
                label="Position Size"
                value={`${computed.positionOz} oz / ${computed.positionLots} lots`}
              />
              <MetricRow
                label="R:R to T1"
                value={
                  computed.rrToT1 !== null
                    ? `${computed.rrToT1}:1`
                    : "—"
                }
                color={
                  computed.rrToT1 === null
                    ? C.muted
                    : computed.rrToT1 >= 1.5
                    ? C.green
                    : C.red
                }
              />
              <MetricRow
                label="R:R to T2"
                value={
                  computed.rrToT2 !== null
                    ? `${computed.rrToT2}:1`
                    : "—"
                }
                color={
                  computed.rrToT2 === null
                    ? C.muted
                    : computed.rrToT2 >= 2
                    ? C.green
                    : C.yellow
                }
              />
            </div>
          )}

          {/* ── Validation Panel ── */}
          {validation && (
            <div style={S.card}>
              <SectionHeader>Validation Results</SectionHeader>

              {validation.results.map((r, i) => (
                <ValidationRow key={i} step={r.step} valid={r.valid} reasons={r.reasons} />
              ))}

              {/* Overall verdict */}
              <div
                style={{
                  marginTop: 16,
                  padding: "14px 18px",
                  borderRadius: 7,
                  background: isApproved ? C.green + "18" : C.red + "18",
                  border: `2px solid ${isApproved ? C.green : C.red}`,
                  textAlign: "center",
                }}
              >
                <div
                  style={{
                    fontSize: 18,
                    fontWeight: 900,
                    letterSpacing: "0.12em",
                    color: isApproved ? C.green : C.red,
                    fontFamily: "monospace",
                    marginBottom: isApproved ? 0 : 8,
                  }}
                >
                  {isApproved ? "✓  APPROVED" : "✗  BLOCKED"}
                </div>
                {isBlocked && validation.reasons.length > 0 && (
                  <ul style={{ margin: "6px 0 0 0", padding: "0 0 0 20px", textAlign: "left" }}>
                    {validation.reasons.map((r, i) => (
                      <li
                        key={i}
                        style={{
                          fontSize: 12,
                          color: C.red,
                          marginBottom: 3,
                          fontFamily: "system-ui, sans-serif",
                        }}
                      >
                        {r}
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {/* Execute button */}
              <div style={{ marginTop: 16 }}>
                {isApproved ? (
                  <button
                    onClick={handleExecuteTrade}
                    style={{
                      width: "100%",
                      padding: "13px 0",
                      background: C.green,
                      border: "none",
                      borderRadius: 6,
                      color: "#fff",
                      fontSize: 14,
                      fontWeight: 800,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      cursor: "pointer",
                      fontFamily: "system-ui, sans-serif",
                    }}
                  >
                    Execute Trade
                  </button>
                ) : (
                  <button
                    disabled
                    style={{
                      width: "100%",
                      padding: "13px 0",
                      background: C.border,
                      border: `1px solid ${C.red}44`,
                      borderRadius: 6,
                      color: C.muted,
                      fontSize: 14,
                      fontWeight: 800,
                      letterSpacing: "0.08em",
                      textTransform: "uppercase",
                      cursor: "not-allowed",
                      fontFamily: "system-ui, sans-serif",
                    }}
                  >
                    Execution Blocked
                  </button>
                )}

                {executeFeedback === "success" && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "10px 14px",
                      background: C.green + "22",
                      border: `1px solid ${C.green}44`,
                      borderRadius: 5,
                      color: C.green,
                      fontSize: 13,
                      fontFamily: "system-ui, sans-serif",
                      textAlign: "center",
                    }}
                  >
                    Trade saved successfully
                  </div>
                )}
                {executeFeedback === "error" && (
                  <div
                    style={{
                      marginTop: 10,
                      padding: "10px 14px",
                      background: C.red + "22",
                      border: `1px solid ${C.red}44`,
                      borderRadius: 5,
                      color: C.red,
                      fontSize: 13,
                      fontFamily: "system-ui, sans-serif",
                      textAlign: "center",
                    }}
                  >
                    Failed to save trade
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          CLOSE TRADE PANEL
      ═══════════════════════════════════════════════════════ */}
      {activeTab === "close" && (
        <div>
          <div style={S.card}>
            <SectionHeader>Select Open Trade</SectionHeader>

            {openTrades.length === 0 ? (
              <div
                style={{
                  textAlign: "center",
                  color: C.muted,
                  fontSize: 13,
                  padding: "24px 0",
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                No open trades found
              </div>
            ) : (
              <Field label="Open Trade">
                <select
                  value={selectedTradeId}
                  onChange={(e) => {
                    setSelectedTradeId(e.target.value);
                    setExitPrice("");
                  }}
                  style={S.select}
                >
                  <option value="">— Select a trade —</option>
                  {openTrades.map((t) => (
                    <option key={t.id} value={t.id}>
                      {t.direction.toUpperCase()} @ {t.entry} | Stop {t.stop} |{" "}
                      {new Date(t.date).toLocaleDateString()}
                    </option>
                  ))}
                </select>
              </Field>
            )}

            {/* Show selected trade summary */}
            {selectedOpenTrade && (
              <div
                style={{
                  background: C.inputBg,
                  borderRadius: 6,
                  padding: "12px 14px",
                  marginBottom: 14,
                  border: `1px solid ${C.border}`,
                }}
              >
                <MetricRow
                  label="Direction"
                  value={selectedOpenTrade.direction.toUpperCase()}
                  color={selectedOpenTrade.direction === "long" ? C.green : C.red}
                  mono={false}
                />
                <MetricRow label="Entry" value={`$${selectedOpenTrade.entry}`} />
                <MetricRow label="Stop" value={`$${selectedOpenTrade.stop}`} />
                {selectedOpenTrade.t1 && (
                  <MetricRow label="T1" value={`$${selectedOpenTrade.t1}`} />
                )}
                {selectedOpenTrade.t2 && (
                  <MetricRow label="T2" value={`$${selectedOpenTrade.t2}`} />
                )}
                <MetricRow label="Risk Distance" value={`$${selectedOpenTrade.riskDistance}`} />
                <MetricRow label="Position" value={`${selectedOpenTrade.positionOz} oz`} />
              </div>
            )}
          </div>

          {selectedOpenTrade && (
            <div style={S.card}>
              <SectionHeader>Exit Details</SectionHeader>

              <Field label="Exit Price">
                <NumInput
                  value={exitPrice}
                  onChange={setExitPrice}
                  placeholder="Enter exit price"
                  step="0.01"
                />
              </Field>

              {/* R-multiple preview */}
              {closeComputed && (
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: 6,
                    background:
                      closeComputed.rm > 0
                        ? C.green + "18"
                        : closeComputed.rm < 0
                        ? C.red + "18"
                        : C.inputBg,
                    border: `1px solid ${
                      closeComputed.rm > 0
                        ? C.green + "44"
                        : closeComputed.rm < 0
                        ? C.red + "44"
                        : C.border
                    }`,
                    marginBottom: 14,
                    textAlign: "center",
                  }}
                >
                  <div style={{ fontSize: 11, color: C.muted, marginBottom: 4, fontFamily: "system-ui, sans-serif", textTransform: "uppercase", letterSpacing: "0.08em" }}>
                    R-Multiple
                  </div>
                  <div
                    style={{
                      fontSize: 28,
                      fontWeight: 900,
                      fontFamily: "monospace",
                      color:
                        closeComputed.rm > 0
                          ? C.green
                          : closeComputed.rm < 0
                          ? C.red
                          : C.muted,
                    }}
                  >
                    {closeComputed.rm > 0 ? "+" : ""}
                    {closeComputed.rm}R
                  </div>
                </div>
              )}

              <Field label="Exit Reason">
                <select
                  value={exitReason}
                  onChange={(e) => setExitReason(e.target.value)}
                  style={S.select}
                >
                  <option>T1 hit</option>
                  <option>T2 hit</option>
                  <option>Stop hit</option>
                  <option>Trailing stop</option>
                  <option>Time stop</option>
                  <option>Manual</option>
                </select>
              </Field>

              <Field label="Error Type">
                <select
                  value={errorType}
                  onChange={(e) => setErrorType(e.target.value)}
                  style={S.select}
                >
                  <option>None</option>
                  <option>Process</option>
                  <option>Analytical</option>
                  <option>Timing</option>
                  <option>Behavioral</option>
                </select>
              </Field>

              <Field label="Notes">
                <textarea
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  placeholder="Post-trade observations, market conditions, lessons..."
                  rows={4}
                  style={{
                    ...S.input,
                    resize: "vertical",
                    fontFamily: "system-ui, sans-serif",
                    lineHeight: 1.5,
                  }}
                />
              </Field>

              <button
                onClick={handleCloseTrade}
                disabled={!closeComputed}
                style={{
                  width: "100%",
                  padding: "13px 0",
                  background: closeComputed ? C.accent : C.border,
                  border: "none",
                  borderRadius: 6,
                  color: closeComputed ? "#fff" : C.muted,
                  fontSize: 14,
                  fontWeight: 800,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                  cursor: closeComputed ? "pointer" : "not-allowed",
                  fontFamily: "system-ui, sans-serif",
                }}
              >
                Close Trade
              </button>

              {closeFeedback === "success" && (
                <div
                  style={{
                    marginTop: 10,
                    padding: "10px 14px",
                    background: C.green + "22",
                    border: `1px solid ${C.green}44`,
                    borderRadius: 5,
                    color: C.green,
                    fontSize: 13,
                    fontFamily: "system-ui, sans-serif",
                    textAlign: "center",
                  }}
                >
                  Trade closed successfully
                </div>
              )}
              {closeFeedback === "error" && (
                <div
                  style={{
                    marginTop: 10,
                    padding: "10px 14px",
                    background: C.red + "22",
                    border: `1px solid ${C.red}44`,
                    borderRadius: 5,
                    color: C.red,
                    fontSize: 13,
                    fontFamily: "system-ui, sans-serif",
                    textAlign: "center",
                  }}
                >
                  Failed to close trade
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
