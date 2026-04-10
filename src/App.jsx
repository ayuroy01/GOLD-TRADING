import { useState, useCallback, useEffect } from "react";
import TradeExecutionPanel from "./components/TradeExecutionPanel";
import AnalyticsDashboard from "./components/AnalyticsDashboard";
import JournalPanel from "./components/JournalPanel";
import RulesPanel from "./components/RulesPanel";
import FoundationPanel from "./components/FoundationPanel";
import { loadTrades, migrateFromOldJournal } from "./data/tradeStore";

const views = [
  { id: "execute", label: "Execute" },
  { id: "analytics", label: "Analytics" },
  { id: "journal", label: "Journal" },
  { id: "rules", label: "Rules" },
  { id: "foundation", label: "Foundation" },
];

export default function App() {
  const [activeView, setActiveView] = useState("execute");
  const [trades, setTrades] = useState([]);

  // Load trades on mount + migrate old journal data
  useEffect(() => {
    migrateFromOldJournal();
    setTrades(loadTrades());
  }, []);

  // Callback for child components to trigger trade list refresh
  const refreshTrades = useCallback(() => {
    setTrades(loadTrades());
  }, []);

  const openCount = trades.filter(t => t.status === "open").length;
  const closedCount = trades.filter(t => t.status === "closed" && t.rMultiple != null).length;

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="topbar-left">
          <span className="brand-mark" />
          <div>
            <h1 className="brand-title">Gold V1</h1>
            <p className="brand-sub">XAU/USD Execution System</p>
          </div>
        </div>
        <nav className="topnav" aria-label="Primary views">
          {views.map((view) => (
            <button
              key={view.id}
              className={activeView === view.id ? "nav-btn active" : "nav-btn"}
              onClick={() => setActiveView(view.id)}
            >
              {view.label}
              {view.id === "execute" && openCount > 0 && (
                <span className="badge">{openCount}</span>
              )}
              {view.id === "analytics" && closedCount > 0 && (
                <span className="badge muted">{closedCount}</span>
              )}
            </button>
          ))}
        </nav>
        <div className="topbar-status">
          <span className="status-dot" />
          <span className="status-text">{trades.length} trades</span>
        </div>
      </header>

      <main className="content-shell">
        {activeView === "execute" && (
          <TradeExecutionPanel onTradeUpdate={refreshTrades} />
        )}
        {activeView === "analytics" && (
          <AnalyticsDashboard trades={trades} />
        )}
        {activeView === "journal" && (
          <JournalPanel trades={trades} onTradeUpdate={refreshTrades} />
        )}
        {activeView === "rules" && <RulesPanel />}
        {activeView === "foundation" && <FoundationPanel />}
      </main>
    </div>
  );
}
