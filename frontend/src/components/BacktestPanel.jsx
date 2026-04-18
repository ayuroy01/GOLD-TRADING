import { useState } from "react";
import { api } from "../api";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine,
} from "recharts";

const GOLD = "#d4a843";
const GREEN = "#2dd4a0";
const RED = "#f06060";
const BLUE = "#5b8ef5";
const BORDER = "#1e2131";
const MUTED = "#555972";

function MetricRow({ label, value, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid var(--border)" }}>
      <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>{label}</span>
      <span style={{ fontSize: 12, fontFamily: "var(--font-mono)", fontWeight: 600, color: color || "var(--text)" }}>{value}</span>
    </div>
  );
}

export default function BacktestPanel() {
  const [result, setResult] = useState(null);
  const [wfResult, setWfResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [wfLoading, setWfLoading] = useState(false);
  const [candles, setCandles] = useState("500");
  const [spread, setSpread] = useState("0.40");
  const [folds, setFolds] = useState("3");

  async function runBacktest() {
    setLoading(true);
    try {
      const res = await api.runBacktest(parseInt(candles), parseFloat(spread));
      setResult(res);
    } catch (e) {
      alert("Backtest failed: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  async function runWalkForward() {
    setWfLoading(true);
    try {
      const res = await api.runWalkForward(parseInt(candles), parseInt(folds));
      setWfResult(res);
    } catch (e) {
      alert("Walk-forward failed: " + e.message);
    } finally {
      setWfLoading(false);
    }
  }

  const m = result?.backtest?.metrics;
  const baselines = result?.baselines || [];
  const equityData = m?.equity_curve?.map((v, i) => ({ trade: i, cumR: v })) || [];

  return (
    <div>
      {/* Controls */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Backtesting & Research</div>
            <div className="card-subtitle">Evaluate strategies against historical data (simulated)</div>
          </div>
        </div>

        <div className="form-grid" style={{ marginBottom: 16 }}>
          <div className="field">
            <label className="field-label">Candles (1h)</label>
            <input className="field-input" type="number" min="100" max="5000" value={candles} onChange={e => setCandles(e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Spread ($)</label>
            <input className="field-input" type="number" step="0.05" min="0.1" max="2" value={spread} onChange={e => setSpread(e.target.value)} />
          </div>
          <div className="field">
            <label className="field-label">Walk-Forward Folds</label>
            <input className="field-input" type="number" min="2" max="10" value={folds} onChange={e => setFolds(e.target.value)} />
          </div>
        </div>

        <div className="btn-group">
          <button className="btn btn-primary" onClick={runBacktest} disabled={loading}>
            {loading && <span className="spinner" />}
            {loading ? "Running..." : "Run Backtest"}
          </button>
          <button className="btn" onClick={runWalkForward} disabled={wfLoading}>
            {wfLoading && <span className="spinner" />}
            {wfLoading ? "Running..." : "Walk-Forward Test"}
          </button>
        </div>

        <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 12 }}>
          Data is simulated. Results do not represent real market performance. Past backtests do not guarantee future results.
        </div>
      </div>

      {/* Backtest Results */}
      {m && (
        <div>
          <div className="card" style={{ marginBottom: 16 }}>
            <div className="card-header">
              <div className="card-title">Backtest Results</div>
              <span className="badge badge-muted">{m.total_trades || m.closed_trades} trades</span>
            </div>

            <div className="metrics-grid" style={{ marginBottom: 16 }}>
              <div className="metric-card"><div className="metric-label">Win Rate</div><div className="metric-value" style={{ color: m.win_rate >= 0.5 ? GREEN : RED }}>{(m.win_rate * 100).toFixed(1)}%</div></div>
              <div className="metric-card"><div className="metric-label">Expectancy</div><div className="metric-value" style={{ color: m.expectancy > 0 ? GREEN : RED }}>{m.expectancy?.toFixed(4)}R</div></div>
              <div className="metric-card"><div className="metric-label">Profit Factor</div><div className="metric-value">{m.profit_factor === "Infinity" ? "n/a" : m.profit_factor}</div></div>
              <div className="metric-card"><div className="metric-label">Sharpe</div><div className="metric-value">{m.sharpe?.toFixed(2)}</div></div>
              <div className="metric-card"><div className="metric-label">Max DD</div><div className="metric-value negative">{m.max_drawdown_r?.toFixed(2)}R</div></div>
              <div className="metric-card"><div className="metric-label">Total R</div><div className="metric-value" style={{ color: m.total_r > 0 ? GREEN : RED }}>{m.total_r?.toFixed(2)}R</div></div>
            </div>

            {/* Equity curve */}
            {equityData.length > 1 && (
              <div className="chart-container">
                <ResponsiveContainer width="100%" height={220}>
                  <LineChart data={equityData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                    <XAxis dataKey="trade" tick={{ fill: MUTED, fontSize: 10 }} />
                    <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
                    <ReferenceLine y={0} stroke={MUTED} strokeDasharray="4 4" />
                    <Tooltip contentStyle={{ background: "#13151d", border: `1px solid ${BORDER}`, borderRadius: 6, fontSize: 12 }} />
                    <Line type="monotone" dataKey="cumR" stroke={GOLD} strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Strategy breakdown */}
            {m.by_strategy && Object.keys(m.by_strategy).length > 0 && (
              <div style={{ marginTop: 16 }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "var(--text-muted)", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.08em" }}>By Strategy</div>
                {Object.entries(m.by_strategy).map(([name, stats]) => (
                  <div key={name} style={{ display: "flex", justifyContent: "space-between", padding: "6px 0", borderBottom: "1px solid var(--border)" }}>
                    <span style={{ fontFamily: "var(--font-mono)", fontSize: 12, color: "var(--text)" }}>{name}</span>
                    <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                      {stats.trades} trades · WR {(stats.win_rate * 100).toFixed(0)}% · EV {stats.expectancy?.toFixed(3)}R · Total {stats.total_r}R
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Baselines comparison */}
          {baselines.length > 0 && (
            <div className="card" style={{ marginBottom: 16 }}>
              <div className="card-header">
                <div className="card-title">Baseline Comparisons</div>
              </div>
              {baselines.map((b, i) => (
                <div key={i} style={{ padding: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", marginBottom: i < baselines.length - 1 ? 8 : 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, color: "var(--text)" }}>{b.name}</div>
                  <div style={{ fontSize: 12, color: "var(--text-muted)", marginBottom: 6 }}>{b.description}</div>
                  <div style={{ display: "flex", gap: 20, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                    <span>Trades: {b.metrics?.closed_trades || 0}</span>
                    <span>WR: {b.metrics?.win_rate ? (b.metrics.win_rate * 100).toFixed(1) + "%" : "0%"}</span>
                    <span>EV: {b.metrics?.expectancy?.toFixed(4) || "0"}R</span>
                    <span style={{ color: (b.metrics?.total_r || 0) >= 0 ? GREEN : RED }}>Total: {b.metrics?.total_r?.toFixed(2) || "0"}R</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Walk-Forward Results */}
      {wfResult && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <div className="card-title">Walk-Forward Results</div>
            <span className="badge badge-blue">{wfResult.n_folds} folds</span>
          </div>

          {wfResult.folds?.map((fold, i) => (
            <div key={i} style={{ padding: 12, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", marginBottom: 8 }}>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 6, color: "var(--text)" }}>Fold {fold.fold}</div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
                <div>
                  <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 4 }}>Train (in-sample)</div>
                  <div style={{ fontSize: 12, fontFamily: "var(--font-mono)" }}>
                    {fold.train_trades} trades · EV {fold.train_metrics?.expectancy?.toFixed(4) || "0"}R
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: 10, textTransform: "uppercase", color: "var(--text-muted)", marginBottom: 4 }}>Test (out-of-sample)</div>
                  <div style={{ fontSize: 12, fontFamily: "var(--font-mono)", color: (fold.test_metrics?.expectancy || 0) > 0 ? GREEN : RED }}>
                    {fold.test_trades} trades · EV {fold.test_metrics?.expectancy?.toFixed(4) || "0"}R
                  </div>
                </div>
              </div>
            </div>
          ))}

          {wfResult.aggregate_oos_metrics && (
            <div style={{ padding: 12, background: "var(--surface)", borderRadius: "var(--radius-sm)", border: "1px solid var(--border)" }}>
              <div style={{ fontSize: 11, textTransform: "uppercase", color: "var(--gold)", fontWeight: 600, marginBottom: 6 }}>Aggregate OOS</div>
              <div style={{ display: "flex", gap: 20, fontSize: 12, fontFamily: "var(--font-mono)" }}>
                <span>Trades: {wfResult.aggregate_oos_metrics.closed_trades || 0}</span>
                <span>WR: {wfResult.aggregate_oos_metrics.win_rate ? (wfResult.aggregate_oos_metrics.win_rate * 100).toFixed(1) + "%" : "n/a"}</span>
                <span style={{ color: (wfResult.aggregate_oos_metrics.expectancy || 0) > 0 ? GREEN : RED }}>
                  EV: {wfResult.aggregate_oos_metrics.expectancy?.toFixed(4) || "0"}R
                </span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Empty state */}
      {!result && !wfResult && !loading && !wfLoading && (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <div className="empty-title">No research results yet</div>
            <div className="empty-desc">
              Run a backtest or walk-forward test to evaluate strategy performance against historical data.
              Results use simulated data and do not represent real market outcomes.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
