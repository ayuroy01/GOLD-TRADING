import { useState, useEffect } from "react";
import { api } from "../api";

export default function StrategiesPanel() {
  const [data, setData] = useState(null);
  const [risk, setRisk] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    refresh();
  }, []);

  async function refresh() {
    setLoading(true);
    try {
      const [strats, riskData] = await Promise.all([
        api.getStrategies(),
        api.getRisk(),
      ]);
      setData(strats);
      setRisk(riskData);
    } catch (e) {
      console.error("Failed to load strategies:", e);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="card">
        <div style={{ padding: 40, textAlign: "center" }}>
          <span className="spinner" />
          <p style={{ marginTop: 12, color: "var(--text-muted)", fontSize: 13 }}>
            Evaluating strategies...
          </p>
        </div>
      </div>
    );
  }

  const strategies = data?.strategies || [];
  const validCount = data?.valid_count || 0;

  return (
    <div>
      {/* Risk Status */}
      {risk && (
        <div
          className="card"
          style={{
            marginBottom: 16,
            borderColor: risk.trading_allowed ? "var(--green)" : "var(--red)",
            borderLeftWidth: 3,
          }}
        >
          <div className="card-header">
            <div>
              <div className="card-title">Risk Status</div>
              <div className="card-subtitle">
                {risk.trading_allowed
                  ? "Trading allowed"
                  : `${risk.blockers?.length || 0} blocker(s) active`}
              </div>
            </div>
            <span
              className={`badge ${risk.trading_allowed ? "badge-green" : "badge-red"}`}
            >
              {risk.trading_allowed ? "CLEAR" : "BLOCKED"}
            </span>
          </div>
          {risk.blockers?.length > 0 && (
            <div>
              {risk.blockers.map((b, i) => (
                <div
                  key={i}
                  style={{
                    padding: "6px 0",
                    fontSize: 13,
                    color: b.severity === "hard" ? "var(--red)" : "var(--amber)",
                    borderBottom:
                      i < risk.blockers.length - 1
                        ? "1px solid var(--border)"
                        : "none",
                  }}
                >
                  <span style={{ fontWeight: 600 }}>[{b.rule}]</span> {b.reason}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Strategy Evaluations */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Strategy Evaluations</div>
            <div className="card-subtitle">
              {strategies.length} strategies · {validCount} valid setup
              {validCount !== 1 ? "s" : ""}
            </div>
          </div>
          <button className="btn btn-sm" onClick={refresh}>
            Refresh
          </button>
        </div>

        {strategies.map((s, i) => (
          <div
            key={i}
            style={{
              padding: 16,
              background: s.valid ? "var(--green-dim)" : "var(--bg-elevated)",
              border: `1px solid ${s.valid ? "var(--green)" : "var(--border)"}`,
              borderRadius: "var(--radius-sm)",
              marginBottom: i < strategies.length - 1 ? 12 : 0,
            }}
          >
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: 8,
              }}
            >
              <div>
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 700,
                    color: "var(--text)",
                    fontFamily: "var(--font-mono)",
                  }}
                >
                  {s.strategy_name}
                </span>
                <span
                  className={`badge ${s.valid ? "badge-green" : "badge-muted"}`}
                  style={{ marginLeft: 8 }}
                >
                  {s.valid ? "VALID SETUP" : "NO SETUP"}
                </span>
              </div>
              {s.valid && (
                <span
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontWeight: 700,
                    color: "var(--gold)",
                  }}
                >
                  {s.confidence}/100
                </span>
              )}
            </div>

            {s.valid ? (
              <div className="metrics-grid" style={{ marginBottom: 8 }}>
                <div className="metric-card">
                  <div className="metric-label">Direction</div>
                  <div
                    className={`metric-value ${s.direction === "long" ? "positive" : "negative"}`}
                    style={{ fontSize: 14 }}
                  >
                    {s.direction?.toUpperCase()}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Entry</div>
                  <div className="metric-value" style={{ fontSize: 14 }}>
                    ${s.entry?.toFixed(2)}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Stop</div>
                  <div className="metric-value" style={{ fontSize: 14 }}>
                    ${s.stop?.toFixed(2)}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Target 1</div>
                  <div className="metric-value" style={{ fontSize: 14 }}>
                    ${s.target_1?.toFixed(2)}
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">R:R</div>
                  <div
                    className={`metric-value ${s.risk_reward >= 2 ? "positive" : ""}`}
                    style={{ fontSize: 14 }}
                  >
                    {s.risk_reward?.toFixed(2)}:1
                  </div>
                </div>
                <div className="metric-card">
                  <div className="metric-label">Quality</div>
                  <div className="metric-value gold" style={{ fontSize: 14 }}>
                    {s.quality_score}
                  </div>
                </div>
              </div>
            ) : null}

            {s.invalidation_reason && !s.valid && (
              <div style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 4 }}>
                {s.invalidation_reason}
              </div>
            )}

            {s.rationale?.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {s.rationale.map((r, j) => (
                  <div
                    key={j}
                    style={{ fontSize: 12, color: "var(--text-secondary)", marginBottom: 2 }}
                  >
                    - {r}
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
