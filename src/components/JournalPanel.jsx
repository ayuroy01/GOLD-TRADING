import JournalApp from "../../gold_v1_journal";

export default function JournalPanel() {
  return (
    <section className="panel-stack">
      <article className="surface-card journal-shell">
        <div className="section-head">
          <p className="eyebrow">Journal Workspace</p>
          <h2>Embedded execution journal</h2>
          <p className="subtle-copy">
            This panel mounts the original journal component directly so your
            authored trading workflow stays intact inside the new app shell.
          </p>
        </div>
        <div className="journal-stage">
          <JournalApp />
        </div>
      </article>
    </section>
  );
}
