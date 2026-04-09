import { useState, useMemo } from "react";

const INITIAL_TRADES = [];

const STORAGE_KEY = "gold_v1_journal";

function loadTrades() {
  try {
    const raw = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
    return Array.isArray(raw) ? raw : [];
  } catch { return []; }
}

function saveTrades(t) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(t)); } catch {}
}

const fmt = (n, d = 2) => (typeof n === "number" ? n.toFixed(d) : "—");
const pct = (n) => (typeof n === "number" ? (n * 100).toFixed(1) + "%" : "—");

function calcStats(trades) {
  if (!trades.length) return null;
  const closed = trades.filter(t => t.rMultiple !== null && t.rMultiple !== undefined);
  if (!closed.length) return null;
  const wins = closed.filter(t => t.rMultiple > 0);
  const losses = closed.filter(t => t.rMultiple <= 0);
  const winRate = wins.length / closed.length;
  const avgWinR = wins.length ? wins.reduce((s, t) => s + t.rMultiple, 0) / wins.length : 0;
  const avgLossR = losses.length ? Math.abs(losses.reduce((s, t) => s + t.rMultiple, 0) / losses.length) : 0;
  const expectancy = (winRate * avgWinR) - ((1 - winRate) * avgLossR);
  const grossWin = wins.reduce((s, t) => s + t.rMultiple, 0);
  const grossLoss = Math.abs(losses.reduce((s, t) => s + t.rMultiple, 0));
  const profitFactor = grossLoss > 0 ? grossWin / grossLoss : grossWin > 0 ? Infinity : 0;
  const rs = closed.map(t => t.rMultiple);
  const mean = rs.reduce((a, b) => a + b, 0) / rs.length;
  const variance = rs.reduce((s, r) => s + (r - mean) ** 2, 0) / rs.length;
  const sd = Math.sqrt(variance);
  const sharpe = sd > 0 ? expectancy / sd : 0;
  
  let maxStreak = 0, streak = 0;
  for (const t of closed) {
    if (t.rMultiple <= 0) { streak++; maxStreak = Math.max(maxStreak, streak); }
    else streak = 0;
  }
  
  const winRateSE = Math.sqrt(winRate * (1 - winRate) / closed.length);
  const ciLow = Math.max(0, winRate - 1.96 * winRateSE);
  const ciHigh = Math.min(1, winRate + 1.96 * winRateSE);
  const evAtCiLow = (ciLow * avgWinR) - ((1 - ciLow) * avgLossR);
  
  const phase = closed.length < 50 ? 1 : closed.length < 150 ? 2 : 3;
  
  let edgeStatus = "Insufficient data";
  if (phase === 3) {
    if (expectancy > 0.20 && evAtCiLow > 0 && profitFactor > 1.3) edgeStatus = "EDGE VALIDATED";
    else if (expectancy > 0 && evAtCiLow > -0.3) edgeStatus = "Preliminary positive — continue";
    else edgeStatus = "EDGE NOT CONFIRMED — review system";
  } else if (phase === 2) {
    if (expectancy > 0 && evAtCiLow > -0.3) edgeStatus = "On track — continue";
    else edgeStatus = "Warning — monitor closely";
  }
  
  return { total: closed.length, wins: wins.length, losses: losses.length, winRate, avgWinR, avgLossR, expectancy, profitFactor, sd, sharpe, maxStreak, ciLow, ciHigh, evAtCiLow, phase, edgeStatus };
}

function MetricCard({ label, value, sub, warn }) {
  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 10, padding: "14px 16px", minWidth: 140 }}>
      <div style={{ fontSize: 11, color: "var(--muted)", letterSpacing: 0.5, textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 22, fontWeight: 600, color: warn ? "var(--red)" : "var(--fg)", fontFamily: "'DM Mono', monospace" }}>{value}</div>
      {sub && <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 2 }}>{sub}</div>}
    </div>
  );
}

