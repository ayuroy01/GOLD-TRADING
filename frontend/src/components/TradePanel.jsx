import { useState, useEffect } from "react";
import { api } from "../api";

const DIRECTIONS = ["long", "short"];
const ZONES = ["EMA", "S/R Flip", "50% Fib"];
const TRIGGERS_LONG = ["Bullish Engulfing", "Hammer"];
const TRIGGERS_SHORT = ["Bearish Engulfing", "Shooting Star"];
const ERRORS = ["None", "Process", "Analytical", "Timing", "Behavioral"];

function computeLocal(entry, stop, t1, t2, equity, riskPct) {
  const risk = Math.abs(entry - stop);
  if (risk <= 0) return null;
  const direction = entry > stop ? "long" : "short";
  const riskUsd = equity * (riskPct / 100);
  const oz = riskUsd / risk;
  const lots = oz / 100;
  const rrT1 = t1 ? Math.abs(t1 - entry) / risk : null;
  const rrT2 = t2 ? Math.abs(t2 - entry) / risk : null;

  return {
    direction,
    risk: Math.round(risk * 100) / 100,
    riskUsd: Math.round(riskUsd * 100) / 100,
    oz: Math.round(oz * 100) / 100,
    lots: Math.round(lots * 1000) / 1000,
    rrT1: rrT1 ? Math.round(rrT1 * 100) / 100 : null,
    rrT2: rrT2 ? Math.round(rrT2 * 100) / 100 : null,
    rrValid: rrT1 !== null && rrT1 >= 1.5,
  };
}

