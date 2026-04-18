import { useState, useEffect, useCallback, lazy, Suspense } from "react";
import { api } from "./api";
import ReadinessBadges from "./components/ReadinessBadges";

// Lazy-load heavy panels
const AnalysisPanel = lazy(() => import("./components/AnalysisPanel"));
const StrategiesPanel = lazy(() => import("./components/StrategiesPanel"));
const BacktestPanel = lazy(() => import("./components/BacktestPanel"));
const PaperTradingPanel = lazy(() => import("./components/PaperTradingPanel"));
const JournalPanel = lazy(() => import("./components/JournalPanel"));
const MetricsPanel = lazy(() => import("./components/MetricsPanel"));
const SettingsPanel = lazy(() => import("./components/SettingsPanel"));

const VIEWS = [
  { id: "analysis", label: "Analysis" },
  { id: "strategies", label: "Strategies" },
  { id: "backtest", label: "Research" },
  { id: "paper", label: "Paper Trade" },
  { id: "journal", label: "Journal" },
  { id: "metrics", label: "Metrics" },
  { id: "settings", label: "Settings" },
];

function PanelLoader() {
  return (
    <div className="card" style={{ padding: 40, textAlign: "center" }}>
      <span className="spinner" />
      <p style={{ marginTop: 12, color: "var(--text-muted)", fontSize: 13 }}>Loading...</p>
    </div>
  );
}

const MODE_LABELS = {
  analysis_only: { label: "ANALYSIS ONLY", color: "var(--text-muted)" },
  backtest: { label: "BACKTEST", color: "var(--blue)" },
  paper_trading: { label: "PAPER", color: "var(--amber)" },
  live_disabled: { label: "LIVE DISABLED", color: "var(--red)" },
};

export default function App() {
  const [view, setView] = useState("analysis");
  const [trades, setTrades] = useState([]);
  const [connected, setConnected] = useState(null);
  const [hasApiKey, setHasApiKey] = useState(false);
  const [systemMode, setSystemMode] = useState("paper_trading");
  const [health, setHealth] = useState(null);

  const refreshTrades = useCallback(async () => {
    try {
      const data = await api.getTrades();
      setTrades(data);
    } catch {
      setTrades([]);
    }
  }, []);

  const refreshHealth = useCallback(() => {
    api
      .health()
      .then((h) => {
        setConnected(true);
        setHasApiKey(h.has_api_key);
        setSystemMode(h.system_mode || "paper_trading");
        setHealth(h);
      })
      .catch(() => setConnected(false));
  }, []);

  useEffect(() => {
    refreshHealth();
    refreshTrades();
    // Refresh readiness every 30s so DATA freshness stays honest.
    const id = setInterval(refreshHealth, 30000);
    return () => clearInterval(id);
  }, [refreshHealth, refreshTrades]);

  const openCount = trades.filter((t) => t.status === "open").length;
  const modeInfo = MODE_LABELS[systemMode] || MODE_LABELS.paper_trading;

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-bar" />
          <div>
            <div className="brand-name">Gold Intelligence</div>
            <div className="brand-sub">XAU / USD Trading Platform</div>
          </div>
        </div>

        <nav className="topnav">
          {VIEWS.map((v) => (
            <button
              key={v.id}
              className={`nav-btn${view === v.id ? " active" : ""}`}
              onClick={() => setView(v.id)}
            >
              {v.label}
              {v.id === "paper" && openCount > 0 && (
                <span
                  style={{
                    marginLeft: 6,
                    background: "var(--gold-dim)",
                    color: "var(--gold)",
                    fontSize: 10,
                    padding: "1px 6px",
                    borderRadius: 100,
                    fontWeight: 700,
                  }}
                >
                  {openCount}
                </span>
              )}
            </button>
          ))}
        </nav>

        <div className="topbar-right">
          <span
            className="badge"
            style={{
              background: "rgba(255,255,255,0.05)",
              color: modeInfo.color,
              border: `1px solid ${modeInfo.color}`,
              fontSize: 10,
              fontWeight: 700,
            }}
            title={`System mode: ${systemMode}`}
          >
            {modeInfo.label}
          </span>
          <ReadinessBadges health={health} />
          {!hasApiKey && connected && (
            <span
              className="badge badge-gold"
              title="Set ANTHROPIC_API_KEY for AI-powered analysis"
            >
              DEMO
            </span>
          )}
          <div className="status-indicator">
            <span
              className="status-dot"
              style={{
                background:
                  connected === true
                    ? "var(--green)"
                    : connected === false
                      ? "var(--red)"
                      : "var(--text-muted)",
              }}
            />
            {connected === true
              ? "Connected"
              : connected === false
                ? "Offline"
                : "..."}
          </div>
        </div>
      </header>

      <main className="main-content">
        {connected === false && (
          <div
            className="card"
            style={{ marginBottom: 20, borderColor: "var(--red)" }}
          >
            <p style={{ color: "var(--red)", fontWeight: 600, marginBottom: 6 }}>
              Backend not connected
            </p>
            <p style={{ color: "var(--text-secondary)", fontSize: 13 }}>
              Start the backend: <code>python backend/server.py</code> — then
              refresh this page.
            </p>
          </div>
        )}

        <Suspense fallback={<PanelLoader />}>
          {view === "analysis" && <AnalysisPanel />}
          {view === "strategies" && <StrategiesPanel />}
          {view === "backtest" && <BacktestPanel />}
          {view === "paper" && <PaperTradingPanel onUpdate={refreshTrades} />}
          {view === "journal" && (
            <JournalPanel trades={trades} onUpdate={refreshTrades} />
          )}
          {view === "metrics" && <MetricsPanel trades={trades} />}
          {view === "settings" && <SettingsPanel />}
        </Suspense>
      </main>
    </div>
  );
}