function PhaseIndicator({ phase, total }) {
  const phases = [
    { n: 1, label: "Paper", range: "1–50", target: 50 },
    { n: 2, label: "Small live", range: "51–150", target: 150 },
    { n: 3, label: "Validation", range: "151–250", target: 250 },
  ];
  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      {phases.map((p, i) => {
        const active = phase === p.n;
        const complete = total >= p.target;
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 4 }}>
            <div style={{
              padding: "4px 10px", borderRadius: 6, fontSize: 11, fontWeight: 500,
              background: complete ? "var(--green-bg)" : active ? "var(--accent-bg)" : "var(--card)",
              color: complete ? "var(--green)" : active ? "var(--accent)" : "var(--muted)",
              border: `1px solid ${complete ? "var(--green)" : active ? "var(--accent)" : "var(--border)"}`,
            }}>
              {p.label} ({p.range})
            </div>
            {i < 2 && <span style={{ color: "var(--border)" }}>→</span>}
          </div>
        );
      })}
    </div>
  );
}

function TradeForm({ onAdd }) {
  const [f, setF] = useState({
    date: new Date().toISOString().slice(0, 16),
    session: "London",
    trend: "Up",
    zone: "EMA",
    trigger: "Bullish Engulfing",
    entry: "", stop: "", t1: "", t2: "",
    exitPrice: "", exitReason: "T1 hit",
    rMultiple: "",
    mae: "", mfe: "",
    error: "None",
    notes: "",
    status: "open"
  });

  const set = (k, v) => setF(p => ({ ...p, [k]: v }));

  const rr = useMemo(() => {
    const e = parseFloat(f.entry), s = parseFloat(f.stop), t = parseFloat(f.t1);
    if (!e || !s || !t) return null;
    const risk = Math.abs(e - s);
    return risk > 0 ? ((t - e) / risk).toFixed(2) : null;
  }, [f.entry, f.stop, f.t1]);

  const submit = () => {
    const entry = parseFloat(f.entry), stop = parseFloat(f.stop);
    if (!entry || !stop) return;
    const rM = f.status === "closed" && f.rMultiple !== "" ? parseFloat(f.rMultiple) : null;
    onAdd({
      id: Date.now(),
      date: f.date,
      session: f.session,
      trend: f.trend,
      zone: f.zone,
      trigger: f.trigger,
      entry, stop,
      t1: parseFloat(f.t1) || null,
      t2: parseFloat(f.t2) || null,
      riskDist: Math.abs(entry - stop),
      rrToT1: rr ? parseFloat(rr) : null,
      exitPrice: f.status === "closed" ? parseFloat(f.exitPrice) || null : null,
      exitReason: f.status === "closed" ? f.exitReason : null,
      rMultiple: rM,
      mae: parseFloat(f.mae) || null,
      mfe: parseFloat(f.mfe) || null,
      error: f.error,
      notes: f.notes,
      status: f.status
    });
    setF(p => ({ ...p, entry: "", stop: "", t1: "", t2: "", exitPrice: "", rMultiple: "", mae: "", mfe: "", notes: "" }));
  };

  const sel = (label, key, opts) => (
    <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 12 }}>
      <span style={{ color: "var(--muted)", fontSize: 11 }}>{label}</span>
      <select value={f[key]} onChange={e => set(key, e.target.value)} style={inputStyle}>
        {opts.map(o => <option key={o} value={o}>{o}</option>)}
      </select>
    </label>
  );

  const inp = (label, key, placeholder) => (
    <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 12 }}>
      <span style={{ color: "var(--muted)", fontSize: 11 }}>{label}</span>
      <input value={f[key]} onChange={e => set(key, e.target.value)} placeholder={placeholder} style={inputStyle} />
    </label>
  );

  const inputStyle = {
    padding: "7px 10px", borderRadius: 6, border: "1px solid var(--border)",
    background: "var(--card)", color: "var(--fg)", fontSize: 13, fontFamily: "'DM Mono', monospace",
    outline: "none", width: "100%", boxSizing: "border-box"
  };

  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
      <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 14, color: "var(--fg)" }}>Log trade</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 10, marginBottom: 12 }}>
        {inp("Date (UTC)", "date", "")}
        {sel("Session", "session", ["London", "New York", "Overlap"])}
        {sel("H4 Trend", "trend", ["Up", "Down"])}
        {sel("Pullback zone", "zone", ["EMA", "S/R Flip", "50% Fib"])}
        {sel("Trigger", "trigger", ["Bullish Engulfing", "Hammer", "Bearish Engulfing", "Shooting Star"])}
        {inp("Entry $", "entry", "2320")}
        {inp("Stop $", "stop", "2303")}
        {inp("Target 1 $", "t1", "2340")}
        {inp("Target 2 $", "t2", "2365")}
      </div>

      {rr && (
        <div style={{ fontSize: 12, color: parseFloat(rr) >= 1.5 ? "var(--green)" : "var(--red)", marginBottom: 10, fontFamily: "'DM Mono', monospace" }}>
          R:R to T1: {rr} {parseFloat(rr) < 1.5 ? " — BELOW MINIMUM (1.5:1). Do not enter." : " — OK"}
        </div>
      )}

      {sel("Status", "status", ["open", "closed"])}

      {f.status === "closed" && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(130px, 1fr))", gap: 10, marginTop: 10 }}>
          {inp("Exit $", "exitPrice", "2338")}
          {sel("Exit reason", "exitReason", ["T1 hit", "T2 hit", "Stop hit", "Trailing stop", "Time stop", "Manual"])}
          {inp("R-Multiple", "rMultiple", "2.1")}
          {inp("MAE $", "mae", "5")}
          {inp("MFE $", "mfe", "22")}
          {sel("Error type", "error", ["None", "Process", "Analytical", "Timing", "Behavioral"])}
        </div>
      )}

      <div style={{ marginTop: 10 }}>
        <label style={{ display: "flex", flexDirection: "column", gap: 3, fontSize: 12 }}>
          <span style={{ color: "var(--muted)", fontSize: 11 }}>Notes</span>
          <textarea value={f.notes} onChange={e => set("notes", e.target.value)} rows={2} style={{ ...inputStyle, resize: "vertical" }} />
        </label>
      </div>

      <button onClick={submit} style={{
        marginTop: 14, padding: "9px 20px", borderRadius: 8, border: "none",
        background: "var(--accent)", color: "#fff", fontSize: 13, fontWeight: 600,
        cursor: "pointer"
      }}>
        Add trade
      </button>
    </div>
  );
}