export default function TradePanel({ trades = [], onUpdate }) {
  const [settings, setSettings] = useState({ equity: 50000, risk_pct: 1 });
  const [form, setForm] = useState({
    entry: "",
    stop: "",
    t1: "",
    t2: "",
    zone: "EMA",
    trigger: "Bullish Engulfing",
    notes: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api.getSettings().then(setSettings).catch(() => {});
  }, []);

  const entry = parseFloat(form.entry) || 0;
  const stop = parseFloat(form.stop) || 0;
  const t1 = parseFloat(form.t1) || 0;
  const t2 = parseFloat(form.t2) || 0;
  const calc = entry && stop ? computeLocal(entry, stop, t1, t2, settings.equity, settings.risk_pct) : null;

  const direction = calc?.direction || (entry > stop ? "long" : "short");
  const triggers = direction === "long" ? TRIGGERS_LONG : TRIGGERS_SHORT;

  // Validation
  const maxPos = settings.max_positions || 2;
  const issues = [];
  if (calc && !calc.rrValid && calc.rrT1 !== null) {
    issues.push(`R:R to T1 is ${calc.rrT1}:1 — minimum 1.5:1`);
  }
  const openTrades = trades.filter((t) => t.status === "open");
  if (openTrades.length >= maxPos) {
    issues.push(`Already ${openTrades.length} open positions (max ${maxPos})`);
  }

  async function handleSubmit() {
    if (!calc || issues.length > 0) return;
    setSaving(true);
    try {
      await api.logTrade({
        date: new Date().toISOString(),
        direction: calc.direction,
        entry,
        stop,
        t1: t1 || null,
        t2: t2 || null,
        zone: form.zone,
        trigger: form.trigger,
        risk_distance: calc.risk,
        rr_to_t1: calc.rrT1,
        position_oz: calc.oz,
        position_lots: calc.lots,
        risk_usd: calc.riskUsd,
        status: "open",
        exit_price: null,
        r_multiple: null,
        error_type: "None",
        notes: form.notes,
      });
      setForm({ entry: "", stop: "", t1: "", t2: "", zone: "EMA", trigger: triggers[0], notes: "" });
      onUpdate?.();
    } catch (e) {
      alert("Failed to log trade: " + e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Trade Planning</div>
            <div className="card-subtitle">Validate and log trade plans (manual journal entry)</div>
          </div>
        </div>

        <div className="form-grid" style={{ marginBottom: 16 }}>
          <div className="field">
            <label className="field-label">Entry Price</label>
            <input
              className="field-input"
              type="number"
              step="0.01"
              placeholder="3245.50"
              value={form.entry}
              onChange={(e) => setForm({ ...form, entry: e.target.value })}
            />
          </div>
          <div className="field">
            <label className="field-label">Stop Loss</label>
            <input
              className="field-input"
              type="number"
              step="0.01"
              placeholder="3228.00"
              value={form.stop}
              onChange={(e) => setForm({ ...form, stop: e.target.value })}
            />
          </div>
          <div className="field">
            <label className="field-label">Target 1</label>
            <input
              className="field-input"
              type="number"
              step="0.01"
              placeholder="3270.00"
              value={form.t1}
              onChange={(e) => setForm({ ...form, t1: e.target.value })}
            />
          </div>
          <div className="field">
            <label className="field-label">Target 2</label>
            <input
              className="field-input"
              type="number"
              step="0.01"
              placeholder="3300.00"
              value={form.t2}
              onChange={(e) => setForm({ ...form, t2: e.target.value })}
            />
          </div>
          <div className="field">
            <label className="field-label">Pullback Zone</label>
            <select
              className="field-input"
              value={form.zone}
              onChange={(e) => setForm({ ...form, zone: e.target.value })}
            >
              {ZONES.map((z) => (
                <option key={z} value={z}>{z}</option>
              ))}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Entry Trigger</label>
            <select
              className="field-input"
              value={form.trigger}
              onChange={(e) => setForm({ ...form, trigger: e.target.value })}
            >
              {triggers.map((t) => (
                <option key={t} value={t}>{t}</option>
              ))}
            </select>
          </div>
        </div>

        <div className="field" style={{ marginBottom: 16 }}>
          <label className="field-label">Notes</label>
          <input
            className="field-input"
            type="text"
            placeholder="Trade rationale, observations..."
            value={form.notes}
            onChange={(e) => setForm({ ...form, notes: e.target.value })}
          />
        </div>

        {/* Computed values */}
        {calc && (
          <div
            className="metrics-grid"
            style={{ marginBottom: 16 }}
          >
            <div className="metric-card">
              <div className="metric-label">Direction</div>
              <div className={`metric-value ${calc.direction === "long" ? "positive" : "negative"}`}>
                {calc.direction.toUpperCase()}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Risk Distance</div>
              <div className="metric-value">${calc.risk}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Risk USD</div>
              <div className="metric-value">${calc.riskUsd}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Position</div>
              <div className="metric-value">{calc.lots} lots</div>
              <div className="metric-sub">{calc.oz} oz</div>
            </div>
            {calc.rrT1 != null && (
              <div className="metric-card">
                <div className="metric-label">R:R to T1</div>
                <div className={`metric-value ${calc.rrValid ? "positive" : "negative"}`}>
                  {calc.rrT1}:1
                </div>
                {!calc.rrValid && (
                  <div className="metric-sub" style={{ color: "var(--red)" }}>Below 1.5 min</div>
                )}
              </div>
            )}
            {calc.rrT2 != null && (
              <div className="metric-card">
                <div className="metric-label">R:R to T2</div>
                <div className="metric-value blue">{calc.rrT2}:1</div>
              </div>
            )}
          </div>
        )}

        {/* Validation issues */}
        {issues.length > 0 && (
          <div style={{ padding: 12, background: "var(--red-dim)", borderRadius: "var(--radius-sm)", marginBottom: 16 }}>
            {issues.map((i, idx) => (
              <div key={idx} style={{ color: "var(--red)", fontSize: 13, marginBottom: idx < issues.length - 1 ? 4 : 0 }}>
                ⛔ {i}
              </div>
            ))}
          </div>
        )}

        <div className="btn-group">
          <button
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={!calc || issues.length > 0 || saving}
          >
            {saving ? "Logging..." : "Log Trade"}
          </button>
        </div>
      </div>

      {/* Open Trades */}
      {openTrades.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Open Positions ({openTrades.length})</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Date</th>
                  <th>Direction</th>
                  <th>Entry</th>
                  <th>Stop</th>
                  <th>T1</th>
                  <th>R:R</th>
                  <th>Lots</th>
                </tr>
              </thead>
              <tbody>
                {openTrades.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.date).toLocaleDateString()}</td>
                    <td>
                      <span className={`badge ${t.direction === "long" ? "badge-green" : "badge-red"}`}>
                        {t.direction?.toUpperCase()}
                      </span>
                    </td>
                    <td>${t.entry}</td>
                    <td>${t.stop}</td>
                    <td>{t.t1 ? `$${t.t1}` : "—"}</td>
                    <td>{t.rr_to_t1 ? `${t.rr_to_t1}:1` : "—"}</td>
                    <td>{t.position_lots}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
