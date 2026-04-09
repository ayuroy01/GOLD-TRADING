import { useState } from "react";
import FoundationPanel from "./components/FoundationPanel";
import JournalPanel from "./components/JournalPanel";
import OverviewPanel from "./components/OverviewPanel";
import RulesPanel from "./components/RulesPanel";

const views = [
  { id: "overview", label: "Overview" },
  { id: "rules", label: "Rules" },
  { id: "foundation", label: "Foundation" },
  { id: "journal", label: "Journal" },
];

export default function App() {
  const [activeView, setActiveView] = useState("overview");

  return (
    <div className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />

      <header className="topbar">
        <div>
          <p className="eyebrow">Claude Agent Project</p>
          <div className="brand-row">
            <span className="brand-mark" />
            <div>
              <h1>Gold V1 Execution Workbench</h1>
              <p className="subtle-copy">
                Runnable framework built around the original strategy assets.
              </p>
            </div>
          </div>
        </div>
        <nav className="topnav" aria-label="Primary views">
          {views.map((view) => (
            <button
              key={view.id}
              className={activeView === view.id ? "nav-button active" : "nav-button"}
              onClick={() => setActiveView(view.id)}
            >
              {view.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="content-shell">
        {activeView === "overview" && <OverviewPanel onSelectView={setActiveView} />}
        {activeView === "rules" && <RulesPanel />}
        {activeView === "foundation" && <FoundationPanel />}
        {activeView === "journal" && <JournalPanel />}
      </main>
    </div>
  );
}