function TradeTable({ trades, onDelete }) {
  if (!trades.length) return <div style={{ color: "var(--muted)", fontSize: 13, padding: 20 }}>No trades logged yet. Use the form above to add your first trade.</div>;
  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: "'DM Mono', monospace" }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--border)" }}>
            {["#", "Date", "Dir", "Zone", "Entry", "Stop", "T1", "R:R", "Exit", "R-Mult", "Error", ""].map(h => (
              <th key={h} style={{ padding: "8px 6px", textAlign: "left", color: "var(--muted)", fontSize: 10, textTransform: "uppercase", letterSpacing: 0.5 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={t.id} style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={cellStyle}>{i + 1}</td>
              <td style={cellStyle}>{t.date?.slice(5, 16)}</td>
              <td style={{ ...cellStyle, color: t.trend === "Up" ? "var(--green)" : "var(--red)" }}>{t.trend === "Up" ? "LONG" : "SHORT"}</td>
              <td style={cellStyle}>{t.zone}</td>
              <td style={cellStyle}>{fmt(t.entry, 0)}</td>
              <td style={cellStyle}>{fmt(t.stop, 0)}</td>
              <td style={cellStyle}>{fmt(t.t1, 0)}</td>
              <td style={cellStyle}>{fmt(t.rrToT1, 1)}</td>
              <td style={cellStyle}>{t.status === "closed" ? fmt(t.exitPrice, 0) : "—"}</td>
              <td style={{ ...cellStyle, color: t.rMultiple > 0 ? "var(--green)" : t.rMultiple < 0 ? "var(--red)" : "var(--muted)", fontWeight: 600 }}>
                {t.rMultiple !== null ? (t.rMultiple > 0 ? "+" : "") + fmt(t.rMultiple, 2) + "R" : "—"}
              </td>
              <td style={{ ...cellStyle, color: t.error !== "None" ? "var(--red)" : "var(--muted)" }}>{t.error === "None" ? "—" : t.error}</td>
              <td style={cellStyle}>
                <button onClick={() => onDelete(t.id)} style={{ background: "none", border: "none", color: "var(--muted)", cursor: "pointer", fontSize: 14 }}>×</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

const cellStyle = { padding: "8px 6px", verticalAlign: "middle" };

function EquityCurve({ trades }) {
  const closed = trades.filter(t => t.rMultiple !== null);
  if (closed.length < 3) return null;
  
  let cum = 0;
  const points = closed.map((t, i) => { cum += t.rMultiple; return { x: i, y: cum }; });
  const maxY = Math.max(...points.map(p => p.y), 1);
  const minY = Math.min(...points.map(p => p.y), -1);
  const range = maxY - minY || 1;
  const W = 600, H = 160, PAD = 30;
  
  const scaleX = (x) => PAD + (x / (points.length - 1)) * (W - 2 * PAD);
  const scaleY = (y) => H - PAD - ((y - minY) / range) * (H - 2 * PAD);
  
  const pathD = points.map((p, i) => `${i === 0 ? "M" : "L"}${scaleX(p.x).toFixed(1)},${scaleY(p.y).toFixed(1)}`).join(" ");
  const zeroY = scaleY(0);
  
  return (
    <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: "14px 16px" }}>
      <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Cumulative R-multiple equity curve</div>
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: "100%", height: "auto" }}>
        <line x1={PAD} y1={zeroY} x2={W - PAD} y2={zeroY} stroke="var(--border)" strokeWidth="1" strokeDasharray="4 3" />
        <text x={PAD - 4} y={zeroY + 3} fill="var(--muted)" fontSize="9" textAnchor="end" fontFamily="'DM Mono', monospace">0R</text>
        <text x={PAD - 4} y={scaleY(maxY) + 3} fill="var(--muted)" fontSize="9" textAnchor="end" fontFamily="'DM Mono', monospace">{fmt(maxY, 1)}R</text>
        <text x={PAD - 4} y={scaleY(minY) + 3} fill="var(--muted)" fontSize="9" textAnchor="end" fontFamily="'DM Mono', monospace">{fmt(minY, 1)}R</text>
        <path d={pathD} fill="none" stroke={cum >= 0 ? "var(--green)" : "var(--red)"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={i} cx={scaleX(p.x)} cy={scaleY(p.y)} r="3" fill={closed[i].rMultiple >= 0 ? "var(--green)" : "var(--red)"} />
        ))}
      </svg>
    </div>
  );
}

