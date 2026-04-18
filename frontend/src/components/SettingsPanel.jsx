import { useState, useEffect } from "react";
import { api } from "../api";

const MODES = [
  { value: "analysis_only", label: "Analysis Only" },
  { value: "paper_trading", label: "Paper Trading" },
  { value: "live_disabled", label: "Live (Disabled)" },
];

export default function SettingsPanel() {
  const [settings, setSettings] = useState(null);
  const [health, setHealth] = useState(null);
  const [saving, setSaving] = useState(false);
  const [form, setForm] = useState({});

  useEffect(() => {
    api.getSettings().then((s) => {
      setSettings(s);
      setForm({
        equity: String(s.equity || 50000),
        risk_pct: String(s.risk_pct || 1),
        max_positions: String(s.max_positions || 2),
        max_daily_loss_pct: String(s.max_daily_loss_pct || 3),
        max_drawdown_pct: String(s.max_drawdown_pct || 5),
        max_trades_per_day: String(s.max_trades_per_day || 5),
        friday_cutoff_hour: String(s.friday_cutoff_hour || 18),
        cooloff_after_losses: String(s.cooloff_after_losses || 3),
        max_spread: String(s.max_spread || 0.6),
        min_risk_reward: String(s.min_risk_reward || 1.5),
        min_confidence: String(s.min_confidence || 50),
        safe_mode: !!s.safe_mode,
        system_mode: s.system_mode || "paper_trading",
      });
    }).catch(() => {});
    api.health().then(setHealth).catch(() => {});
  }, []);

  async function handleSave() {
    setSaving(true);
    try {
      const updated = await api.updateSettings({
        equity: parseFloat(form.equity) || 50000,
        risk_pct: parseFloat(form.risk_pct) || 1,
        max_positions: parseInt(form.max_positions) || 2,
        max_daily_loss_pct: parseFloat(form.max_daily_loss_pct) || 3,
        max_drawdown_pct: parseFloat(form.max_drawdown_pct) || 5,
        max_trades_per_day: parseInt(form.max_trades_per_day) || 5,
        friday_cutoff_hour: parseInt(form.friday_cutoff_hour) || 18,
        cooloff_after_losses: parseInt(form.cooloff_after_losses) || 3,
        max_spread: parseFloat(form.max_spread) || 0.6,
        min_risk_reward: parseFloat(form.min_risk_reward) || 1.5,
        min_confidence: parseInt(form.min_confidence) || 50,
        safe_mode: form.safe_mode,
        system_mode: form.system_mode,
      });
      setSettings(updated);
    } catch (e) {
      alert("Failed: " + e.message);
    } finally {
      setSaving(false);
    }
  }

  function field(label, key, type = "number", props = {}) {
    return (
      <div className="field">
        <label className="field-label">{label}</label>
        <input className="field-input" type={type} value={form[key] || ""} onChange={(e) => setForm({ ...form, [key]: e.target.value })} {...props} />
      </div>
    );
  }

  return (
    <div>
      {/* System Status */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">System Status</div>
            <div className="card-subtitle">Gold Intelligence System v4.0</div>
          </div>
        </div>

        <div className="metrics-grid">
          <div className="metric-card">
            <div className="metric-label">Backend</div>
            <div className="metric-value" style={{ fontSize: 14, color: health ? "var(--green)" : "var(--red)" }}>
              {health ? "Connected" : "Offline"}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Claude API</div>
            <div className="metric-value" style={{ fontSize: 14, color: health?.has_api_key ? "var(--green)" : "var(--amber)" }}>
              {health?.has_api_key ? "Configured" : "Demo Mode"}
            </div>
            {!health?.has_api_key && <div className="metric-sub">Set ANTHROPIC_API_KEY env var</div>}
          </div>
          <div className="metric-card">
            <div className="metric-label">Mode</div>
            <div className="metric-value" style={{ fontSize: 14 }}>
              {(health?.system_mode || "paper_trading").replace(/_/g, " ").toUpperCase()}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Live Trading</div>
            <div className="metric-value" style={{ fontSize: 14, color: health?.live_enabled ? "var(--red)" : "var(--green)" }}>
              {health?.live_enabled ? "ENABLED" : "Disabled (safe)"}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Strategies</div>
            <div className="metric-value" style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
              {health?.strategies?.join(", ") || "—"}
            </div>
          </div>
          <div className="metric-card">
            <div className="metric-label">Version</div>
            <div className="metric-value" style={{ fontSize: 14 }}>{health?.version || "—"}</div>
          </div>
        </div>
      </div>

      {/* System Mode */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">System Mode</div>
            <div className="card-subtitle">Controls whether the system can execute trades</div>
          </div>
        </div>
        <div className="form-grid">
          <div className="field">
            <label className="field-label">Mode</label>
            <select className="field-input" value={form.system_mode || "paper_trading"} onChange={(e) => setForm({ ...form, system_mode: e.target.value })}>
              {MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          <div className="field">
            <label className="field-label">Safe Mode (Kill Switch)</label>
            <select className="field-input" value={form.safe_mode ? "on" : "off"} onChange={(e) => setForm({ ...form, safe_mode: e.target.value === "on" })}>
              <option value="off">Off — normal operation</option>
              <option value="on">ON — all trading blocked</option>
            </select>
          </div>
        </div>
      </div>

      {/* Account Settings */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Account & Position Sizing</div>
            <div className="card-subtitle">Core risk parameters</div>
          </div>
          <button className="btn btn-primary btn-sm" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save All"}
          </button>
        </div>
        <div className="form-grid">
          {field("Account Equity (USD)", "equity")}
          {field("Risk Per Trade (%)", "risk_pct", "number", { step: "0.1", min: "0.1", max: "5" })}
          {field("Max Open Positions", "max_positions", "number", { min: "1", max: "10" })}
        </div>
      </div>

      {/* Risk Management */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Risk Management Rules</div>
            <div className="card-subtitle">Hard gates that block trading when violated</div>
          </div>
        </div>
        <div className="form-grid">
          {field("Max Daily Loss (%)", "max_daily_loss_pct", "number", { step: "0.5", min: "0.5", max: "20" })}
          {field("Max Account Drawdown (%)", "max_drawdown_pct", "number", { step: "1", min: "1", max: "50" })}
          {field("Max Trades Per Day", "max_trades_per_day", "number", { min: "1", max: "50" })}
          {field("Friday Cutoff Hour (UTC)", "friday_cutoff_hour", "number", { min: "12", max: "23" })}
          {field("Cooloff After N Losses", "cooloff_after_losses", "number", { min: "0", max: "10" })}
          {field("Max Spread ($)", "max_spread", "number", { step: "0.05", min: "0.1", max: "2" })}
          {field("Min Risk:Reward", "min_risk_reward", "number", { step: "0.1", min: "1", max: "5" })}
          {field("Min Confidence (0-100)", "min_confidence", "number", { min: "0", max: "100" })}
        </div>
      </div>

      {/* Setup Instructions */}
      <div className="card">
        <div className="card-header">
          <div className="card-title">Setup Guide</div>
        </div>
        <div style={{ fontSize: 13, color: "var(--text-secondary)", lineHeight: 1.8 }}>
          <p style={{ marginBottom: 12 }}>
            <strong style={{ color: "var(--text)" }}>1. Backend</strong> — Python 3.10+, no pip dependencies for core. Start with:
          </p>
          <code style={{ display: "block", padding: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 12, marginBottom: 16 }}>
            cd backend && python3 server.py
          </code>

          <p style={{ marginBottom: 12 }}>
            <strong style={{ color: "var(--text)" }}>2. AI Analysis</strong> — For Claude-powered analysis:
          </p>
          <code style={{ display: "block", padding: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 12, marginBottom: 16 }}>
            export ANTHROPIC_API_KEY=sk-ant-... && python3 backend/server.py
          </code>

          <p style={{ marginBottom: 12 }}>
            <strong style={{ color: "var(--text)" }}>3. Frontend</strong> — Install and run:
          </p>
          <code style={{ display: "block", padding: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", fontFamily: "var(--font-mono)", fontSize: 12, marginBottom: 16 }}>
            cd frontend && npm install && npm run dev
          </code>

          <p style={{ color: "var(--red)", fontWeight: 600, marginTop: 16 }}>
            Live trading is disabled by default and requires explicit configuration.
            Paper trading is the default mode. No real money is at risk.
          </p>
        </div>
      </div>
    </div>
  );
}
