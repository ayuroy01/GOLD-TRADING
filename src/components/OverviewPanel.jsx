import {
  strategyMeta,
  noTradeRules,
  validationPhases,
} from "../data/strategy";

const infoCards = [
  {
    label: "Instrument",
    value: strategyMeta.asset,
    detail: "Focused exposure for cleaner validation",
  },
  {
    label: "Analysis stack",
    value: `${strategyMeta.timeframes.analysis} → ${strategyMeta.timeframes.entry}`,
    detail: "H4 structure, H1 confirmation",
  },
  {
    label: "Risk",
    value: strategyMeta.risk_per_trade,
    detail: `Max ${strategyMeta.max_open_positions} concurrent positions`,
  },
];

export default function OverviewPanel({ onSelectView }) {
  const phases = Object.entries(validationPhases);

  return (
    <section className="panel-stack">
      <section className="hero-card">
        <div className="hero-copy">
          <p className="eyebrow">Execution Framework</p>
          <h1>Gold V1 turns a manual edge into a system you can actually run.</h1>
          <p className="hero-text">
            The app keeps the original strategy rules, mathematical foundation,
            and journal intact, then adds the missing execution shell around
            them so the project is usable, reviewable, and ready to validate.
          </p>
          <div className="hero-actions">
            <button className="primary-button" onClick={() => onSelectView("journal")}>
              Open journal workspace
            </button>
            <button className="secondary-button" onClick={() => onSelectView("rules")}>
              Read system rules
            </button>
          </div>
        </div>
        <div className="hero-grid">
          {infoCards.map((card) => (
            <article key={card.label} className="glass-card">
              <span className="card-label">{card.label}</span>
              <strong className="card-value">{card.value}</strong>
              <span className="card-detail">{card.detail}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="split-grid">
        <article className="surface-card">
          <div className="section-head">
            <p className="eyebrow">Trade Filter</p>
            <h2>Hard no-trade gates</h2>
          </div>
          <div className="chip-grid">
            {noTradeRules.map((rule) => (
              <span key={rule} className="signal-chip">
                {rule}
              </span>
            ))}
          </div>
        </article>

        <article className="surface-card">
          <div className="section-head">
            <p className="eyebrow">Validation Ladder</p>
            <h2>Three phases, one decision tree</h2>
          </div>
          <div className="phase-list">
            {phases.map(([key, phase]) => (
              <div key={key} className="phase-row">
                <div>
                  <strong>
                    {key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}
                  </strong>
                  <p>{phase.objective}</p>
                </div>
                <span className="phase-range">{phase.trades}</span>
              </div>
            ))}
          </div>
        </article>
      </section>
    </section>
  );
}
