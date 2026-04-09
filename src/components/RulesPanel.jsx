import { strategyMeta, strategySteps, validationPhases } from "../data/strategy";

function renderValue(value, path = "root") {
  if (Array.isArray(value)) {
    return (
      <ul className="content-list">
        {value.map((item, index) => (
          <li key={`${path}-${index}`}>{renderValue(item, `${path}-${index}`)}</li>
        ))}
      </ul>
    );
  }

  if (value && typeof value === "object") {
    return (
      <div className="object-stack">
        {Object.entries(value).map(([key, nested]) => (
          <div key={`${path}-${key}`} className="object-row">
            <strong>{key.replaceAll("_", " ")}</strong>
            <div>{renderValue(nested, `${path}-${key}`)}</div>
          </div>
        ))}
      </div>
    );
  }

  return <span>{String(value)}</span>;
}

export default function RulesPanel() {
  return (
    <section className="panel-stack">
      <article className="surface-card">
        <div className="section-head">
          <p className="eyebrow">System Specification</p>
          <h2>{strategyMeta.name}</h2>
        </div>
        <div className="meta-grid">
          <div>
            <span className="meta-label">Version</span>
            <strong>{strategyMeta.version}</strong>
          </div>
          <div>
            <span className="meta-label">Type</span>
            <strong>{strategyMeta.type}</strong>
          </div>
          <div>
            <span className="meta-label">Sessions</span>
            <strong>{strategyMeta.sessions.join(" / ")}</strong>
          </div>
          <div>
            <span className="meta-label">Principle</span>
            <strong>{strategyMeta.design_principle}</strong>
          </div>
        </div>
      </article>

      <div className="step-grid">
        {strategySteps.map((step) => (
          <article key={step.id} className="surface-card step-card">
            <div className="step-index">Step {step.index}</div>
            <h3>{step.title}</h3>
            <div className="rules-content">{renderValue(step.value, step.id)}</div>
          </article>
        ))}
      </div>

      <article className="surface-card">
        <div className="section-head">
          <p className="eyebrow">Validation Phases</p>
          <h2>Pass-fail checkpoints</h2>
        </div>
        <div className="step-grid">
          {Object.entries(validationPhases).map(([key, phase]) => (
            <article key={key} className="sub-card">
              <h3>{key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase())}</h3>
              <p className="subtle-copy">{phase.objective}</p>
              <div className="rules-content">{renderValue(phase, key)}</div>
            </article>
          ))}
        </div>
      </article>
    </section>
  );
}
