import { useState, Fragment } from "react";
import { api } from "../api";

const ERROR_TYPES = ["None", "Process", "Analytical", "Timing", "Behavioral"];

function fmt(n, d = 2) {
  return typeof n === "number" && !isNaN(n) ? n.toFixed(d) : "—";
}

function CloseTrade({ trade, onDone }) {
  const [exitPrice, setExitPrice] = useState("");
  const [exitReason, setExitReason] = useState("T1 hit");
  const [errorType, setErrorType] = useState("None");
  const [saving, setSaving] = useState(false);

  const ep = parseFloat(exitPrice) || 0;
  const risk = Math.abs(trade.entry - trade.stop);
  let rMult = null;
  if (ep && risk > 0) {
    const dir = trade.direction === "long" ? 1 : -1;
    rMult = Math.round(((ep - trade.entry) * dir / risk) * 100) / 100;
  }

  async function handleClose() {
    if (!ep) return;
    setSaving(true);
    try {
      await api.updateTrade(trade.id, {
        status: "closed",
        exit_price: ep,
        exit_reason: exitReason,
        r_multiple: rMult,
        error_type: errorType,
        closed_at: new Date().toISOString(),
      });
      onDone?.();
    } catch (e) {
      alert("Failed: " + e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div style={{ padding: 16, background: "var(--bg-elevated)", borderRadius: "var(--radius-sm)", marginTop: 8 }}>
      <div style={{ fontSize: 12, fontWeight: 600, color: "var(--gold)", marginBottom: 10, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Close Trade
      </div>
      <div className="form-grid" style={{ marginBottom: 12 }}>
        <div className="field">
          <label className="field-label">Exit Price</label>
          <input className="field-input" type="number" step="0.01" placeholder="3265.00" value={exitPrice} onChange={(e) => setExitPrice(e.target.value)} autoFocus />
        </div>
        <div className="field">
          <label className="field-label">Exit Reason</label>
          <select className="field-input" value={exitReason} onChange={(e) => setExitReason(e.target.value)}>
            {["T1 hit", "T2 hit", "Trailing stop", "Stop loss", "Breakeven", "Manual close", "Time exit"].map(r => <option key={r}>{r}</option>)}
          </select>
        </div>
        <div className="field">
          <label className="field-label">Error Classification</label>
          <select className="field-input" value={errorType} onChange={(e) => setErrorType(e.target.value)}>
            {ERROR_TYPES.map((e) => <option key={e}>{e}</option>)}
          </select>
        </div>
        {rMult !== null && (
          <div className="field">
            <label className="field-label">R-Multiple</label>
            <div style={{ padding: "9px 12px", fontFamily: "var(--font-mono)", fontSize: 18, fontWeight: 700, color: rMult >= 0 ? "var(--green)" : "var(--red)" }}>
              {rMult >= 0 ? "+" : ""}{fmt(rMult)}R
            </div>
          </div>
        )}
      </div>
      <div className="btn-group">
        <button className="btn btn-primary btn-sm" onClick={handleClose} disabled={!ep || saving}>
          {saving ? "Closing..." : "Confirm Close"}
        </button>
        <button className="btn btn-sm" onClick={() => onDone?.()}>Cancel</button>
      </div>
    </div>
  );
}

export default function JournalPanel({ trades = [], onUpdate }) {
  const [closingId, setClosingId] = useState(null);
  const [filter, setFilter] = useState("all");
  const [deleting, setDeleting] = useState(null);

  const filtered = trades
    .filter((t) => filter === "all" || t.status === filter)
    .sort((a, b) => (b.id || 0) - (a.id || 0));

  async function handleDelete(id) {
    if (!confirm("Delete this trade permanently?")) return;
    setDeleting(id);
    try {
      await api.deleteTrade(id);
      onUpdate?.();
    } catch (e) {
      alert("Failed: " + e.message);
    } finally {
      setDeleting(null);
    }
  }

  if (!trades.length) {
    return (
      <div className="card">
        <div className="empty-state">
          <div className="empty-icon">◈</div>
          <div className="empty-title">No trades logged</div>
          <div className="empty-desc">Use the Paper Trade tab to execute trades, or log manual entries. They will appear here for review and closure.</div>
        </div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="card-header">
        <div>
          <div className="card-title">Trade Journal</div>
          <div className="card-subtitle">{trades.length} total · {trades.filter(t => t.status === "open").length} open</div>
        </div>
        <div className="tab-bar" style={{ marginBottom: 0 }}>
          {["all", "open", "closed"].map((f) => (
            <button key={f} className={`tab-btn${filter === f ? " active" : ""}`} onClick={() => setFilter(f)}>
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Date</th>
              <th>Dir</th>
              <th>Entry</th>
              <th>Stop</th>
              <th>T1</th>
              <th>R:R</th>
              <th>Status</th>
              <th>Exit</th>
              <th>R-Mult</th>
              <th>Error</th>
              <th style={{ width: 100 }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((t) => (
              <Fragment key={t.id}>
                <tr>
                  <td>{t.date ? new Date(t.date).toLocaleDateString() : "—"}</td>
                  <td>
                    <span className={`badge ${t.direction === "long" ? "badge-green" : "badge-red"}`}>
                      {t.direction?.toUpperCase() || "—"}
                    </span>
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{fmt(t.entry)}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{fmt(t.stop)}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.t1 ? fmt(t.t1) : "—"}</td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.rr_to_t1 ? `${fmt(t.rr_to_t1)}:1` : "—"}</td>
                  <td>
                    <span className={`badge ${t.status === "open" ? "badge-gold" : "badge-muted"}`}>
                      {t.status?.toUpperCase() || "—"}
                    </span>
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)" }}>{t.exit_price ? fmt(t.exit_price) : "—"}</td>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 700, color: t.r_multiple > 0 ? "var(--green)" : t.r_multiple < 0 ? "var(--red)" : "var(--text-muted)" }}>
                    {t.r_multiple != null ? `${t.r_multiple >= 0 ? "+" : ""}${fmt(t.r_multiple)}R` : "—"}
                  </td>
                  <td>
                    {t.error_type && t.error_type !== "None" ? (
                      <span className="badge badge-red">{t.error_type}</span>
                    ) : "—"}
                  </td>
                  <td>
                    <div className="btn-group">
                      {t.status === "open" && (
                        <button className="btn btn-sm btn-primary" onClick={() => setClosingId(closingId === t.id ? null : t.id)}>
                          {closingId === t.id ? "Cancel" : "Close"}
                        </button>
                      )}
                      <button className="btn btn-sm btn-danger" onClick={() => handleDelete(t.id)} disabled={deleting === t.id}>×</button>
                    </div>
                  </td>
                </tr>
                {closingId === t.id && (
                  <tr>
                    <td colSpan={11} style={{ padding: 0 }}>
                      <CloseTrade trade={t} onDone={() => { setClosingId(null); onUpdate?.(); }} />
                    </td>
                  </tr>
                )}
                {t.notes && (
                  <tr>
                    <td colSpan={11} style={{ padding: "4px 14px 8px", fontSize: 12, color: "var(--text-muted)", fontStyle: "italic", borderBottom: "1px solid var(--border)" }}>
                      {t.notes}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
