/**
 * The document picker — a demo control, not a product one.
 *
 * The POC's claim is that one catalog and one renderer produce different
 * interfaces for different documents. A single fixed document cannot demonstrate
 * that, and switching by restarting the backend breaks the flow of a demo. So the
 * page carries a picker: choose a document, watch the section re-compose.
 *
 * `expect` is shown deliberately. Stating what a document should produce *before*
 * running it is the difference between a demonstration and a reveal — the audience
 * gets to check the claim rather than be told what they just saw.
 *
 * This is chrome. It is hand-built and static, like the rest of the shell; the
 * agent has no say in it.
 */
export default function DocumentPicker({ documents, selected, onSelect, isBusy }) {
  if (!documents.length) return null;

  return (
    <section className="doc-picker" aria-label="Choose a document to analyse">
      <span className="small-label" style={{ margin: 0 }}>
        Document
      </span>

      <div className="doc-options" role="group">
        {documents.map((document) => {
          const isSelected = document.key === selected;
          return (
            <button
              key={document.key}
              type="button"
              className={isSelected ? 'doc-option selected' : 'doc-option'}
              // The agent is mid-run; switching now would race two streams onto
              // one surface and interleave their molecules.
              disabled={isBusy && !isSelected}
              aria-pressed={isSelected}
              onClick={() => {
                if (!isSelected) onSelect(document.key);
              }}
            >
              <span className="doc-title">{document.client}</span>
              <span className="doc-meta">
                {document.sector} · {document.reference}
              </span>
              <span className="doc-expect">{document.expect}</span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
