import { useState, useEffect } from "react";
import { api } from "../api";

export default function PaperTradingPanel({ onUpdate }) {
  const [account, setAccount] = useState(null);
  const [positions, setPositions] = useState([]);
  const [fills, setFills] = useState([]);
  const [executing, setExecuting] = useState(false);
  const [deciding, setDeciding] = useState(false);
  const [lastDecision, setLastDecision] = useState(null);
  const [price, setPrice] = useState(null);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10000);
    return () => clearInterval(interval);
  }, []);

  async function refresh() {
    try {
      const [acc, pos, fl, pr] = await Promise.all([
        api.getPaperAccount(),
        api.getPaperPositions(),
        api.getPaperFills(20),
        api.getPrice(),
      ]);
      setAccount(acc);
      setPositions(pos);
      setFills(fl);
      setPrice(pr);
    } catch {}
  }

  async function runDecision() {
    setDeciding(true);
    try {
      const result = await api.runDecision(false);
      setLastDecision(result);
    } catch (e) {
      alert("Decision failed: " + e.message);
    } finally {
      setDeciding(false);
    }
  }

  async function executeTrade() {
    if (!lastDecision?.decision_id) return;
    setExecuting(true);
    try {
      await api.executePaperTrade(lastDecision.decision_id);
      refresh();
      onUpdate?.();
      setLastDecision(null);
    } catch (e) {
      alert("Execution failed: " + e.message);
    } finally {
      setExecuting(false);
    }
  }

  async function closePosition(posId) {
    try {
      await api.closePaperPosition(posId, price?.price);
      refresh();
      onUpdate?.();
    } catch (e) {
      alert("Close failed: " + e.message);
    }
  }

  const dd = account?.drawdown_pct || 0;
  const dec = lastDecision?.decision;

  return (
    <div>
      {/* Account Summary */}
      {account && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Paper Trading Account</div>
              <div className="card-subtitle">Simulated execution — no real money</div>
            </div>
            <span className="badge badge-gold">PAPER MODE</span>
          </div>

          <div className="metrics-grid">
            <div className="metric-card">
              <div className="metric-label">Balance</div>
              <div className="metric-value gold">${account.balance?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Equity</div>
              <div className="metric-value">${account.equity?.toLocaleString(undefined, { minimumFractionDigits: 2 })}</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Unrealized P&L</div>
              <div className={`metric-value ${account.unrealized_pnl >= 0 ? "positive" : "negative"}`}>
                ${account.unrealized_pnl?.toFixed(2)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Drawdown</div>
              <div className={`metric-value ${dd > 3 ? "negative" : ""}`}>{dd.toFixed(2)}%</div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Daily P&L</div>
              <div className={`metric-value ${account.daily_pnl >= 0 ? "positive" : "negative"}`}>
                ${account.daily_pnl?.toFixed(2)}
              </div>
            </div>
            <div className="metric-card">
              <div className="metric-label">Open Positions</div>
              <div className="metric-value">{account.open_positions}</div>
            </div>
          </div>
        </div>
      )}

      {/* Decision & Execute */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Trade Decision</div>
            <div className="card-subtitle">Run structured pipeline then execute</div>
          </div>
          <div className="btn-group">
            <button className="btn btn-primary" onClick={runDecision} disabled={deciding}>
              {deciding && <span className="spinner" />}
              {deciding ? "Deciding..." : "Run Decision"}
            </button>
            {dec?.trade_or_no_trade === "trade" && (
              <button className="btn" onClick={executeTrade} disabled={executing} style={{ borderColor: "var(--green)", color: "var(--green)" }}>
                {executing ? "Executing..." : "Execute Paper Trade"}
              </button>
            )}
          </div>
        </div>

        {dec && (
          <div style={{ padding: 16, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)" }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <span className={`badge ${dec.trade_or_no_trade === "trade" ? "badge-green" : "badge-red"}`} style={{ fontSize: 12 }}>
                {dec.trade_or_no_trade === "trade" ? "TRADE SIGNAL" : "NO TRADE"}
              </span>
              <span style={{ fontFamily: "var(--font-mono)", color: "var(--gold)" }}>{dec.confidence}/100</span>
            </div>

            <div style={{ fontSize: 13, color: "var(--text)", marginBottom: 8 }}>
              <strong>Strategy:</strong> {dec.chosen_strategy} | <strong>State:</strong> {dec.market_state}
            </div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 }}>
              {dec.thesis_summary}
            </div>

            {dec.trade_or_no_trade === "trade" && (
              <div className="metrics-grid">
                <div className="metric-card">
                  <div className="metric-label">Entry</div>
                  <div className="metric-value" style={{ fontSize: 14 }}>${dec.entry?.toFixed(2)}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Stop</div>
                  <div className="metric-value negative" style={{ fontSize: 14 }}>${dec.stop?.toFixed(2)}</div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Target 1</div>
                  <div className="metric-value positive" style={{ fontSize: 14 }}>${dec.target_1?.toFixed(2)}</div>
                </div>
              </div>
            )}

            {dec.rationale?.length > 0 && (
              <div style={{ marginTop: 8, fontSize: 12, color: "var(--text-muted)" }}>
                {dec.rationale.map((r, i) => <div key={i}>- {r}</div>)}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Open Positions */}
      {positions.length > 0 && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <div className="card-title">Open Positions ({positions.length})</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Dir</th>
                  <th>Entry</th>
                  <th>Stop</th>
                  <th>Target</th>
                  <th>Lots</th>
                  <th>Strategy</th>
                  <th>Unrealized</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.position_id}>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{p.position_id}</td>
                    <td><span className={`badge ${p.direction === "long" ? "badge-green" : "badge-red"}`}>{p.direction?.toUpperCase()}</span></td>
                    <td>${p.entry?.toFixed(2)}</td>
                    <td>${p.stop?.toFixed(2)}</td>
                    <td>${p.target_1?.toFixed(2)}</td>
                    <td>{p.lots}</td>
                    <td><span className="badge badge-muted">{p.strategy}</span></td>
                    <td style={{ color: p.unrealized_pnl >= 0 ? "var(--green)" : "var(--red)", fontFamily: "var(--font-mono)" }}>
                      ${p.unrealized_pnl?.toFixed(2)}
                    </td>
                    <td>
                      <button className="btn btn-sm btn-danger" onClick={() => closePosition(p.position_id)}>Close</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Recent Fills */}
      {fills.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recent Fills</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Dir</th>
                  <th>Price</th>
                  <th>Lots</th>
                  <th>P&L</th>
                  <th>R-Mult</th>
                  <th>Strategy</th>
                </tr>
              </thead>
              <tbody>
                {fills.slice().reverse().map((f, i) => (
                  <tr key={i}>
                    <td style={{ fontSize: 11 }}>{f.timestamp ? new Date(f.timestamp).toLocaleTimeString() : "—"}</td>
                    <td><span className={`badge ${f.type === "open" ? "badge-blue" : "badge-muted"}`}>{f.type}</span></td>
                    <td><span className={`badge ${f.direction === "long" ? "badge-green" : "badge-red"}`}>{f.direction?.toUpperCase()}</span></td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>${f.fill_price?.toFixed(2) || f.exit_price?.toFixed(2)}</td>
                    <td>{f.lots}</td>
                    <td style={{ fontFamily: "var(--font-mono)", color: (f.pnl || 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                      {f.pnl != null ? `$${f.pnl.toFixed(2)}` : "—"}
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: (f.r_multiple || 0) >= 0 ? "var(--green)" : "var(--red)" }}>
                      {f.r_multiple != null ? `${f.r_multiple >= 0 ? "+" : ""}${f.r_multiple.toFixed(2)}R` : "—"}
                    </td>
                    <td><span className="badge badge-muted">{f.strategy || "—"}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!account && (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <div className="empty-title">Paper trading</div>
            <div className="empty-desc">
              Connect to the backend to see your paper trading account. No real money is involved.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