export default function App() {
  const [trades, setTrades] = useState(INITIAL_TRADES);
  const [tab, setTab] = useState("dashboard");
  const stats = useMemo(() => calcStats(trades), [trades]);

  const addTrade = (t) => setTrades(prev => [...prev, t]);
  const deleteTrade = (id) => setTrades(prev => prev.filter(t => t.id !== id));

  const total = stats?.total || 0;
  const phase = total < 50 ? 1 : total < 150 ? 2 : 3;

  return (
    <div style={{
      "--fg": "var(--color-text-primary)",
      "--muted": "var(--color-text-secondary)",
      "--card": "var(--color-background-secondary)",
      "--border": "var(--color-border-tertiary)",
      "--accent": "#1D6B54",
      "--accent-bg": "#E1F5EE",
      "--green": "#0F6E56",
      "--green-bg": "#E1F5EE",
      "--red": "#993C1D",
      "--red-bg": "#FAECE7",
      fontFamily: "'DM Sans', system-ui, sans-serif",
      color: "var(--fg)",
      maxWidth: 900,
    }}>
      <link href="https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />

      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 18, fontWeight: 700, margin: 0, letterSpacing: -0.3 }}>Gold V1 — trade journal + validation</h2>
        <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 4 }}>H4 pullback in trend — {total} trades logged</div>
        <div style={{ marginTop: 10 }}><PhaseIndicator phase={phase} total={total} /></div>
      </div>

      <div style={{ display: "flex", gap: 6, marginBottom: 16, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
        {["dashboard", "log trade", "trade list"].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: "6px 14px", borderRadius: 6, border: "none", fontSize: 12, fontWeight: 500,
            background: tab === t ? "var(--accent)" : "transparent",
            color: tab === t ? "#fff" : "var(--muted)",
            cursor: "pointer", textTransform: "capitalize"
          }}>{t}</button>
        ))}
      </div>

      {tab === "dashboard" && (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {stats ? (
            <>
              <div style={{
                padding: "12px 16px", borderRadius: 10,
                background: stats.edgeStatus.includes("VALIDATED") ? "var(--green-bg)" : stats.edgeStatus.includes("NOT CONFIRMED") ? "var(--red-bg)" : "var(--card)",
                border: `1px solid ${stats.edgeStatus.includes("VALIDATED") ? "var(--green)" : stats.edgeStatus.includes("NOT CONFIRMED") ? "var(--red)" : "var(--border)"}`,
                fontSize: 13, fontWeight: 600,
                color: stats.edgeStatus.includes("VALIDATED") ? "var(--green)" : stats.edgeStatus.includes("NOT CONFIRMED") ? "var(--red)" : "var(--fg)"
              }}>
                Phase {stats.phase}: {stats.edgeStatus}
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))", gap: 10 }}>
                <MetricCard label="Trades" value={stats.total} sub={`${stats.wins}W / ${stats.losses}L`} />
                <MetricCard label="Win rate" value={pct(stats.winRate)} sub={`95% CI: ${pct(stats.ciLow)} – ${pct(stats.ciHigh)}`} />
                <MetricCard label="Avg win" value={fmt(stats.avgWinR) + "R"} />
                <MetricCard label="Avg loss" value={fmt(stats.avgLossR) + "R"} warn={stats.avgLossR > 1.2} />
                <MetricCard label="Expectancy" value={fmt(stats.expectancy) + "R"} sub={`EV at CI low: ${fmt(stats.evAtCiLow)}R`} warn={stats.expectancy < 0} />
                <MetricCard label="Profit factor" value={fmt(stats.profitFactor)} warn={stats.profitFactor < 1} />
                <MetricCard label="Std dev" value={fmt(stats.sd) + "R"} />
                <MetricCard label="Sharpe-like" value={fmt(stats.sharpe)} />
                <MetricCard label="Max losing streak" value={stats.maxStreak} warn={stats.maxStreak >= 7} sub={`Expected max over 100: ~7`} />
              </div>

              <EquityCurve trades={trades} />

              <div style={{ background: "var(--card)", border: "1px solid var(--border)", borderRadius: 12, padding: "14px 16px" }}>
                <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 0.5, marginBottom: 8 }}>Validation checklist — phase {stats.phase}</div>
                {stats.phase === 1 && (
                  <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                    <Check ok={stats.total >= 50} label={`50 trades completed (${stats.total}/50)`} />
                    <Check ok={stats.avgLossR >= 0.8 && stats.avgLossR <= 1.2} label={`Avg loss between -0.8R and -1.2R (current: ${fmt(stats.avgLossR)}R)`} />
                    <Check ok={trades.filter(t => t.error !== "None").length === 0} label={`Zero behavioral errors (${trades.filter(t => t.error !== "None" && t.error !== undefined).length} found)`} />
                  </div>
                )}
                {stats.phase === 2 && (
                  <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                    <Check ok={stats.expectancy > 0} label={`Expectancy > 0R (current: ${fmt(stats.expectancy)}R)`} />
                    <Check ok={stats.evAtCiLow > -0.3} label={`95% CI lower > -0.3R (current: ${fmt(stats.evAtCiLow)}R)`} />
                    <Check ok={true} label="Max drawdown < 8% (track manually)" />
                    <Check ok={trades.filter(t => t.error === "Behavioral").length / Math.max(1, stats.total) < 0.10} label={`Behavioral errors < 10%`} />
                  </div>
                )}
                {stats.phase === 3 && (
                  <div style={{ fontSize: 12, lineHeight: 1.8 }}>
                    <Check ok={stats.expectancy > 0.20} label={`Expectancy > +0.20R (current: ${fmt(stats.expectancy)}R)`} />
                    <Check ok={stats.evAtCiLow > 0} label={`95% CI lower > 0R (current: ${fmt(stats.evAtCiLow)}R)`} />
                    <Check ok={stats.profitFactor > 1.3} label={`Profit factor > 1.3 (current: ${fmt(stats.profitFactor)})`} />
                    <Check ok={false} label="Performance across 2+ regimes (assess manually)" />
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ padding: 40, textAlign: "center", color: "var(--muted)", fontSize: 13 }}>
              Log your first closed trade to see statistics.
            </div>
          )}
        </div>
      )}

      {tab === "log trade" && <TradeForm onAdd={addTrade} />}
      {tab === "trade list" && <TradeTable trades={trades} onDelete={deleteTrade} />}
    </div>
  );
}

function Check({ ok, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <span style={{ fontSize: 14, color: ok ? "var(--green)" : "var(--red)" }}>{ok ? "✓" : "✗"}</span>
      <span style={{ color: ok ? "var(--fg)" : "var(--red)" }}>{label}</span>
    </div>
  );
}
