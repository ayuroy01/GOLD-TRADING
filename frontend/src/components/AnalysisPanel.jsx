import { useState, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";

export default function AnalysisPanel() {
  const [analysis, setAnalysis] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [context, setContext] = useState("");
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  // Load market data on mount
  useEffect(() => {
    loadMarketData();
    loadHistory();
  }, []);

  async function loadMarketData() {
    try {
      const [price, macro, calendar] = await Promise.all([
        api.getPrice(),
        api.getMacro(),
        api.getCalendar(),
      ]);
      setMarketData({ price, macro, calendar });
    } catch (e) {
      console.error("Market data load failed:", e);
    }
  }

  async function loadHistory() {
    try {
      const log = await api.getAnalysisLog(5);
      setHistory(log.reverse());
    } catch {}
  }

  async function runAnalysis() {
    setLoading(true);
    setError(null);
    try {
      const result = await api.runAnalysis(context);
      setAnalysis(result);
      loadHistory();
      loadMarketData();
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const price = marketData?.price;
  const macro = marketData?.macro;
  const cal = marketData?.calendar;

  return (
    <div>
      {/* Market Overview Strip */}
      {price && (
        <div className="metrics-grid" style={{ marginBottom: 16 }}>
          <div className="metric-card">
            <div className="metric-label">XAU/USD</div>
            <div className="metric-value gold">
              ${price.price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </div>
            <div className="metric-sub">
              Spread: ${price.spread?.toFixed(2)} · {price.source}
            </div>
          </div>

          {macro && (
            <>
              <div className="metric-card">
                <div className="metric-label">USD Index</div>
                <div className="metric-value">{macro.usd_index}</div>
                <div className="metric-sub">
                  <span className={`badge ${macro.usd_regime === "strong" ? "badge-red" : macro.usd_regime === "weak" ? "badge-green" : "badge-muted"}`}>
                    {macro.usd_regime}
                  </span>
                </div>
              </div>
              <div className="metric-card">
                <div className="metric-label">10Y Treasury</div>
                <div className="metric-value">{macro.treasury_10y}%</div>
                <div className="metric-sub">{macro.rate_direction}</div>
              </div>
              <div className="metric-card">
                <div className="metric-label">Gold Bias</div>
                <div className={`metric-value ${macro.gold_macro_bias === "bullish" ? "positive" : macro.gold_macro_bias === "bearish" ? "negative" : ""}`}>
                  {macro.gold_macro_bias?.toUpperCase()}
                </div>
                <div className="metric-sub">Geo risk: {macro.geopolitical_risk}</div>
              </div>
            </>
          )}

          {cal && (
            <div className="metric-card">
              <div className="metric-label">Next High-Impact</div>
              <div className="metric-value" style={{ fontSize: 14 }}>
                {cal.nearest_high_impact?.name || "None"}
              </div>
              <div className="metric-sub">
                {cal.nearest_high_impact
                  ? `${cal.nearest_high_impact.hours_until?.toFixed(1)}h away`
                  : "—"}
                {cal.high_impact_within_2h && (
                  <span className="badge badge-red" style={{ marginLeft: 6 }}>
                    WITHIN 2H
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Analysis Controls */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div className="card-header">
          <div>
            <div className="card-title">Market Analysis</div>
            <div className="card-subtitle">AI-powered structured reasoning</div>
          </div>
          <button
            className="btn btn-primary"
            onClick={runAnalysis}
            disabled={loading}
          >
            {loading && <span className="spinner" />}
            {loading ? "Analyzing..." : "Run Analysis"}
          </button>
        </div>

        <div className="field" style={{ marginBottom: 12 }}>
          <label className="field-label">Additional Context (optional)</label>
          <input
            className="field-input"
            type="text"
            placeholder="e.g. Focus on London session setup, or I'm seeing a double bottom at 3220..."
            value={context}
            onChange={(e) => setContext(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && runAnalysis()}
          />
        </div>

        {loading && (
          <div>
            <div className="loading-bar">
              <div className="loading-bar-inner" />
            </div>
            <p style={{ fontSize: 12, color: "var(--text-muted)", marginTop: 6 }}>
              Fetching market data, running structured analysis pipeline...
            </p>
          </div>
        )}

        {error && (
          <div style={{ padding: 12, background: "var(--red-dim)", borderRadius: "var(--radius-sm)", color: "var(--red)", fontSize: 13, marginTop: 8 }}>
            {error}
          </div>
        )}
      </div>

      {/* Analysis Result */}
      {analysis && (
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <div>
              <div className="card-title">Analysis Result</div>
              <div className="card-subtitle">
                {analysis.model} · {analysis.iterations} iteration{analysis.iterations !== 1 ? "s" : ""}
              </div>
            </div>
            <span style={{ fontSize: 11, color: "var(--text-muted)", fontFamily: "var(--font-mono)" }}>
              {new Date(analysis.timestamp).toLocaleTimeString()}
            </span>
          </div>

          <div className="analysis-output">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {analysis.analysis}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* Analysis History */}
      {history.length > 0 && (
        <div className="card">
          <div className="card-header">
            <div className="card-title">Recent Analyses</div>
          </div>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>State</th>
                  <th>Decision</th>
                  <th>Confidence</th>
                </tr>
              </thead>
              <tbody>
                {history.map((h) => (
                  <tr key={h.id}>
                    <td>{new Date(h.timestamp).toLocaleString()}</td>
                    <td>
                      <span className="badge badge-muted">{h.analysis_type}</span>
                    </td>
                    <td>{h.market_state || "—"}</td>
                    <td>
                      <span className={`badge ${h.decision === "NO TRADE" ? "badge-red" : h.decision?.includes("BUY") || h.decision?.includes("SELL") ? "badge-green" : "badge-muted"}`}>
                        {h.decision || "—"}
                      </span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)" }}>
                      {h.confidence != null ? `${h.confidence}/100` : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty state */}
      {!analysis && !loading && history.length === 0 && (
        <div className="card">
          <div className="empty-state">
            <div className="empty-icon">◈</div>
            <div className="empty-title">No analysis yet</div>
            <div className="empty-desc">
              Click "Run Analysis" to fetch live market data and generate a structured trade decision through the AI pipeline.
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
