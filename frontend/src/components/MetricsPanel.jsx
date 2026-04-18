import { useState, useEffect, useMemo } from "react";
import { api } from "../api";
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Cell,
} from "recharts";

function fmt(n, d = 2) {
  return typeof n === "number" && !isNaN(n) ? n.toFixed(d) : "—";
}
function fmtPct(n) {
  return typeof n === "number" ? (n * 100).toFixed(1) + "%" : "—";
}

const GOLD = "#d4a843";
const GREEN = "#2dd4a0";
const RED = "#f06060";
const BORDER = "#1e2131";
const MUTED = "#555972";

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="metric-card">
      <div className="metric-label">{label}</div>
      <div className="metric-value" style={color ? { color } : undefined}>{value}</div>
      {sub && <div className="metric-sub">{sub}</div>}
    </div>
  );
}

export default function MetricsPanel({ trades = [] }) {
  const [metrics, setMetrics] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api.getMetrics().then(setMetrics).catch(() => setMetrics(null)).finally(() => setLoading(false));
  }, [trades]);

  const equityData = useMemo(() => {
    if (!metrics?.equity_curve) return [];
    return metrics.equity_curve.map((val, i) => ({ trade: i, cumR: val }));
  }, [metrics]);

  const distributionData = useMemo(() => {
    if (!metrics?.r_multiples) return [];
    const buckets = [
      { label: "< -2R", min: -Infinity, max: -2 },
      { label: "-2 to -1", min: -2, max: -1 },
      { label: "-1 to 0", min: -1, max: 0 },
      { label: "0 to 1", min: 0, max: 1 },
      { label: "1 to 2", min: 1, max: 2 },
      { label: "2 to 3", min: 2, max: 3 },
      { label: "> 3R", min: 3, max: Infinity },
    ];
    return buckets.map((b) => ({
      bucket: b.label,
      count: metrics.r_multiples.filter((r) => r >= b.min && r < b.max).length,
      pos: b.min >= 0,
    }));
  }, [metrics]);

  const rSeq = useMemo(() => {
    if (!metrics?.r_multiples) return [];
    return metrics.r_multiples.map((r, i) => ({ trade: i + 1, r }));
  }, [metrics]);

  if (loading) {
    return (<div className="card"><div style={{ padding: 40, textAlign: "center" }}><span className="spinner" /><p style={{ marginTop: 12, color: "var(--text-muted)", fontSize: 13 }}>Loading metrics...</p></div></div>);
  }

  if (!metrics || !metrics.closed_trades) {
    return (<div className="card"><div className="empty-state"><div className="empty-icon">◈</div><div className="empty-title">No analytics yet</div><div className="empty-desc">Close trades with R-multiples in the Journal to see performance analytics and equity curves.</div></div></div>);
  }

  const evColor = metrics.expectancy > 0 ? GREEN : metrics.expectancy < 0 ? RED : undefined;
  const wrColor = metrics.win_rate >= 0.5 ? GREEN : metrics.win_rate >= 0.4 ? GOLD : RED;
  const pfVal = metrics.profit_factor === "Infinity" ? Infinity : parseFloat(metrics.profit_factor);

  return (
    <div>
      <div className="card" style={{ marginBottom: 16, borderColor: metrics.edge_status?.includes("VALIDATED") ? GREEN : metrics.edge_status?.includes("NOT") ? RED : GOLD, borderLeftWidth: 3 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--text-muted)", marginBottom: 4 }}>Edge Status</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{metrics.edge_status}</div>
          </div>
          <div style={{ textAlign: "right" }}>
            <span className="badge badge-gold">Phase {metrics.phase}</span>
            <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>
              {metrics.phase === 1 ? "0–50 trades" : metrics.phase === 2 ? "50–150 trades" : "150+ trades"}
            </div>
          </div>
        </div>
      </div>

      <div className="metrics-grid">
        <MetricCard label="Total Trades" value={metrics.total_trades} sub={`${metrics.open_trades} open`} />
        <MetricCard label="Win Rate" value={fmtPct(metrics.win_rate)} color={wrColor} sub={`CI: ${fmtPct(metrics.ci_low)} – ${fmtPct(metrics.ci_high)}`} />
        <MetricCard label="Expectancy" value={`${fmt(metrics.expectancy, 3)}R`} color={evColor} sub={`CI low: ${fmt(metrics.ev_at_ci_low, 3)}R`} />
        <MetricCard label="Profit Factor" value={pfVal === Infinity ? "∞" : fmt(pfVal)} color={pfVal > 1 ? GREEN : RED} />
        <MetricCard label="Avg Win" value={`+${fmt(metrics.avg_win_r)}R`} color={GREEN} />
        <MetricCard label="Avg Loss" value={`-${fmt(metrics.avg_loss_r)}R`} color={RED} />
        <MetricCard label="Sharpe" value={fmt(metrics.sharpe)} color={metrics.sharpe > 0.5 ? GREEN : undefined} />
        <MetricCard label="Max Drawdown" value={`${fmt(metrics.max_drawdown_r)}R`} color={RED} />
        <MetricCard label="Max Lose Streak" value={metrics.max_losing_streak} color={metrics.max_losing_streak >= 5 ? RED : undefined} />
        <MetricCard label="Std Dev" value={`${fmt(metrics.std_dev, 3)}R`} />
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header"><div className="card-title">Equity Curve (Cumulative R)</div></div>
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={equityData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
              <XAxis dataKey="trade" tick={{ fill: MUTED, fontSize: 10 }} />
              <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
              <ReferenceLine y={0} stroke={MUTED} strokeDasharray="4 4" />
              <Tooltip contentStyle={{ background: "#13151d", border: `1px solid ${BORDER}`, borderRadius: 6, fontSize: 12 }} labelFormatter={(v) => `Trade ${v}`} formatter={(v) => [`${v}R`, "Cumulative"]} />
              <Line type="monotone" dataKey="cumR" stroke={GOLD} strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginTop: 16 }}>
        <div className="card">
          <div className="card-header"><div className="card-title">R-Multiple Distribution</div></div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={distributionData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="bucket" tick={{ fill: MUTED, fontSize: 9 }} />
                <YAxis tick={{ fill: MUTED, fontSize: 10 }} allowDecimals={false} />
                <Tooltip contentStyle={{ background: "#13151d", border: `1px solid ${BORDER}`, borderRadius: 6, fontSize: 12 }} />
                <Bar dataKey="count" radius={[3, 3, 0, 0]}>
                  {distributionData.map((d, i) => (<Cell key={i} fill={d.pos ? GREEN : RED} opacity={0.8} />))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <div className="card-header"><div className="card-title">R-Multiple Sequence</div></div>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={rSeq} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={BORDER} />
                <XAxis dataKey="trade" tick={{ fill: MUTED, fontSize: 10 }} />
                <YAxis tick={{ fill: MUTED, fontSize: 10 }} />
                <ReferenceLine y={0} stroke={MUTED} />
                <Tooltip contentStyle={{ background: "#13151d", border: `1px solid ${BORDER}`, borderRadius: 6, fontSize: 12 }} formatter={(v) => [`${v}R`, "Result"]} />
                <Bar dataKey="r" radius={[3, 3, 0, 0]}>
                  {rSeq.map((d, i) => (<Cell key={i} fill={d.r >= 0 ? GREEN : RED} opacity={0.8} />))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: 16 }}>
        <div className="card-header"><div className="card-title">Win / Loss</div></div>
        <div style={{ display: "flex", gap: 0, height: 32, borderRadius: "var(--radius-sm)", overflow: "hidden" }}>
          <div style={{ width: `${metrics.win_rate * 100}%`, background: GREEN, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#08090d", minWidth: metrics.wins > 0 ? 40 : 0 }}>{metrics.wins}W</div>
          <div style={{ width: `${(1 - metrics.win_rate) * 100}%`, background: RED, display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, color: "#08090d", minWidth: metrics.losses > 0 ? 40 : 0 }}>{metrics.losses}L</div>
        </div>
      </div>
    </div>
  );
}
