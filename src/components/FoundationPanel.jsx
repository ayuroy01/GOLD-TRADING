import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { foundationMarkdown } from "../data/strategy";

export default function FoundationPanel() {
  return (
    <section className="panel-stack">
      <article className="surface-card prose-shell">
        <div className="section-head">
          <p className="eyebrow">Mathematical Foundation</p>
          <h2>Original written thesis, rendered for reading</h2>
        </div>
        <div className="prose-view">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{foundationMarkdown}</ReactMarkdown>
        </div>
      </article>
    </section>
  );
}
