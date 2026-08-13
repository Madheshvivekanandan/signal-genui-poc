import { A2uiSurface } from '@a2ui/react/v0_9';

/**
 * DS §4.1 — one accordion section.
 *
 * The shell is fixed: the numbered head, the signal count, the toggle, the body
 * surface, the CTA. Only the body is generated, and it is an A2UI surface — so
 * this component never knows what a callout or a score row is, and there is no
 * longer any code of ours between a message and the DOM.
 *
 * `A2uiSurface` renders the surface's `root` component with no wrapper of its
 * own, so the catalog's `MoleculeStack` lands exactly where the hand-written
 * `.molecule-stack` div used to be.
 *
 * Three states are distinct on purpose — streaming, empty, and failed are not the
 * same thing, and collapsing them is how a demo ends up showing a spinner over a
 * section that already failed.
 */
export default function Section({
  index,
  title,
  summary,
  surface,
  moleculeCount,
  signalCount,
  isStreaming,
  cta,
  aside,
}) {
  // The measurement rail only exists once a run has finished, so the body is a
  // single column until then. Grid columns are switched by a class rather than
  // left empty: an empty 200px track would indent the molecules for the whole
  // stream and then reflow them the moment the numbers arrived.
  const bodyClass = aside ? 'acc-body has-aside' : 'acc-body';

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

      <div className={bodyClass}>
        {/* Announced so the arrival of a generated section is not silent to a
            screen reader — the whole interaction here is visual by default. */}
        <div role="status" aria-live="polite" className="sr-only">
          {isStreaming
            ? `${title} is being generated`
            : `${title} ready, ${moleculeCount} components`}
        </div>

        <div className="acc-main">
          {surface ? <A2uiSurface surface={surface} /> : null}

          {isStreaming ? (
            <div className="stream-hint">Composing this section…</div>
          ) : (
            cta ?? null
          )}
        </div>

        {aside ?? null}
      </div>
    </section>
  );
}
