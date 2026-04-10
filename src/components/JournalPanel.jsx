import { useMemo } from "react";
import { updateTrade, deleteTrade } from "../data/tradeStore";
import { rMultiple as calcRMultiple } from "../engine/tradeEngine";

const C = {
  bg: "#0a0e17",
  card: "#111827",
  border: "#1e293b",
  text: "#e2e8f0",
  muted: "#64748b",
  green: "#10b981",
  red: "#ef4444",
  accent: "#3b82f6",
  mono: "'SF Mono', 'Fira Code', monospace",
  sans: "system-ui, -apple-system, sans-serif",
};

const fmt = (n, d = 2) => (typeof n === "number" && !isNaN(n) ? n.toFixed(d) : "—");

export default function JournalPanel({ trades = [], onTradeUpdate }) {
  const sorted = useMemo(
    () => [...trades].sort((a, b) => (b.id || 0) - (a.id || 0)),
    [trades]
  );

  const handleDelete = (id) => {
    deleteTrade(id);
    onTradeUpdate?.();
  };

  if (!sorted.length) {
    return (
      <div style={{ padding: 40, textAlign: "center", color: C.muted, fontFamily: C.sans }}>
        <div style={{ fontSize: 48, opacity: 0.3, marginBottom: 16 }}>
          ◈
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, color: C.text, marginBottom: 8 }}>
          No trades logged
        </div>
        <div style={{ fontSize: 13, maxWidth: 360, margin: "0 auto", lineHeight: 1.6 }}>
          Use the Execute tab to validate and log trades. They will appear here for review.
        </div>
      </div>
    );
  }

  return (
    <div style={{ fontFamily: C.sans, color: C.text }}>
      <div style={{ marginBottom: 20 }}>
        <h2 style={{ fontSize: 20, fontWeight: 700, margin: 0, color: C.text }}>
          Trade Journal
        </h2>
        <p style={{ fontSize: 12, color: C.muted, marginTop: 4 }}>
          {sorted.length} trade{sorted.length !== 1 ? "s" : ""} logged — review, annotate, and track execution quality
        </p>
      </div>

      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: C.mono }}>
          <thead>
            <tr style={{ borderBottom: `2px solid ${C.border}` }}>
              {["#", "Date", "Dir", "Zone", "Trigger", "Entry", "Stop", "T1", "R:R", "Exit", "R-Mult", "Error", "Status", ""].map(h => (
                <th key={h} style={{
                  padding: "10px 8px",
                  textAlign: "left",
                  color: C.muted,
                  fontSize: 10,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  fontFamily: C.sans,
                  fontWeight: 600,
                  whiteSpace: "nowrap",
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sorted.map((t, i) => {
              const isLong = t.direction === "long";
              const rColor = t.rMultiple > 0 ? C.green : t.rMultiple < 0 ? C.red : C.muted;
              return (
                <tr key={t.id} style={{ borderBottom: `1px solid ${C.border}` }}>
                  <td style={cellStyle}>{sorted.length - i}</td>
                  <td style={cellStyle}>{t.date?.slice(0, 16) || "—"}</td>
                  <td style={{ ...cellStyle, color: isLong ? C.green : C.red, fontWeight: 600 }}>
                    {isLong ? "LONG" : "SHORT"}
                  </td>
                  <td style={cellStyle}>{t.zone || "—"}</td>
                  <td style={cellStyle}>{t.trigger || "—"}</td>
                  <td style={cellStyle}>{fmt(t.entry, 0)}</td>
                  <td style={cellStyle}>{fmt(t.stop, 0)}</td>
                  <td style={cellStyle}>{fmt(t.t1, 0)}</td>
                  <td style={cellStyle}>{fmt(t.rrToT1, 1)}</td>
                  <td style={cellStyle}>{t.status === "closed" ? fmt(t.exitPrice, 0) : "—"}</td>
                  <td style={{ ...cellStyle, color: rColor, fontWeight: 700 }}>
                    {t.rMultiple != null
                      ? (t.rMultiple > 0 ? "+" : "") + fmt(t.rMultiple) + "R"
                      : "—"}
                  </td>
                  <td style={{ ...cellStyle, color: t.error && t.error !== "None" ? C.red : C.muted }}>
                    {t.error === "None" || !t.error ? "—" : t.error}
                  </td>
                  <td style={cellStyle}>
                    <span style={{
                      fontSize: 10,
                      padding: "2px 8px",
                      borderRadius: 4,
                      background: t.status === "open" ? C.accent + "22" : C.border,
                      color: t.status === "open" ? C.accent : C.muted,
                      border: `1px solid ${t.status === "open" ? C.accent + "44" : C.border}`,
                      fontFamily: C.sans,
                    }}>
                      {t.status}
                    </span>
                  </td>
                  <td style={cellStyle}>
                    <button
                      onClick={() => handleDelete(t.id)}
                      style={{
                        background: "none",
                        border: "none",
                        color: C.muted,
                        cursor: "pointer",
                        fontSize: 14,
                        padding: 4,
                      }}
                      title="Delete trade"
                    >
                      ×
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Notes section for trades with notes */}
      {sorted.filter(t => t.notes).length > 0 && (
        <div style={{
          marginTop: 24,
          background: C.card,
          border: `1px solid ${C.border}`,
          borderRadius: 8,
          padding: "16px 20px",
        }}>
          <div style={{
            fontSize: 12,
            color: C.muted,
            textTransform: "uppercase",
            letterSpacing: "0.07em",
            marginBottom: 12,
            fontFamily: C.sans,
          }}>
            Trade Notes
          </div>
          {sorted.filter(t => t.notes).map(t => (
            <div key={t.id} style={{
              padding: "8px 0",
              borderBottom: `1px solid ${C.border}`,
              display: "flex",
              gap: 12,
              fontSize: 12,
            }}>
              <span style={{ color: C.muted, whiteSpace: "nowrap" }}>
                #{trades.indexOf(t) + 1}
              </span>
              <span style={{ color: C.text, lineHeight: 1.5 }}>{t.notes}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

const cellStyle = {
  padding: "10px 8px",
  verticalAlign: "middle",
  whiteSpace: "nowrap",
};
