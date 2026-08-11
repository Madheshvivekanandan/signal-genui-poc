import Molecule from '../molecules/registry.jsx';

/**
 * DS §4.1 — one accordion section.
 *
 * The shell is fixed: the numbered head, the signal count, the toggle, the body
 * surface, the CTA. Only `molecules` is generated, and it is rendered through the
 * registry, so this component never knows what a callout or a score row is.
 *
 * Three states are distinct on purpose — streaming, empty, and failed are not the
 * same thing, and collapsing them is how a demo ends up showing a spinner over a
 * section that already failed.
 */
export default function Section({
  index,
  title,
  summary,
  molecules,
  signalCount,
  isStreaming,
  isLocked,
  cta,
  onInspect,
}) {
  if (isLocked) {
    return (
      <section className="glass" aria-label={`${title} (locked)`}>
        <div className="acc-head" style={{ opacity: 0.5 }}>
          <div className="title-block">
            <h3>
              <span className="section-num">{index}</span> {title}
            </h3>
          </div>
          <span className="review-trigger" style={{ letterSpacing: '0.10em' }}>
            Locked
          </span>
        </div>
      </section>
    );
  }

  return (
    <section className="glass" data-section={`section-${index}`}>
      <div className="acc-head">
        <div className="title-block">
          <h3>
            <span className="section-num">{index}</span> {title}
          </h3>
          {summary ? <div className="subtitle">{summary}</div> : null}
        </div>
        {signalCount > 0 ? (
          <button type="button" className="review-trigger">
            <span className="dot" />
            {signalCount} {signalCount === 1 ? 'signal' : 'signals'}
          </button>
        ) : null}
      </div>

      <div className="acc-body">
        {/* Announced so the arrival of a generated section is not silent to a
            screen reader — the whole interaction here is visual by default. */}
        <div role="status" aria-live="polite" className="sr-only">
          {isStreaming
            ? `${title} is being generated`
            : `${title} ready, ${molecules.length} components`}
        </div>

        <div className="molecule-stack">
          {molecules.map((molecule, position) => (
            <Molecule
              // Position is the identity here: the stream appends in order and
              // never reorders or filters, and the authoritative pass replaces
              // the whole list at once.
              key={position}
              molecule={molecule}
              onInspect={onInspect}
            />
          ))}
        </div>

        {isStreaming ? (
          <div className="stream-hint">Composing this section…</div>
        ) : (
          cta ?? null
        )}
      </div>
    </section>
  );
}
